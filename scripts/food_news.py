#!/usr/bin/env python3
"""식품·외식 전문지 기사 목록에서 프랜차이즈 신메뉴와 편의점 신상 기사를 골라 오늘 기록에 저장한다."""
import json, os, re, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

KST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "data", "food.json")
FEEDS = [("식품외식경제", "https://www.foodbank.co.kr/rss/allArticle.xml"),
         ("식품저널", "https://www.foodnews.co.kr/rss/allArticle.xml")]
DAYS = 14
NEW = re.compile(r"신메뉴|신제품|신상|출시|선봬|선보|한정|시즌 ?메뉴|콜라보|컬래버|협업 ?메뉴")
SKIP = re.compile(r"호점|개점|매장 ?오픈|수출|박람회|협약|MOU|\[인사\]|\[동향\]|기부|수상|돌파|실적|매출|채용|상생|가맹")
CVS = re.compile(r"\bCU\b|GS25|세븐일레븐|이마트24|편의점")
BRANDS = """맥도날드 롯데리아 버거킹 KFC 맘스터치 노브랜드버거 프랭크버거 쉐이크쉑 파이브가이즈 써브웨이
BBQ bhc 교촌 굽네 푸라닭 네네치킨 처갓집 60계 자담치킨 호식이 페리카나 멕시카나 노랑통닭 지코바
스타벅스 메가MGC커피 메가커피 컴포즈 이디야 투썸 빽다방 할리스 폴바셋 공차 커피빈 엔제리너스 탐앤탐스 더벤티 매머드
파리바게뜨 뚜레쥬르 던킨 배스킨라빈스 크리스피크림 노티드 설빙 요아정
도미노 피자헛 미스터피자 파파존스 피자알볼로 아웃백 빕스 애슐리 본죽 한솥 홍콩반점 역전우동 새마을식당
명륜진사갈비 엽기떡볶이 신전떡볶이 청년다방 죠스떡볶이 이삭토스트 에그드랍 김가네 고봉민 본도시락 두찜 샤브올데이 쿠우쿠우""".split()
BRAND = re.compile("|".join(re.escape(b) for b in sorted(BRANDS, key=len, reverse=True)), re.I)
KIND = re.compile(r"치킨|버거|피자|커피|카페|베이커리|도넛|떡볶이|프랜차이즈|외식|레스토랑|뷔페|도시락|덮밥|분식|디저트|샌드위치|아이스크림")


def classify(title):
    """('franchise' 또는 'cvs', 브랜드) 를 돌려준다. 해당 없으면 None."""
    strong = "신메뉴" in title   # 신메뉴라고 적힌 기사는 브랜드 목록에 없어도, 상생·매출 같은 단어가 있어도 넣는다
    if not NEW.search(title) or (SKIP.search(title) and not strong):
        return None
    if CVS.search(title):
        return "cvs", CVS.search(title).group(0)
    m = BRAND.search(title)
    if m:
        return "franchise", m.group(0)
    return ("franchise", "") if strong or KIND.search(title) else None


def day(text):
    text = (text or "").strip()
    if re.match(r"\d{4}-\d{2}-\d{2}", text):
        return text[:10]
    try:
        return parsedate_to_datetime(text).astimezone(KST).strftime("%Y-%m-%d")
    except Exception:
        return ""


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


def main():
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    since = (now - timedelta(days=DAYS)).strftime("%Y-%m-%d")
    items = {i["url"]: i for i in (json.load(open(STORE, encoding="utf-8")) if os.path.exists(STORE) else [])}
    for source, url in FEEDS:
        try:
            base = url.split("/rss/")[0]
            found = 0
            for it in ET.fromstring(fetch(url)).iter("item"):
                title = re.sub(r"\s+", " ", it.findtext("title") or "").strip()
                link = (it.findtext("link") or "").strip().replace("http://", "https://")
                if link and not link.startswith("http"):
                    link = base + "/news/" + link.lstrip("/")
                kind = classify(title)
                if not kind or not link:
                    continue
                found += 1
                items.setdefault(link, {"title": title[:110], "url": link, "source": source, "kind": kind[0],
                                        "brand": kind[1], "date": day(it.findtext("pubDate")) or today})
            print("OK  ", source, found)
        except Exception as e:
            print("FAIL", source, repr(e)[:200])
    keep, seen = [], set()
    for i in sorted(items.values(), key=lambda i: i["date"], reverse=True):
        key = re.sub(r"\W", "", i["title"])[:18]   # 같은 보도자료를 두 매체가 실은 경우 하나만
        if i["date"] >= since and key not in seen:
            seen.add(key)
            keep.append(i)
    json.dump(keep, open(STORE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    path = os.path.join(ROOT, "data", "snapshots", today[:7] + ".json")
    month = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    month.setdefault(today, {"date": today})["food"] = {
        "franchise": [i for i in keep if i["kind"] == "franchise"][:20],
        "cvs": [i for i in keep if i["kind"] == "cvs"][:12]}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(month, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
