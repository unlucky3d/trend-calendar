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
PAGES = 6   # 한 쪽에 60명, 시청자 많은 순 (6쪽 = 상위 360명)
DAYS = 5    # 최근 며칠 글까지
KEEP = 80   # 저장할 글 수
# 제목에 이 단어가 들어간 글만 보여 준다
HOT = re.compile(r"신청|모집|발표|서버|참가|합격|대회|컨텐츠|콘텐츠|내전|선발|오디션|시참")


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
    posts, failed = [], 0
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(boards, list(names)))
    for uid, rows in results:
        if rows is None:
            failed += 1
            continue
        for p in rows:
            date, title = p.get("reg_date") or "", (p.get("title_name") or "").strip()
            hit = HOT.search(title)
            if date < since or not hit:
                continue
            posts.append({"id": uid, "nick": names[uid] or p.get("user_nick") or uid, "title": title[:100],
                          "body": re.sub(r"\s+", " ", p.get("content") or "")[:120], "date": date[:16],
                          "reads": num((p.get("count") or {}).get("read_cnt")), "tag": hit.group(0),
                          "viewers": live.get(uid, 0), "peak": peak.get(uid, 0), "watched": uid in watched,
                          "url": "https://www.sooplive.com/station/%s/post/%s" % (uid, p.get("title_no"))})
    if not posts and failed:
        print("FAIL streamer news: 방송국", failed, "곳 모두 실패")
        return
    # 시청자 많은 스트리머 순. 아직 시청자 기록이 없는 지켜보는 스트리머는 맨 위. 같은 스트리머 안에서는 조회수 순
    posts.sort(key=lambda p: (not (p["watched"] and not p["peak"]), -p["peak"], p["id"], -p["reads"]))
    seen = set()  # 같은 스트리머가 같은 제목으로 다시 올린 글은 조회수 높은 것만
    posts = [p for p in posts if not ((p["id"], p["title"]) in seen or seen.add((p["id"], p["title"])))]
    path = os.path.join(ROOT, "data", "snapshots", today[:7] + ".json")
    month = load(path, {})
    month.setdefault(today, {"date": today})["soopNews"] = posts[:KEEP]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(month, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(peak, open(PEAK, "w", encoding="utf-8"), ensure_ascii=False, sort_keys=True)
    print("OK   soopNews", len(posts), "방송국", len(names), "실패", failed)


if __name__ == "__main__":
    main()
