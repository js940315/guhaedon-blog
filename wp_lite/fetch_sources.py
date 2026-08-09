"""
fetch_sources.py
매일 예약 작업 실행 시 가장 먼저 돌리는 스크립트.
설정된 키워드로 구글 뉴스 RSS를 조회해 "최근 24시간 이내" 후보 소재를 뽑아
candidates.json으로 저장한다.

이 스크립트는 글을 쓰지 않는다 — 단순 수집만 한다.
실제 선별/집필/SEO-GEO-AEO 최적화는 Cowork 예약 작업 안에서 Claude가 이 결과를 읽고 직접 수행한다.
"""

import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import requests

CONFIG_PATH = Path(__file__).parent / "sources_config.json"
OUTPUT_PATH = Path(__file__).parent / "candidates.json"


def build_rss_url(keyword: str) -> str:
    q = quote(keyword)
    return f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"


def parse_pubdate(text: str) -> datetime | None:
    try:
        return datetime.strptime(text, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
    except Exception:
        return None


def fetch_keyword(keyword: str, hours: int = 24) -> list[dict]:
    url = build_rss_url(keyword)
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    items = []
    for item in root.findall(".//item"):
        title = item.findtext("title", "")
        link = item.findtext("link", "")
        pub_raw = item.findtext("pubDate", "")
        pub = parse_pubdate(pub_raw)
        if pub and pub < cutoff:
            continue
        items.append({
            "keyword": keyword,
            "title": title,
            "link": link,
            "published": pub_raw,
        })
    return items


def main():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    all_candidates = []
    for category, keywords in config["categories"].items():
        for kw in keywords:
            try:
                found = fetch_keyword(kw, hours=config.get("lookback_hours", 24))
                for f in found:
                    f["category"] = category
                all_candidates.extend(found)
            except Exception as e:
                print(f"[경고] '{kw}' 수집 실패: {e}")

    # 중복 제목 제거
    seen = set()
    deduped = []
    for c in all_candidates:
        if c["title"] in seen:
            continue
        seen.add(c["title"])
        deduped.append(c)

    OUTPUT_PATH.write_text(json.dumps(deduped, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"수집 완료: {len(deduped)}건 → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
