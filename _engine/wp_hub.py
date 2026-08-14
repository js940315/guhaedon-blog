# -*- coding: utf-8 -*-
"""워드프레스 허브 연동 — savemoney119.com 의 새 발행글을 읽어 스포크 뼈대를 만든다.

## 왜 필요한가 (2026-08-13)

지금까지 "오늘 어느 허브글로 스포크를 뽑을지"를 사람이 손으로 정했다.
그러다 보니 허브가 매일 나오는데도 스포크는 0809 이후 멈춰 있었다.
게다가 로컬 `_report_*.json` 만 보고 "허브가 멈췄다"고 잘못 판단한 적도 있다
— 실제 사이트는 계속 발행 중이었다. **사이트를 직접 봐야 한다.**

## 어떻게

워드프레스 REST API 는 공개돼 있어 인증 없이 읽힌다.
    https://savemoney119.com/wp-json/wp/v2/posts

  --list            최근 허브글을 본다
  --brief <slug>    그 글로 스포크 10건 뼈대(hubbrief_MMDD.json)를 만든다

뼈대에는 허브 주소·제목·본문 소제목과 **이미 쓴 세부키워드 전체**가 들어간다.
제목 10개를 정하는 건 사람(또는 루틴 에이전트)의 몫이다. 검색 의도를 읽어야
하는 일이라 기계가 대신하면 뻔한 제목만 나온다(인수인계서 2-3절).
"""

import argparse
import html as html_mod
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import keyword_ledger

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://savemoney119.com"
UA = {"User-Agent": "Mozilla/5.0 (guhaedon-spoke-builder)"}


def _get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))


def _clean(s):
    """워드프레스가 돌려주는 HTML 조각을 평문으로.

    ⚠️ 태그만 지우면 안 된다. 허브 글은 본문 맨 앞에 <style> 블록이 통째로
    들어 있어서, 태그만 벗기면 CSS 가 본문인 것처럼 딸려온다(2026-08-14 실측).
    style·script 는 내용까지 통째로 걷어낸다.
    """
    s = s or ""
    s = re.sub(r"<(style|script)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html_mod.unescape(s)
    return re.sub(r"[ \t]{2,}", " ", s).strip()


def fetch_posts(n=10):
    url = (f"{SITE}/wp-json/wp/v2/posts?per_page={n}"
           "&_fields=id,date,slug,link,title,excerpt")
    return _get(url)


def fetch_one(ident):
    """slug 또는 글 번호로 한 건을 본문까지 가져온다."""
    if str(ident).isdigit():
        url = f"{SITE}/wp-json/wp/v2/posts/{ident}?_fields=id,date,slug,link,title,content"
        return _get(url)
    url = (f"{SITE}/wp-json/wp/v2/posts?slug={ident}"
           "&_fields=id,date,slug,link,title,content")
    got = _get(url)
    if not got:
        raise SystemExit(f"[중단] slug '{ident}' 로 찾은 글이 없습니다.")
    return got[0]


def cmd_list(n):
    posts = fetch_posts(n)
    if not posts:
        print("최근 글이 없습니다.")
        return
    print(f"{SITE} 최근 {len(posts)}건")
    print("=" * 72)
    for p in posts:
        print(f"  [{p['id']:>5}] {p['date'][5:16].replace('T', ' ')}  {_clean(p['title']['rendered'])}")
        print(f"          {p['slug']}")


def cmd_brief(ident, date, n_spokes):
    p = fetch_one(ident)
    body = _clean(p["content"]["rendered"])
    heads = re.findall(r"<h[23][^>]*>(.*?)</h[23]>", p["content"]["rendered"], re.S)
    heads = [_clean(h) for h in heads][:20]

    used = keyword_ledger.all_keywords(REPO)
    out = {
        "date": date,
        "hub": p["link"],
        "hub_id": p["id"],
        "hub_title": _clean(p["title"]["rendered"]),
        "hub_slug": p["slug"],
        "hub_headings": heads,
        "hub_text_head": body[:1200],
        "_todo": [
            "세부키워드 10개를 정한다. 공식은 [한정어]+[핵심키워드]+[행동어].",
            "한정어 4종 중 하나를 반드시 붙인다 — 지역/대상/시점/상황.",
            "제목은 지식iN·연관검색어에서 가져온다. 지어내지 않는다.",
            "아래 seen_keywords 와 겹치는 각도는 쓰지 않는다.",
            "정한 뒤 search_<MMDD>_sN.json 10개로 옮기고 이 파일은 지운다.",
        ],
        "seen_keywords": used,
        "spokes": [{"seq": i, "title": "", "angle": ""} for i in range(1, n_spokes + 1)],
    }

    dst = os.path.join(REPO, "_engine", f"hubbrief_{date}.json")
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print(f"허브: {out['hub_title']}")
    print(f"      {out['hub']}")
    print(f"소제목 {len(heads)}개 · 이미 쓴 키워드 {len(used)}건")
    print(f"→ _engine/hubbrief_{date}.json")


def main():
    ap = argparse.ArgumentParser(description="워드프레스 허브 연동")
    ap.add_argument("--list", type=int, nargs="?", const=10, metavar="N",
                    help="최근 허브글 N건 보기 (기본 10)")
    ap.add_argument("--brief", metavar="SLUG|ID",
                    help="그 글로 스포크 뼈대 만들기")
    ap.add_argument("--date", help="스포크 날짜 MMDD (--brief 와 같이)")
    ap.add_argument("--count", type=int, default=10, help="스포크 개수 (기본 10)")
    a = ap.parse_args()

    if a.list is not None:
        cmd_list(a.list)
    elif a.brief:
        if not a.date:
            raise SystemExit("[중단] --brief 는 --date MMDD 와 같이 씁니다.")
        cmd_brief(a.brief, a.date, a.count)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
