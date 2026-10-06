#!/usr/bin/env python3
"""지켜보는 스트리머와 지금 시청자 상위 스트리머의 SOOP 방송국 게시글 중 콘텐츠 공지를 모아 오늘 기록에 저장한다."""
import json, os, re, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCH = os.path.join(ROOT, "data", "streamers.json")
PEAK = os.path.join(ROOT, "data", "streamer_peak.json")
LIVE = ("https://live.sooplive.co.kr/api/main_broad_list_api.php?selectType=action"
        "&selectValue=all&orderType=view_cnt&pageNo=%d&lang=ko_KR")
ROSTER = 800  # 방송을 꺼 둔 스트리머도 최고 시청자 순으로 이만큼까지 함께 확인
PER = 3       # 한 스트리머당 보여 줄 글 수
PAGES = 6   # 한 쪽에 60명, 시청자 많은 순 (6쪽 = 상위 360명)
DAYS = 5    # 최근 며칠 글까지
MIN_READS = 500  # 조회수가 이보다 적은 글은 숨김
MIN_RECRUIT = 100  # 모집 글은 이 조회수부터 보여 준다
KEEP = 80   # 저장할 글 수
# 제목으로 글을 분류한다. 어디에도 안 걸리는 글, "신청했다"류의 후기 글, 벌칙·방셀·채용 공지는 숨긴다
APPLIED = re.compile(r"신청했|신청해|신청함|신청 ?완료|지원했|지원함|참가했|참여했|하고 ?싶|붙었|뽑혔|입주했|입주한|합격했|떨어졌|탈락했")
SKIP = re.compile(r"편집자|매니저|디자이너|썸네일|PM ?모집|팝니다|삽니다|갖고 ?계신|방셀|리캡|휴방|생방 ?공지|방송 ?공지|벌칙|API|하실 ?분들은|\d+카|알바|작업해 ?주실|자막", re.I)
RULES = [
    ("모집", re.compile(r"모집|공모|신청자|신청 ?받|신청하신|신청하실|신청 ?방법|신청 ?양식|신청서|참가 ?신청|입주 ?신청|참가자|참여자|지원자|입주자"
                      r"|선발|오디션|구합니다|구해요|구함|구인|구해봅|하실 ?분|오실 ?분|함께하실|같이 ?하실|참여하실|참가하실|접수|선착순|찾습니다|찾아요|찾고 ?있|\[합방\]|합방 ?(모집|하실|멤버)")),
    ("발표", re.compile(r"합격자|합격 ?발표|명단|라인업|(결과|참가자|입주자|멤버|대진|팀) ?발표")),
    ("대회", re.compile(r"대회|내전|리그|토너먼트|멸망전|예선|본선|결승|대진|조추첨|드래프트|팀 ?경매")),
]
TOPIC = re.compile(r"서버|컨텐츠|콘텐츠|프로젝트")
NOTICE = re.compile(r"공지|안내|오픈|설명회|규칙|시즌 ?\d|개최|예고|입주")


def classify(title):
    if APPLIED.search(title) or SKIP.search(title):
        return ""
    for tag, rule in RULES:
        if rule.search(title):
            return tag
    return "공지" if TOPIC.search(title) and NOTICE.search(title) else ""


# 글 분류: 위에서부터 먼저 걸리는 것으로 정한다
CATS = [
    ("배그", re.compile(r"배그|배틀그라운드|PUBG|펍지", re.I)),
    ("마크", re.compile(r"마크|마인크래프트|그냥서버", re.I)),
    ("노래", re.compile(r"노래|보컬|가요|커버곡|음악|합창|밴드|작곡|최애곡|OST", re.I)),
    ("크루모집", re.compile(r"크루|엔터|동아리|소속사|멤버 ?모집|오디션|클랜|길드|유니온")),
    ("종합게임", re.compile(r"게임|CK|내전|대회|리그|토너먼트|멸망전|롤|LOL|발로|FC|피파|스타|러스트|서버|와우|WOW|로아|메이플|철권|오버워치|합방", re.I)),
]
DEADLINE = re.compile(r"(?:~|까지|마감)\s*(\d{1,2})\s*[/.월]\s*(\d{1,2})|(\d{1,2})\s*[/.월]\s*(\d{1,2})\s*일?\s*(?:까지|마감)")


