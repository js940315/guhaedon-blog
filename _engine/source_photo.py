# -*- coding: utf-8 -*-
"""키워드 → 배경 사진 소싱. 계절 키워드는 미리, 긴급 키워드는 즉시.

왜 이 파일이 필요한가
---------------------
홈판 썸네일은 "카피와 배경이 같은 얘기를 해야" 한다(홈판 가이드 5절).
따릉이 글에 엉뚱한 건물 사진을 깔면 그 순간 아마추어가 된다.

그런데 소재마다 사진이 있는 곳이 다르다.
  · 따릉이·쿠팡·테무 같은 **브랜드**는 스톡에 없다 → Wikimedia Commons
  · 종합소득세·근로장려금 같은 **제도**는 애초에 찍을 물건이 없다 → 상황 컷을 스톡에서
그래서 `topics.json` 에 키워드별 검색 계획을 적어두고 여기서 그대로 집행한다.

역할이 둘이고 기준이 정반대다 (운영 매뉴얼 3-3절)
  thumb : 120px 로 줄어든다 → 피사체 하나가 화면을 채우는 **클로즈업**
  card  : 화면 폭 전체로 본다 → **전경·상황 컷**이 오히려 낫다
같은 소재라도 검색어를 따로 두는 이유다.

⚠️ 한글 고유명사는 한글 그대로 검색한다 (2026-08-10 실측)
      '따릉이' 6건 / 'Ttareungi' 0건 / 'Seoul Bike Ttareungi' 0건
   영문 검색어는 스톡(일반명사) 단계에서만 의미가 있다.

사용
----
    python _engine/source_photo.py --topic 종합소득세      # 사전에 있는 키워드
    python _engine/source_photo.py --season 5월            # 그 시즌 전부 미리
    python _engine/source_photo.py --all                   # 전부
    python _engine/source_photo.py --adhoc "쿠팡 개인정보 유출" \
           --brand 쿠팡 --thumb "smartphone alert close up" --slug coupang_leak
                                                           # 사전에 없는 긴급 키워드

소싱이 끝나면 `assets/photos/_검수_{slug}.jpg` 몽타주가 생긴다.
**반드시 눈으로 보고** 주제에 안 맞는 컷을 지운 뒤 `git add -f` 한다.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import sys

ECON_ENGINE = os.getenv(
    "ECON_ENGINE",
    r"C:\Users\you64\OneDrive\문서\GitHub\경제비버\_engine",
)
sys.path.insert(0, ECON_ENGINE)

import image_sourcing as isrc          # noqa: E402
from PIL import Image                  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent
PHOTO_DIR = REPO / "assets" / "photos"
INDEX = PHOTO_DIR / "index.json"
TOPICS = pathlib.Path(__file__).resolve().parent / "topics.json"

# 재게시 가능한 라이선스만 채택한다. 뉴스 보도사진 무단 전재는 금지.
LICENSE_OK = ("public domain", "cc0", "cc by", "cc by-sa", "kogl",
              "pexels", "unsplash", "pixabay")

PER_ROLE = 4          # 역할당 목표 장수. 3~5일 순환에 이 정도면 안 겹친다.


def license_ok(credit: str) -> bool:
    return any(k in (credit or "").lower() for k in LICENSE_OK)


def _load(path: pathlib.Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _save_index(data: dict) -> None:
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    tmp = INDEX.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, INDEX)     # 원자적 쓰기 — OneDrive 가 파일을 NUL 로 만든 사례가 있다


def _is_korean(s: str) -> bool:
    return any("\uac00" <= c <= "\ud7a3" for c in s)


def gather(queries: list[str], tmp: pathlib.Path, tag: str,
           verify: list[str] | None = None) -> list[dict]:
    """검색어를 순서대로 시도한다. 브랜드(verify 있음)는 Wikimedia, 나머지는 스톡.

    ⚠️ 오매칭이 흔하다 (2026-08-10 실측)
        '쿠팡'     -> 인도네시아 Kupang 시 문장·해변 사진
        'Temu app' -> 이탈리아 Temù 마을 교회
        'Coupang'  -> 실제 쿠팡 배송백  ✅
        '따릉이'   -> 실제 따릉이       ✅
    브랜드마다 먹히는 표기가 달라서 "한글로만 검색" 같은 단일 규칙은 통하지 않는다.
    그래서 **verify 게이트**를 둔다. 결과의 출처 문자열에 기대 단어가 하나도
    없으면 그 후보는 버리고 다음 검색어로 넘어간다. 이게 없으면 인도네시아
    해변 사진이 쿠팡 글에 그대로 실린다.
    """
    out: list[dict] = []
    for q in queries:
        if len(out) >= PER_ROLE:
            break
        # verify 가 있는 소재는 브랜드다. 한글이든 영문이든 Wikimedia 에서 실물을 찾는다.
        # verify 가 없으면 제도·개념이라 찍을 실물이 없으므로 스톡 상황 컷으로 간다.
        use_wiki = bool(verify) and (_is_korean(q) or q[:1].isupper())
        src = "wikimedia" if use_wiki else "stock"
        try:
            if use_wiki:
                cands = isrc.wikimedia_photo_candidates(
                    q, str(tmp), limit=PER_ROLE * 2, min_width=1200)
            else:
                cands = isrc.stock_photo_candidates(
                    q, str(tmp), keep=PER_ROLE, min_side=1200,
                    prefix=f"{tag}_{abs(hash(q)) % 9999}")
        except Exception as e:
            print(f"    [{src}:{q}] 실패 {type(e).__name__}: {e}")
            continue

        got = dropped = 0
        for c in cands or []:
            if not (isinstance(c, dict) and c.get("path") and os.path.exists(c["path"])):
                continue
            cred = c.get("credit", "")
            if not license_ok(cred):
                dropped += 1
                continue
            # 브랜드 실물은 출처에 브랜드명이 실제로 들어있어야 인정한다.
            if use_wiki and verify and not any(v.lower() in cred.lower() for v in verify):
                dropped += 1
                continue
            out.append({"path": c["path"], "credit": cred, "source": src, "query": q})
            got += 1
            if len(out) >= PER_ROLE:
                break
        note = f" (오매칭·라이선스로 {dropped}건 폐기)" if dropped else ""
        print(f"    [{src}] '{q}' → {got}건{note}")
    return out


def fetch_logo(brand_en: str, slug: str, tmp: pathlib.Path,
               verify: list[str]) -> str | None:
    """공식 로고를 확보한다 — 브랜드 인지도를 만드는 가장 확실한 요소.

    구글 이미지에 뜨는 로고는 대부분 나무위키·언론사가 재가공한 것이라 그대로 못 쓴다.
    그런데 **단순 워드마크는 창작성 기준 미달로 Wikimedia 에 Public domain 으로 올라와 있다.**
    실측(2026-08-10)에서 아래가 전부 PD/CC0 였다:
        Coupang logo.svg · Temu logo.svg · SK Hynix.svg
        Samsung Electronics logo (hangul).svg · Bitcoin logo clean.svg
    긁을 이유가 없다. 여기서 정식으로 받아 `build_thumbnail_svg(logo_path=...)` 에 넘긴다.

    ⚠️ 여기도 오매칭이 심하다. 'Temu logo' 검색에 인도네시아 학교 로고가 섞여 나온다.
       그래서 파일명에 브랜드명이 실제로 들어있는 것만 채택한다.
    """
    try:
        rep = isrc.logo_candidates(brand_en, str(tmp), width=1200, limit=8,
                                   prefix=f"{slug}_logo")
    except Exception as e:
        print(f"    [로고] 실패 {type(e).__name__}: {e}")
        return None

    best = None
    for c in rep or []:
        if not c.get("path"):
            continue
        title, lic = c.get("title", ""), str(c.get("license", ""))
        if not any(v.lower() in title.lower() for v in verify):
            continue                                   # 남의 로고를 걸러낸다
        if not license_ok(lic):
            continue
        # 가로로 긴 워드마크가 썸네일에 얹기 좋다. 큰 것을 고른다.
        if best is None or (c.get("w") or 0) > (best.get("w") or 0):
            best = c

    if not best:
        print("    [로고] 채택 0건 — 로고 없이 간다")
        return None

    dst = PHOTO_DIR / f"{slug}_logo.png"
    shutil.copy2(best["path"], dst)
    idx = _load(INDEX, {})
    idx[dst.name] = {"role": "logo", "credit": f"{best['title']} / {best.get('license')}",
                     "source": "wikimedia", "query": f"{brand_en} logo"}
    _save_index(idx)
    print(f"    [로고] {best['title'][:44]}  {best.get('w')}x{best.get('h')}  {best.get('license')}")
    return str(dst)


def contact_sheet(files: list[pathlib.Path], out_path: pathlib.Path) -> None:
    """육안검수용 몽타주. 아래 줄은 120px 실제 썸네일 크기로 같이 깐다.

    큰 그림만 보면 '괜찮네' 하고 넘어가지만, 120px 로 줄이면 피사체가
    뭉개지는 컷이 바로 드러난다. 그 판정을 눈으로 하라고 두 줄로 만든다.
    """
    if not files:
        return
    big, small, pad = 220, 120, 10
    w = pad + len(files) * (big + pad)
    h = pad + big + pad + small + pad
    sheet = Image.new("RGB", (w, h), (24, 26, 31))
    for i, f in enumerate(files):
        try:
            im = Image.open(f).convert("RGB")
        except OSError:
            continue
        x = pad + i * (big + pad)
        sheet.paste(im.resize((big, big), Image.LANCZOS), (x, pad))
        sheet.paste(im.resize((small, small), Image.LANCZOS),
                    (x + (big - small) // 2, pad + big + pad))
    sheet.save(out_path, "JPEG", quality=90)


def run_topic(name: str, spec: dict, tmp_root: pathlib.Path) -> dict:
    slug = spec["slug"]
    print(f"\n=== {name}  ({spec.get('kind','?')} · {spec.get('season','?')}) ===")
    idx = _load(INDEX, {})
    saved_all: list[pathlib.Path] = []

    for role in ("thumb", "card"):
        queries = list(spec.get(role) or [])
        if spec.get("brand") and spec["brand"] not in queries:
            queries.insert(0, spec["brand"])       # 사건형은 브랜드 실물을 먼저 본다
        if not queries:
            continue
        print(f"  [{role}]")
        tmp = tmp_root / f"{slug}_{role}"
        tmp.mkdir(parents=True, exist_ok=True)
        n = 0
        for c in gather(queries, tmp, f"{slug}_{role}", spec.get("verify")):
            fn = f"{slug}_{role}_{n}.jpg"
            shutil.copy2(c["path"], PHOTO_DIR / fn)
            idx[fn] = {"topic": name, "role": role, "credit": c["credit"],
                       "source": c["source"], "query": c["query"]}
            saved_all.append(PHOTO_DIR / fn)
            n += 1
        print(f"  [{role}] 채택 {n}건")

    _save_index(idx)

    # 브랜드 소재는 로고를 같이 확보한다. 배경 사진이 애매해도 로고 하나로 판정이 된다.
    if spec.get("verify"):
        print("  [로고]")
        fetch_logo(spec.get("logo_query") or spec["verify"][0], slug,
                   tmp_root / f"{slug}_logo", spec["verify"])

    if saved_all:
        sheet = PHOTO_DIR / f"_검수_{slug}.jpg"
        contact_sheet(saved_all, sheet)
        print(f"  검수 몽타주 → {sheet.name}  (아랫줄이 실제 120px 크기)")
    else:
        print("  ⚠️ 0건 — 검색어를 바꾸거나 dim 0.6+ 단색 배경으로 간다")
    return {"topic": name, "saved": len(saved_all)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", help="topics.json 의 키워드 하나")
    ap.add_argument("--season", help="해당 시즌 키워드 전부 (예: 5월, 긴급)")
    ap.add_argument("--all", action="store_true", help="전부 사전 소싱")
    ap.add_argument("--adhoc", help="사전에 없는 긴급 키워드 이름")
    ap.add_argument("--brand", help="adhoc 전용 — 한글 브랜드명")
    ap.add_argument("--thumb", nargs="*", default=[], help="adhoc 전용 — 썸네일 검색어")
    ap.add_argument("--card", nargs="*", default=[], help="adhoc 전용 — 카드 검색어")
    ap.add_argument("--slug", help="adhoc 전용 — 파일 접두어")
    a = ap.parse_args()

    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    tmp_root = REPO / "_tmp_photos"
    tmp_root.mkdir(exist_ok=True)

    if a.adhoc:
        if not a.slug:
            ap.error("--adhoc 에는 --slug 가 필요하다")
        jobs = [(a.adhoc, {"slug": a.slug, "kind": "긴급", "season": "긴급",
                           "brand": a.brand,
                           "thumb": a.thumb or ([a.brand] if a.brand else []),
                           "card": a.card or ([a.brand] if a.brand else [])})]
    else:
        data = _load(TOPICS, {}).get("topics", {})
        if not data:
            ap.error(f"{TOPICS} 를 읽지 못했다")
        if a.topic:
            if a.topic not in data:
                ap.error(f"'{a.topic}' 은 topics.json 에 없다. --adhoc 을 쓰거나 먼저 등록할 것")
            jobs = [(a.topic, data[a.topic])]
        elif a.season:
            jobs = [(k, v) for k, v in data.items() if a.season in (v.get("season") or "")]
            if not jobs:
                ap.error(f"시즌 '{a.season}' 에 해당하는 키워드가 없다")
        elif a.all:
            jobs = list(data.items())
        else:
            ap.error("--topic / --season / --all / --adhoc 중 하나가 필요하다")

    results = [run_topic(n, s, tmp_root) for n, s in jobs]
    shutil.rmtree(tmp_root, ignore_errors=True)

    print("\n" + "=" * 46)
    for r in results:
        mark = "OK " if r["saved"] else "0건"
        print(f"  [{mark}] {r['topic']}  {r['saved']}장")
    print("=" * 46)
    print("\n다음: assets/photos/_검수_*.jpg 를 눈으로 확인한다.")
    print("  · 윗줄 = 원본, 아랫줄 = 실제 홈판 크기(120px)")
    print("  · 120px 에서 피사체가 안 읽히는 컷은 thumb 에서 뺀다")
    print("  · 확정한 것만 git add -f assets/photos")


if __name__ == "__main__":
    main()
