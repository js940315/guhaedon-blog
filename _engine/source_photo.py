# -*- coding: utf-8 -*-
"""제목에서 뽑은 핵심 명사로 배경 사진을 구해온다 — 3단계 폴백.

왜 이 파일이 필요한가
---------------------
홈판 썸네일은 "카피와 배경이 같은 얘기를 해야" 한다.
따릉이 글에 엉뚱한 건물 사진을 깔면 그 순간 아마추어가 된다.
그런데 스톡 사이트에는 '따릉이' 같은 실존 브랜드가 없다.
그래서 소스를 종류별로 나눠서 순서대로 내려간다.

  1단계  고유명사(따릉이·서울시설공단·국민연금)  -> Wikimedia Commons
  2단계  일반명사(자전거·쿠폰·문자·고지서)        -> Pexels / Unsplash 스톡
  3단계  둘 다 0건                                -> 어두운 단색 폴백(dim 0.6+)

⚠️ 실측 (2026-08-10)
  한글 고유명사는 반드시 **한글 그대로** 검색해야 한다. 영문 음차는 거의 0건이다.
      '따릉이'                -> 6건
      'Ttareungi'             -> 0건
      'Seoul Bike Ttareungi'  -> 0건
  영문 검색어는 일반명사 단계에서만 의미가 있다.

사용
----
    python _engine/source_photo.py 따릉이 --general 자전거 대여소 --slug ttareungi
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import sys

# 엔진은 economy-blog 것을 그대로 재사용한다 (홈판 복제가이드 9절: 코드 100% 재사용).
ECON_ENGINE = os.getenv(
    "ECON_ENGINE",
    r"C:\Users\you64\OneDrive\문서\GitHub\경제비버\_engine",
)
sys.path.insert(0, ECON_ENGINE)

import image_sourcing as isrc  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent
PHOTO_DIR = REPO / "assets" / "photos"
INDEX = PHOTO_DIR / "index.json"

# 재게시 가능한 라이선스만 채택한다. 뉴스 보도사진 무단 전재는 금지.
LICENSE_OK = ("public domain", "cc0", "cc by", "cc by-sa", "kogl")


def license_ok(credit: str) -> bool:
    c = (credit or "").lower()
    return any(k in c for k in LICENSE_OK)


def _load_index() -> dict:
    if not INDEX.exists():
        return {}
    try:
        return json.loads(INDEX.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}          # 손상되면 새로 시작한다 (기록용이라 복구 불필요)


def _save_index(data: dict) -> None:
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    tmp = INDEX.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, INDEX)   # 원자적 쓰기 — OneDrive가 파일을 NUL로 만든 사례가 있다


def source(proper: str, general: list[str], slug: str, tmp_dir: pathlib.Path,
           limit: int = 6) -> list[dict]:
    """3단계 폴백으로 후보를 모은다. 반환은 [{path, credit, tier}, ...]."""
    out: list[dict] = []

    # 1단계 — 고유명사는 한글 그대로 Wikimedia 에 묻는다.
    if proper:
        try:
            for c in isrc.wikimedia_photo_candidates(
                    proper, str(tmp_dir), limit=limit, min_width=1200):
                if isinstance(c, dict) and c.get("path"):
                    out.append({"path": c["path"], "credit": c.get("credit", ""),
                                "tier": "wikimedia", "query": proper})
        except Exception as e:                      # 네트워크·API 변덕은 치명적이지 않다
            print(f"  [1단계 실패] {type(e).__name__}: {e}")
    print(f"  1단계(고유명사 '{proper}') → {len(out)}건")

    # 2단계 — 일반명사는 스톡에서. 1단계가 충분하면 건너뛴다.
    if len(out) < 3:
        for q in general:
            try:
                for c in isrc.stock_photo_candidates(q, str(tmp_dir), keep=3,
                                                     min_side=1200, prefix=f"st_{q}"):
                    if isinstance(c, dict) and c.get("path"):
                        out.append({"path": c["path"], "credit": c.get("credit", ""),
                                    "tier": "stock", "query": q})
            except Exception as e:
                print(f"  [2단계 실패:{q}] {type(e).__name__}: {e}")
        print(f"  2단계(일반명사 {general}) 포함 누적 → {len(out)}건")

    # 3단계 — 아무것도 못 구하면 호출부가 dim 폴백으로 간다.
    if not out:
        print("  3단계 → 후보 0건. 어두운 단색 배경(dim 0.6+)으로 가야 한다.")
    return out


def adopt(cands: list[dict], slug: str) -> list[str]:
    """라이선스가 통과한 것만 assets/photos 로 옮기고 index.json 에 출처를 남긴다."""
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    idx, saved = _load_index(), []
    for i, c in enumerate(cands):
        if not license_ok(c["credit"]):
            print(f"  [제외] 라이선스 확인 불가 — {c['credit'][:60]}")
            continue
        name = f"{slug}_{len(saved)}.jpg"
        shutil.copy2(c["path"], PHOTO_DIR / name)
        idx[name] = {"credit": c["credit"], "tier": c["tier"], "query": c["query"]}
        saved.append(name)
    _save_index(idx)
    return saved


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("proper", help="고유명사 (한글 그대로. 예: 따릉이)")
    ap.add_argument("--general", nargs="*", default=[], help="일반명사 폴백 검색어")
    ap.add_argument("--slug", required=True, help="저장 파일 접두어 (예: ttareungi)")
    a = ap.parse_args()

    tmp = REPO / "_tmp_photos"
    tmp.mkdir(exist_ok=True)
    print(f"소싱: '{a.proper}' (폴백 {a.general})")
    cands = source(a.proper, a.general, a.slug, tmp)
    saved = adopt(cands, a.slug)

    print(f"\n채택 {len(saved)}건 → {PHOTO_DIR}")
    for s in saved:
        print("  ", s)
    print("\n⚠️ 반드시 눈으로 확인하고 나서 커밋할 것 (.gitignore 가 무시하므로 git add -f).")
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
