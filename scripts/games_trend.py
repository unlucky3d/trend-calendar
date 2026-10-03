#!/usr/bin/env python3
"""치지직, 트위치, 스팀에서 지금 인기 있는 게임을 모아 오늘 기록에 저장한다."""
import html, json, os, re, urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
NOT_GAMES = {"just chatting", "irl", "special events", "music", "art", "sports", "asmr", "talk shows & podcasts",
             "pools, hot tubs, and beaches", "travel & outdoors", "food & drink", "politics", "i'm only sleeping",
             "always on", "co-working & studying", "software and game development", "animals, aquariums, and zoos"}
NAMES = os.path.join(ROOT, "data", "steam_names.json")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def num(v):
    try:
        return int(str(v).replace(",", ""))
    except ValueError:
        return 0


def chzzk():
    """인기 방송을 시청자 순으로 최대 200개 읽어 게임 카테고리별 시청자 합계를 낸다."""
    viewers, count, cursor = Counter(), Counter(), ""
    for _ in range(4):
        d = json.loads(get("https://api.chzzk.naver.com/service/v1/lives?size=50&sortType=POPULAR" + cursor))
        content = d.get("content") or {}
        for b in content.get("data") or []:
            name = b.get("liveCategoryValue")
            if not name or b.get("categoryType") != "GAME":
                continue
            viewers[name] += num(b.get("concurrentUserCount"))
            count[name] += 1
        nxt = (content.get("page") or {}).get("next") or {}
        if not nxt:
            break
        cursor = "&concurrentUserCount=%s&liveId=%s" % (nxt.get("concurrentUserCount"), nxt.get("liveId"))
    return [{"name": n, "viewers": v, "count": count[n]} for n, v in viewers.most_common(15)]


def twitch():
    page = get("https://twitchtracker.com/games")
    seen, out = set(), []
    for m in re.finditer(r'<a\b[^>]*href="/games/(\d+)"[^>]*>([^<]{2,80})</a>', page):
        name = html.unescape(m.group(2)).strip()
        if m.group(1) in seen or not name or name.lower() in NOT_GAMES:
            continue
        seen.add(m.group(1))
        out.append({"name": name})
    if not out:
        raise ValueError("목록을 찾지 못함: " + re.sub(r"\s+", " ", page[:200]))
    return out[:15]


def steam_name(appid, cache):
    key = str(appid)
    if key not in cache:
        try:
            d = json.loads(get("https://store.steampowered.com/api/appdetails?appids=%s&filters=basic&l=koreana&cc=kr" % key))
            cache[key] = d[key]["data"]["name"]
        except Exception:
            try:  # 한국 스토어에 없는 게임은 해외 스토어 이름으로
                d = json.loads(get("https://store.steampowered.com/api/appdetails?appids=%s&filters=basic&l=koreana&cc=us" % key))
                cache[key] = d[key]["data"]["name"] + " (한국 스팀 미판매)"
            except Exception:
                return "앱 " + key
    return cache[key]


def steam(cache):
    d = json.loads(get("https://api.steampowered.com/ISteamChartsService/GetMostPlayedGames/v1/"))
    ranks = d["response"]["ranks"]

    def row(r):
        return {"name": steam_name(r["appid"], cache), "players": num(r.get("peak_in_game") or r.get("concurrent_in_game")),
                "rank": r.get("rank"), "url": "https://store.steampowered.com/app/%s" % r["appid"]}

    top = [row(r) for r in ranks[:15]]
    # 급상승: 지난주 순위보다 많이 오른 게임, 지난주 100위 밖이던 게임은 새로 진입으로 표시
    risers = []
    for r in ranks:
        last = r.get("last_week_rank")
        gain = (last - r["rank"]) if isinstance(last, int) and last > 0 else None
        if gain is None or gain >= 5:
            risers.append((gain if gain is not None else 10 ** 6, r))
    risers.sort(key=lambda x: (-x[0], x[1]["rank"]))
    rising = []
    for gain, r in risers[:10]:
        item = row(r)
        item["gain"] = None if gain == 10 ** 6 else gain
        item["isNew"] = gain == 10 ** 6
        rising.append(item)
    return top, rising


def steam_sellers():
    d = json.loads(get("https://store.steampowered.com/api/featuredcategories?cc=kr&l=koreana"))
    seen, out = set(), []
    for it in d["top_sellers"]["items"]:
        if it.get("name") and it["name"] not in seen:
            seen.add(it["name"])
            out.append({"name": it["name"], "url": "https://store.steampowered.com/app/%s" % it.get("id")})
    return out[:10]


def main():
    today = datetime.now(KST).strftime("%Y-%m-%d")
    path = os.path.join(ROOT, "data", "snapshots", today[:7] + ".json")
    month = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    snap = month.setdefault(today, {"date": today})
    cache = json.load(open(NAMES, encoding="utf-8")) if os.path.exists(NAMES) else {}

    def run(label, fn):
        try:
            result = fn()
            print("OK  ", label)
            return result
        except Exception as e:
            print("FAIL", label, repr(e)[:300])
            return None

    for key, fn in (("chzzk", chzzk), ("twitch", twitch), ("steamSellers", steam_sellers)):
        rows = run(key, fn)
        if rows:
            snap[key] = rows
    both = run("steam", lambda: steam(cache))
    if both:
        snap["steamTop"], snap["steamRising"] = both
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(month, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(cache, open(NAMES, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)


if __name__ == "__main__":
    main()
