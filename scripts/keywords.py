#!/usr/bin/env python3
"""SOOP 인기 방송 제목의 단어를, 그 단어가 들어간 방송을 보고 있는 시청자 수로 집계해 오늘 기록에 저장한다."""
import json, os, re, sys, urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = ("https://live.sooplive.co.kr/api/main_broad_list_api.php?selectType=action"
       "&selectValue=all&orderType=view_cnt&pageNo=%d&lang=ko_KR")
PAGES = 5  # 한 쪽에 60개, 시청자 많은 순
STOP = set("""방송 생방 생방송 라이브 live on 오늘 오늘도 지금 시작 진행 합니다 해요 하는 하기 하고 같이 함께 그리고
진짜 그냥 소통 시간 24시간 ing vs the and with 입니다 있는 없는 에서 까지 부터 ㅋㅋ ㅋㅋㅋ ㅎㅎ 현재 도전 신입 오뱅 오뱅알 공지 휴방 방송중 시작합니다""".split())


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def num(v):
    try:
        return int(str(v).replace(",", ""))
    except ValueError:
        return 0


def words_of(b):
    ws = set(w.lower() for w in re.findall(r"[가-힣A-Za-z0-9]{2,}", b.get("broad_title") or ""))
    return [w for w in ws if w not in STOP and not w.isdigit()]


def tally(broads):
    count, viewers = Counter(), Counter()
    for b in broads:
        v = num(b.get("total_view_cnt"))
        for w in words_of(b):
            count[w] += 1
            viewers[w] += v
    return count, viewers


def load(path):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}


def main():
    broads, seen = [], set()
    for page in range(1, PAGES + 1):
        try:
            rows = json.loads(get(URL % page)).get("broad") or []
        except Exception as e:
            print("FAIL page", page, repr(e))
            break
        rows = [b for b in rows if b.get("broad_no") not in seen]
        if not rows:
            break
        seen.update(b.get("broad_no") for b in rows)
        broads += rows
    if not broads:
        print("방송 목록을 가져오지 못해 키워드를 건너뜁니다")
        return
    count, viewers = tally(broads)
    now = datetime.now(KST)
    today, yday = now.strftime("%Y-%m-%d"), (now - timedelta(days=1)).strftime("%Y-%m-%d")
    snapdir = os.path.join(ROOT, "data", "snapshots")
    path = os.path.join(snapdir, today[:7] + ".json")
    month = load(path)
    prev = (month if yday[:7] == today[:7] else load(os.path.join(snapdir, yday[:7] + ".json"))).get(yday, {})
    before = {k["word"]: k.get("viewers", 0) for k in prev.get("soopKeywords", [])}
    # 방송 2개 이상에서 쓰인 단어만, 시청자 합계 순
    top = sorted((w for w in count if count[w] >= 2), key=lambda w: (-viewers[w], -count[w]))[:30]
    snap = month.setdefault(today, {"date": today})
    snap["soopKeywords"] = [{"word": w, "count": count[w], "viewers": viewers[w],
                             "change": viewers[w] - before[w] if w in before else None,
                             "isNew": bool(before) and w not in before} for w in top]
    snap["soopSample"] = len(broads)
    os.makedirs(snapdir, exist_ok=True)
    json.dump(month, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("OK   soopKeywords", len(top), "방송", len(broads))


if __name__ == "__main__":
    main()
