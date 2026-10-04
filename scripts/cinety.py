#!/usr/bin/env python3
"""SOOP 시네티 공지 제목에서 날짜가 적힌 같이보기 일정을 뽑아 data/cinety.json 에 모은다."""
import json, os, re, urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "data", "cinety.json")
URL = "https://cinety.sooplive.com/api/api.php?type=get_main"
DATE = re.compile(r"(\d{1,2})/(\d{1,2})\s*\([월화수목금토일]\)")
WORK = re.compile(r"[<〈《](.+?)[>〉》]")
TIME = re.compile(r"(오전|오후|저녁|밤|낮|새벽)\s*\d{1,2}시(\s*\d{1,2}분)?")


def walk(node, found):
    """응답 어디에 있든 title_no 와 title_name 을 가진 항목(공지)을 모은다."""
    if isinstance(node, dict):
        if "title_no" in node and isinstance(node.get("title_name"), str):
            found[str(node["title_no"])] = node["title_name"]
        for v in node.values():
            walk(v, found)
    elif isinstance(node, list):
        for v in node:
            walk(v, found)


def parse(no, name, now):
    m = DATE.search(name)
    if not m:
        return None
    month, day = int(m.group(1)), int(m.group(2))
    year = now.year + (1 if now.month - month > 6 else -1 if month - now.month > 6 else 0)
    try:
        date = datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return None
    work = WORK.search(name)
    time = TIME.search(name)
    kind = "서비스 종료" if "종료" in name else "같이보기" if "같이보기" in name else "오픈"
    title = work.group(1) if work else re.sub(r"^\[[^\]]*\]\s*", "", name)[:40]
    return {"id": no, "date": date, "title": "시네티 " + title, "kind": kind, "time": time.group(0) if time else "",
            "note": name[:100], "url": "https://cinety.sooplive.com/board/notice/%s" % no}


def main():
    now = datetime.now(KST)
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,ko;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        print("FAIL cinety", repr(e)[:200])
        return
    found = {}
    walk(data, found)
    events = {e["id"]: e for e in (json.load(open(STORE, encoding="utf-8")) if os.path.exists(STORE) else [])}
    added = 0
    for no, name in found.items():
        e = parse(no, name, now)
        if e:
            added += no not in events
            events[no] = e
    since = (now - timedelta(days=60)).strftime("%Y-%m-%d")
    keep = sorted((e for e in events.values() if e["date"] >= since), key=lambda e: (e["date"], e["id"]))
    json.dump(keep, open(STORE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("OK   cinety 공지", len(found), "일정", len(keep), "새로", added)


if __name__ == "__main__":
    main()
