#!/usr/bin/env python3
"""매시간 트렌드를 모아 data/snapshots/YYYY-MM.json 에 오늘 날짜로 저장한다. 표준 라이브러리만 사용."""
import html, json, os, re, sys, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def text(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def num(v):
    try:
        return int(str(v).replace(",", ""))
    except ValueError:
        return 0


def anchors(page, href_pattern):
    """href 가 패턴에 맞는 링크를 (주소, 글자) 로 순서대로, 주소 중복 없이 돌려준다."""
    seen, out = set(), []
    for m in re.finditer(r'<a\b[^>]*href="(%s)"[^>]*>(.*?)</a>' % href_pattern, page, re.S):
        url, label = html.unescape(m.group(1)), text(m.group(2))
        key = re.sub(r"[?#].*", "", url)
        if key in seen or len(label) < 6:
            continue
        seen.add(key)
        out.append((url, label))
    return out


def soop_categories():
    d = json.loads(get("https://sch.sooplive.co.kr/api.php?m=categoryList&szKeyword=&szOrder=view_cnt"
                       "&nPageNo=1&nListCnt=30&nOffset=0&szPlatform=pc"))
    return [{"name": c["category_name"], "viewers": num(c.get("view_cnt"))} for c in d["data"]["list"][:15]]


def soop_live():
    d = json.loads(get("https://live.sooplive.co.kr/api/main_broad_list_api.php?selectType=action"
                       "&selectValue=all&orderType=view_cnt&pageNo=1&lang=ko_KR"))
    return [{"nick": b.get("user_nick", ""), "title": b.get("broad_title", ""),
             "category": b.get("category_name", ""), "viewers": num(b.get("total_view_cnt")),
             "url": "https://play.sooplive.co.kr/%s/%s" % (b.get("user_id", ""), b.get("broad_no", ""))}
            for b in d["broad"][:12]]


def google():
    ns = {"ht": "https://trends.google.com/trending/rss"}
    out = []
    for it in ET.fromstring(get("https://trends.google.com/trending/rss?geo=KR")).iter("item"):
        news = it.find("ht:news_item", ns)
        out.append({"title": it.findtext("title", ""),
                    "traffic": it.findtext("ht:approx_traffic", "", ns),
                    "headline": news.findtext("ht:news_item_title", "", ns) if news is not None else "",
                    "url": news.findtext("ht:news_item_url", "", ns) if news is not None else ""})
    out.sort(key=lambda g: -num(g["traffic"].rstrip("+")))
    return out[:12]


def news():
    items = anchors(get("https://news.daum.net/"), r"https://v\.daum\.net/v/\d+[^\"]*")
    return [{"title": t[:90], "source": "다음 뉴스", "url": u} for u, t in items[:10]]


def community():
    items = anchors(get("https://bbs.ruliweb.com/best/humor_only/now"),
                    r"https://bbs\.ruliweb\.com/best/board/\d+/read/\d+[^\"]*")
    return [{"title": re.sub(r"\s*\(\d+\)$", "", t)[:90], "source": "루리웹", "url": u} for u, t in items[:12]]


def youtube():
    items = anchors(get("https://kworb.net/youtube/trending/kr.html"),
                    r"https://(?:youtu\.be/|www\.youtube\.com/watch\?v=)[^\"]+")
    return [{"title": t[:90], "url": u} for u, t in items[:12]]


def summary(snap, today):
    lines = []
    cats = snap.get("soopCategories") or []
    if cats:
        lines.append("SOOP 인기 카테고리: " + ", ".join(c["name"] for c in cats[:3]))
    g = []
    if g:
        lines.append("검색 급상승: " + ", ".join(x["title"] for x in g[:3]))
    try:
        games = json.load(open(os.path.join(ROOT, "data", "games.json"), encoding="utf-8"))
        end = (datetime.strptime(today, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
        soon = sorted((x for x in games if today <= x.get("date", "") <= end), key=lambda x: x["date"])
        if soon:
            lines.append("7일 안 출시: " + ", ".join("%s(%s)" % (x["title"], x["date"][5:].replace("-", "/")) for x in soon[:4]))
    except Exception:
        pass
    return "\n".join(lines)


def main():
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    path = os.path.join(ROOT, "data", "snapshots", today[:7] + ".json")
    month = {}
    if os.path.exists(path):
        month = json.load(open(path, encoding="utf-8"))
    snap = month.get(today, {"date": today})
    sources = {"soopCategories": soop_categories, "soopLive": soop_live}
    ok = 0
    for key, fn in sources.items():
        try:
            rows = fn()
            if not rows:
                raise ValueError("빈 결과")
            snap[key] = rows          # 실패한 출처는 이전 값을 그대로 둔다
            ok += 1
            print("OK  ", key, len(rows))
        except Exception as e:
            print("FAIL", key, repr(e))
    if not ok:
        print("모든 출처 실패: 파일을 바꾸지 않습니다")
        sys.exit(1)
    snap["updatedAt"] = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    snap["summary"] = summary(snap, today)
    month[today] = snap
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(month, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
