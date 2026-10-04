#!/usr/bin/env python3
"""SOOP 시네티 공지 게시판에서 작품별 서비스 기간(오픈~종료)과 날짜가 적힌 같이보기 일정을 뽑아 data/cinety.json 에 저장한다."""
import json, os, re, urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "data", "cinety.json")
BOARD = ("https://api-channel.sooplive.com/v1.2/channel/aforiginal/board?page=%d&bbsNo=94915546"
         "&perPage=20&field=title,contents&keyword=&type=all")
MAIN = "https://cinety.sooplive.com/api/api.php?type=get_main"
PAGES = 6   # 한 쪽에 20개, 최신 순
DATE = re.compile(r"(\d{1,2})/(\d{1,2})\s*\([월화수목금토일]\)")
WORK = re.compile(r"[<〈《](.+?)[>〉》]")
TIME = re.compile(r"(오전|오후|저녁|밤|낮|새벽)\s*\d{1,2}시(\s*\d{1,2}분)?")
ENDS = re.compile(r"종료\s*일시\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일")
KINDS = ("영화", "드라마", "애니메이션", "예능")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def norm(title):
    """'은혼 1기', '나의 히어로 아카데미아 5-6기' 처럼 시즌 표기가 달라도 같은 작품으로 묶는 열쇠."""
    t = re.sub(r"\s*(시즌\s*\d+|\d+\s*[-~]\s*\d+\s*기|\d+\s*기)\s*$", "", title.strip())
    return re.sub(r"\s+", "", t)


def title_date(name, now):
    m = DATE.search(name)
    if not m:
        return ""
    month, day = int(m.group(1)), int(m.group(2))
    year = now.year + (1 if now.month - month > 6 else -1 if month - now.month > 6 else 0)
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return ""


def text_end(text):
    """본문의 '종료일시 2026년 10월 5일(월) 오후 3시' 를 (날짜, 시간) 으로. 연장 공지는 마지막(변경) 일시를 쓴다."""
    hits = list(ENDS.finditer(text))
    if not hits:
        return "", ""
    m = hits[-1]
    t = TIME.search(text[m.end():m.end() + 16])
    return "%s-%02d-%02d" % (m.group(1), int(m.group(2)), int(m.group(3))), t.group(0) if t else ""


def build(posts, free, now):
    works, events = {}, {}

    def work(title):
        return works.setdefault(norm(title), {"title": title, "start": "", "startTime": "", "end": "", "endTime": "",
                                              "kind": "", "url": ""})

    for p in sorted(posts, key=lambda p: p.get("regDate") or ""):   # 오래된 글부터, 나중 공지가 덮어쓴다
        name = p.get("titleName") or ""
        no = str(p.get("titleNo"))
        url = "https://cinety.sooplive.com/board/notice/" + no
        text = re.sub(r"\s+", " ", ((p.get("content") or {}).get("textContent") or ""))
        titles = WORK.findall(name)
        date = title_date(name, now)
        time = TIME.search(name)
        if ("종료" in name or "연장" in name) and titles:
            end, end_time = text_end(text)
            for t in titles:
                w = work(t)
                w["end"], w["endTime"] = end or date, end_time
                w["url"] = w["url"] or url
        elif "오픈" in name and date and titles:
            for t in titles:
                w = work(t)
                w.update(title=t, start=date, startTime=time.group(0) if time else "", url=url, end="", endTime="")
                w["kind"] = next((k for k in KINDS if k in name), "")
        elif date:
            title = titles[0] if titles else re.sub(r"^\[[^\]]*\]\s*", "", name)[:40]
            events[no] = {"id": no, "date": date, "title": "시네티 " + title, "kind": "같이보기" if "같이보기" in name else "안내",
                          "time": time.group(0) if time else "", "url": url}
    for f in free:   # 지금 무료 시청 목록에 있는데 오픈 공지를 못 찾은 작품
        title, start = f.get("title") or "", (f.get("episode_date") or "")[:10]
        if not title or not start or re.search(r"예고편|하이라이트", title) or norm(title) in works:
            continue
        work(title).update(start=start, url="https://cinety.sooplive.com/content/detail/%s" % f.get("no"))
    today = now.strftime("%Y-%m-%d")
    old = (now - timedelta(days=60)).strftime("%Y-%m-%d")
    older = (now - timedelta(days=120)).strftime("%Y-%m-%d")
    keep = [w for w in works.values()
            if (w["end"] and w["end"] >= old) or (not w["end"] and w["start"] >= older)]
    live = {norm(f.get("title") or "") for f in free}   # 지금 시청 목록에 있는 작품
    for w in keep:
        w["live"] = norm(w["title"]) in live
        if w["end"] and w["start"] and w["end"] < w["start"]:
            w["end"], w["endTime"] = "", ""   # 재오픈 등으로 순서가 뒤집힌 경우 종료일은 버린다
    keep.sort(key=lambda w: (w["start"] or w["end"], w["title"]))
    ev = sorted((e for e in events.values() if e["date"] >= old), key=lambda e: (e["date"], e["id"]))
    return {"updated": today, "works": keep, "events": ev}


def main():
    now = datetime.now(KST)
    posts, seen = [], set()
    for page in range(1, PAGES + 1):
        try:
            d = get(BOARD % page)
        except Exception as e:
            print("FAIL cinety board", page, repr(e)[:200])
            break
        rows = (d.get("noticeData") or []) + (d.get("contents") or [])
        if not d.get("contents"):
            break
        for p in rows:
            if p.get("titleNo") not in seen:
                seen.add(p.get("titleNo"))
                posts.append(p)
    if not posts:
        return
    free = []
    try:
        for sec in get(MAIN)["data"]["mainDisplayData"]:
            if "무료" in (sec.get("title") or ""):
                info = sec.get("display_info")
                info = json.loads(info) if isinstance(info, str) else info
                free += info.get("dataInfo") or []
    except Exception as e:
        print("FAIL cinety main", repr(e)[:200])
    out = build(posts, free, now)
    json.dump(out, open(STORE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("OK   cinety 공지", len(posts), "작품", len(out["works"]), "일정", len(out["events"]))


if __name__ == "__main__":
    main()