def category(text):
    for name, rule in CATS:
        if rule.search(text):
            return name
    return "기타"


def deadline(text, now):
    """'~10/6', '10월 9일까지', '10/9 마감' 같은 표현에서 마감일을 뽑는다. 없으면 빈 문자열."""
    m = DEADLINE.search(text)
    if not m:
        return ""
    month, day = int(m.group(1) or m.group(3)), int(m.group(2) or m.group(4))
    year = now.year + (1 if now.month - month > 6 else -1 if month - now.month > 6 else 0)
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return ""


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def num(v):
    try:
        return int(str(v).replace(",", ""))
    except ValueError:
        return 0


def load(path, default):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else default


def boards(uid):
    try:
        return uid, json.loads(get("https://chapi.sooplive.co.kr/api/%s/home" % uid)).get("boards") or []
    except Exception:
        return uid, None


def main():
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    since = (now - timedelta(days=DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    names = {s["id"]: s.get("name") or "" for s in load(WATCH, [])}
    watched = set(names)
    live = {}
    for page in range(1, PAGES + 1):
        try:
            rows = json.loads(get(LIVE % page)).get("broad") or []
        except Exception as e:
            print("FAIL live list", page, repr(e)[:200])
            break
        if not rows:
            break
        for b in rows:
            live[b["user_id"]] = max(live.get(b["user_id"], 0), num(b.get("total_view_cnt")))
            names.setdefault(b["user_id"], b.get("user_nick") or "")
    # 스트리머 인기 = 지금 시청자 수와 지금까지 본 최고 시청자 수 중 큰 값 (방송을 꺼 둔 시간에도 순서 유지)
    peak = load(PEAK, {})
    for uid, v in live.items():
        peak[uid] = max(peak.get(uid, 0), v)
    for uid in sorted(peak, key=peak.get, reverse=True)[:ROSTER]:  # 예전에 본 스트리머는 방송 중이 아니어도 확인
        names.setdefault(uid, "")
    posts, failed = [], 0
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(boards, list(names)))
    for uid, rows in results:
        if rows is None:
            failed += 1
            continue
        for p in rows:
            date, title = p.get("reg_date") or "", (p.get("title_name") or "").strip()
            tag = classify(title)
            if date < since or not tag or num((p.get("count") or {}).get("read_cnt")) < (MIN_RECRUIT if tag == "모집" else MIN_READS):
                continue
            posts.append({"id": uid, "nick": names[uid] or p.get("user_nick") or uid, "title": title[:100],
                          "body": re.sub(r"\s+", " ", p.get("content") or "")[:120], "date": date[:16], "cat": category(title + " " + (p.get("content") or "")),
                          "deadline": deadline(title + " " + (p.get("content") or ""), now),
                          "reads": num((p.get("count") or {}).get("read_cnt")), "tag": tag,
                          "viewers": live.get(uid, 0), "peak": peak.get(uid, 0), "watched": uid in watched,
                          "url": "https://www.sooplive.com/station/%s/post/%s" % (uid, p.get("title_no"))})
    if not posts and failed:
        print("FAIL streamer news: 방송국", failed, "곳 모두 실패")
        return
    # 시청자 많은 스트리머 순. 아직 시청자 기록이 없는 지켜보는 스트리머는 맨 위. 같은 스트리머 안에서는 조회수 순
    posts.sort(key=lambda p: (not (p["watched"] and not p["peak"]), -p["peak"], p["id"], -p["reads"]))
    seen = set()  # 같은 스트리머가 같은 제목으로 다시 올린 글은 조회수 높은 것만
    posts = [p for p in posts if not ((p["id"], p["title"]) in seen or seen.add((p["id"], p["title"])))]
    posts = [p for p in posts if not p["deadline"] or p["deadline"] >= today]   # 마감이 지난 글은 숨긴다
    per = {}
    posts = [p for p in posts if per.setdefault(p["id"], []).append(1) or len(per[p["id"]]) <= PER]
    path = os.path.join(ROOT, "data", "snapshots", today[:7] + ".json")
    month = load(path, {})
    month.setdefault(today, {"date": today})["soopNews"] = posts[:KEEP]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(month, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(peak, open(PEAK, "w", encoding="utf-8"), ensure_ascii=False, sort_keys=True)
    print("OK   soopNews", len(posts), "방송국", len(names), "실패", failed)


if __name__ == "__main__":
    main()
