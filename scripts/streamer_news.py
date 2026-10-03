#!/usr/bin/env python3
"""지켜보는 스트리머와 지금 시청자 상위 스트리머의 SOOP 방송국 게시글을 모아 오늘 기록에 저장한다."""
import json, os, re, urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCH = os.path.join(ROOT, "data", "streamers.json")
LIVE = ("https://live.sooplive.co.kr/api/main_broad_list_api.php?selectType=action"
        "&selectValue=all&orderType=view_cnt&pageNo=1&lang=ko_KR")
TOP = 40    # 지금 시청자 상위 몇 명까지 함께 볼지
DAYS = 5    # 최근 며칠 글까지
HOT = re.compile(r"모집|신청|참가|참여|합격|발표|대회|컨텐츠|콘텐츠|서버|일정|예고|시참|내전|선발|오디션|이벤트")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def main():
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    since = (now - timedelta(days=DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    names = {}
    if os.path.exists(WATCH):
        for s in json.load(open(WATCH, encoding="utf-8")):
            names[s["id"]] = s.get("name") or s["id"]
    watched = set(names)
    try:
        for b in (json.loads(get(LIVE)).get("broad") or [])[:TOP]:
            names.setdefault(b["user_id"], b.get("user_nick") or b["user_id"])
    except Exception as e:
        print("FAIL live list", repr(e)[:200])
    posts, failed = [], 0
    for uid, name in names.items():
        try:
            boards = json.loads(get("https://chapi.sooplive.co.kr/api/%s/home" % uid)).get("boards") or []
        except Exception:
            failed += 1
            continue
        for p in boards:
            date, title = p.get("reg_date") or "", (p.get("title_name") or "").strip()
            if date < since or len(title) < 4:
                continue
            body = re.sub(r"\s+", " ", p.get("content") or "")[:120]
            posts.append({"id": uid, "nick": name, "title": title[:100], "body": body, "date": date[:16], "reads": int((p.get("count") or {}).get("read_cnt") or 0),
                          "hot": bool(HOT.search(title + " " + body)), "watched": uid in watched,
                          "url": "https://ch.sooplive.co.kr/%s/post/%s" % (uid, p.get("title_no"))})
    if not posts and failed:
        print("FAIL streamer news: 방송국", failed, "곳 모두 실패")
        return
    # 모집·일정 글 먼저, 그 안에서 조회수 많은(인기 스트리머) 순
    posts.sort(key=lambda p: (not p["hot"], -p["reads"]))
    path = os.path.join(ROOT, "data", "snapshots", today[:7] + ".json")
    month = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    month.setdefault(today, {"date": today})["soopNews"] = posts[:40]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(month, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("OK   soopNews", len(posts), "방송국", len(names), "실패", failed)


if __name__ == "__main__":
    main()
