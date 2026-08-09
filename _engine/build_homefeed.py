# -*- coding: utf-8 -*-
"""홈판 트랙 빌더 — 네이버 복붙용 스탠바이를 만든다.

검색 트랙(build_spokes.py)과 규격이 다르다.
    검색 트랙 : 400~900자 · 세부키워드 10건 · 이미지 없음
    홈판 트랙 : 1,400~1,600자 · 관점 포함 · 이미지 5장

⭐ 링크 배치가 이 파일의 핵심이다 (2026-08-10 확정, 임의 변경 금지)

    맨 위(썸네일)   URL 없음
        └ 여기에 링크를 걸면 읽기도 전에 나간다. 체류시간이 무너지고
          네이버가 "외부 유출 목적 글"로 볼 여지도 커진다.
    본문 중간       {{URL_CARD}}  → URL 단독 입력 + 엔터 = OG 이미지 카드
        └ 답을 다 준 직후. 카드는 크고 눈에 띄어 클릭을 만든다.
    최하단          {{URL_TEXT}}  → 👉 문구 + URL 인라인 = 텍스트 링크
        └ 끝까지 읽은 사람에게 주는 마지막 기회. 조용한 방식.

    ※ 카드가 뜨려면 URL이 **단독 줄에 입력되고 엔터**여야 한다(실측).
      본문과 같이 붙여넣으면 밋밋한 텍스트 링크가 된다. 그래서 중간 것만
      자리를 비워두고, 최하단 것은 본문에 그대로 박아 한 번에 복사되게 한다.

사용
    python _engine/build_homefeed.py _engine/homefeed_0810.json
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
BR = "⠀⠀⠀"                      # 점자 빈칸 3개 — 문단 구분
# 예전에는 여기에 마커를 넣고 사람이 URL 을 직접 입력하게 했다. 그런데 복붙할 때
# 마커를 지우고 주소를 다시 찾아 넣는 게 번거롭다는 피드백이 있었다(2026-08-10).
# 이제 **실제 주소를 그대로 박는다.** 붙여넣으면 그 자리에 텍스트 링크가 생기고,
# 카드로 바꾸고 싶으면 그 줄만 잘라내 다시 입력하고 엔터를 치면 된다.

# 분량·장수는 데이터에서 읽는다. 아직 실측으로 확정된 값이 아니라 트랙마다 다르게 간다.
#   economy-blog 홈판 스펙은 1,400~1,600자지만 그건 뉴스 소재 · 하루 소수 발행 기준이다.
#   구해돈은 같은 소재로 10건을 뿌리므로 길수록 유사문서 표면적이 커진다.
#   게다가 링크를 26% 지점에 두는 설계와 긴 본문은 서로 싸운다.
#   → 기본을 1,000~1,300 으로 낮춰 잡고, 발행 결과를 보고 조정한다.
DEFAULT_CHARS = (1000, 1300)
TAGS_PER_POST = 8
MAX_SENT = 60                                  # 한 문장 60자

MARKER_RE = re.compile(r"【\s*\d+\s*번\s*사진\s*】")
SKIP_PREFIX = ("http", "👉", "💡", "📌", "📝", "※", "#", "【", "⠀")


def build_body(d: dict) -> str:
    """플레이스홀더를 실제 마커·링크로 바꾼다."""
    body = d["body"]
    for i in range(1, len(d["images"]) + 1):
        body = body.replace(f"{{{{IMG{i}}}}}", f"【{i}번 사진】")
    body = body.replace("{{URL_CARD}}", d["hub"])
    body = body.replace("{{URL_TEXT}}", f"{d['cta_text']}\n{d['hub']}")
    body = body.replace("{{BR}}", BR)
    return body


def validate(body: str, d: dict) -> list[str]:
    probs: list[str] = []
    lo, hi = d.get("chars_range", DEFAULT_CHARS)
    n_img = len(d["images"])

    tags = [t for t in body.split() if t.startswith("#")]
    inline = re.findall(r"https?://\S+", body)
    markers = MARKER_RE.findall(body)

    # 자수 — URL·마커·해시태그를 뺀 실제 읽는 분량만 센다
    txt = re.sub(r"https?://\S+", "", body)
    txt = re.sub(r"【[^】]*】", "", txt)
    txt = re.sub(r"#\S+", "", txt)
    n = len(re.sub(r"\s", "", txt))
    if not (lo <= n <= hi):
        probs.append(f"본문 {n}자 — 규격 {lo:,}~{hi:,}자 벗어남")

    # 링크 — 중간(카드 자리)과 최하단(텍스트) 두 곳. 둘 다 같은 메인허브다.
    if len(inline) != 2:
        probs.append(f"본문 내 URL {len(inline)}개 — 중간·최하단 2개여야 함")
    if inline and set(inline) != {d["hub"]}:
        probs.append(f"링크가 {len(set(inline))}종 — 메인허브 하나로만 보내야 한다")

    # 위치 — 맨 위 링크 금지
    if inline:
        first = body.find(inline[0])
        if first < len(body) * 0.25:
            probs.append(f"첫 링크가 글 앞 {first/len(body)*100:.0f}% 지점 — 25% 이후여야 함")

    if len(markers) != n_img:
        probs.append(f"사진 마커 {len(markers)}개 — {n_img}개여야 함")
    if body.find("【1번 사진】") > len(body) * 0.1:
        probs.append("1번 사진(대표 썸네일)이 맨 위가 아니다")
    if len(tags) != TAGS_PER_POST:
        probs.append(f"해시태그 {len(tags)}개 — {TAGS_PER_POST}개 규칙")

    for bad in ("**", "##", "- ", "`"):
        if bad in body:
            probs.append(f"마크다운 기호 '{bad}' 발견 — 네이버는 해석하지 않는다")
    if "댓글" in body:
        probs.append("'댓글' 단어 발견 — 금지")

    for ln in body.split("\n"):
        s = ln.strip()
        if s and not s.startswith(SKIP_PREFIX) and len(s) > MAX_SENT:
            probs.append(f"{MAX_SENT}자 초과: {s[:26]}…")

    return probs



def main() -> None:
    src = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                       else "_engine/homefeed_0810.json")
    d = json.loads(src.read_text(encoding="utf-8"))

    body = build_body(d)
    probs = validate(body, d)
    txt = re.sub(r"#\S+", "", re.sub(r"【[^】]*】", "",
                                     re.sub(r"https?://\S+", "", body)))
    chars = len(re.sub(r"\s", "", txt))

    # out_name 을 주면 그 이름으로 나간다. 하루에 홈판 글이 둘 이상일 때 폴더가 겹치지 않게.
    out = REPO / "output" / (d.get("out_name") or f"{d['date']}_홈판")
    out.mkdir(parents=True, exist_ok=True)
    (out / "0번 본문.txt").write_text(body, encoding="utf-8")

    link = re.findall(r"https?://\S+", body)
    card_at = body.find(link[0]) / len(body) * 100 if link else 0
    text_at = body.rfind(link[-1]) / len(body) * 100 if link else 0
    print(f"본문 {chars:,}자 · 사진 {len(d['images'])}장 · 태그 {TAGS_PER_POST}개")
    print(f"중간 링크(카드 자리) {card_at:4.0f}% 지점")
    print(f"최하단 텍스트 링크  {text_at:4.0f}% 지점")
    print("문제 " + (f"{len(probs)}건" if probs else "0건"))
    for p in probs:
        print("  -", p)
    print(f"\n→ {out}")


if __name__ == "__main__":
    main()
