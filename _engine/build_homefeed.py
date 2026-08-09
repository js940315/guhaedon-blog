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

import html
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
BR = "⠀⠀⠀"                      # 점자 빈칸 3개 — 문단 구분
URL_SLOT = "【여기에 허브 URL 단독 입력 + 엔터 → 이미지 카드】"

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
    body = body.replace("{{URL_CARD}}", URL_SLOT)
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

    # 링크 — 본문에 박히는 건 최하단 텍스트 링크 하나뿐. 중간은 자리만 비워둔다.
    if len(inline) != 1:
        probs.append(f"본문 내 URL {len(inline)}개 — 최하단 텍스트 링크 1개여야 함")
    if inline and inline[0] != d["hub"]:
        probs.append("최하단 링크가 메인허브가 아니다")
    if URL_SLOT not in body:
        probs.append("중간 URL 카드 자리가 없다")

    # 순서 — 카드가 텍스트 링크보다 앞에 있어야 한다
    if URL_SLOT in body and inline:
        if body.find(URL_SLOT) > body.find(inline[0]):
            probs.append("중간 카드가 최하단 텍스트 링크보다 뒤에 있다")

    # 위치 — 맨 위 링크 금지
    first = min([body.find(URL_SLOT)] + ([body.find(inline[0])] if inline else []))
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


def render_html(d: dict, body: str, chars: int, probs: list[str]) -> str:
    n_img = len(d["images"])
    imgs = "".join(
        f"<tr><td><b>{html.escape(i['file'])}</b></td><td>{html.escape(i['kind'])}</td>"
        f"<td>{html.escape(i['where'])}</td><td>{html.escape(i['copy'])}</td></tr>"
        for i in d["images"])
    ok = "문제 없음" if not probs else f"문제 {len(probs)}건"
    plist = "".join(f"<li>{html.escape(p)}</li>" for p in probs)
    return f"""<meta charset="utf-8"><title>구해돈 홈판 스탠바이 {d['date']}</title>
<style>
body{{font-family:'Malgun Gothic',sans-serif;max-width:900px;margin:0 auto;padding:24px;background:#f6f7f9;color:#16181d}}
h1{{font-size:20px;margin:0 0 4px}} h2{{font-size:16px;margin:26px 0 10px}}
.meta{{color:#5b6472;font-size:13px;margin-bottom:16px}}
.warn{{background:#fff8e6;border:1px solid #f0d98a;border-radius:10px;padding:12px 14px;font-size:13px;line-height:1.8;margin-bottom:16px}}
.bad{{background:#ffecec;border:1px solid #f0a8a8;border-radius:10px;padding:12px 14px;font-size:13px;margin-bottom:16px}}
button{{border:0;background:#03c75a;color:#fff;padding:10px 20px;border-radius:6px;cursor:pointer;font-size:14px}}
button.sm{{padding:6px 14px;font-size:13px;background:#2b6cb0}}
.bar{{display:flex;gap:8px;margin-bottom:10px}}
pre{{white-space:pre-wrap;word-break:break-all;background:#fff;border:1px solid #e3e6ea;border-radius:10px;padding:16px;margin:0;font-family:inherit;font-size:14px;line-height:1.9}}
mark{{background:#ffe9a8;padding:1px 3px;border-radius:3px}}
mark.u{{background:#cfe4ff}} mark.t{{background:#d8f5d8}}
table{{width:100%;border-collapse:collapse;background:#fff;font-size:13px;border:1px solid #e3e6ea}}
th,td{{border-bottom:1px solid #eef1f5;padding:9px 12px;text-align:left}} th{{background:#eef1f5}}
</style>
<h1>구해돈 · 네이버 홈판 스탠바이</h1>
<div class="meta">{d['date']} · {html.escape(d['topic'])} · 본문 {chars:,}자 · 사진 {n_img}장 · 검증 {ok}</div>
{f'<div class="bad"><b>검증 실패</b><ul>{plist}</ul></div>' if probs else ''}
<div class="warn">
<b>붙여넣는 순서</b><br>
1. 제목 복사 → 제목칸<br>
2. <b>본문 전체 복사</b> → 본문칸 (해시태그까지 한 번에)<br>
3. 노란 <mark>【N번 사진】</mark> 자리를 지우고 사진 업로드<br>
4. 파란 <mark class="u">【여기에 허브 URL…】</mark> 자리를 지우고
   <b>URL만 단독으로 붙여넣고 엔터</b> → 이미지 카드가 뜬다<br>
5. 초록 <mark class="t">👉 …</mark> 최하단 링크는 <b>이미 본문에 들어있다</b>. 건드리지 않는다<br>
<br>
<b>왜 위쪽엔 링크가 없나</b> — 맨 위에 걸면 읽기도 전에 나가서 체류시간이 무너진다.
중간(카드)과 최하단(텍스트) 두 곳만 노린다.
</div>
<h2>제목</h2>
<div class="bar"><button onclick="cp(this,'t')">제목 복사</button></div>
<pre id="t">{html.escape(d['title'])}</pre>
<h2>본문 (해시태그 포함 · 한 번에 복사)</h2>
<div class="bar"><button onclick="cp(this,'b')">본문 전체 복사</button>
<button class="sm" onclick="cp(this,'u')">허브 URL 복사</button></div>
<pre id="b">{html.escape(body)}</pre>
<div style="display:none" id="u">{html.escape(d['hub'])}</div>
<h2>사진 {n_img}장</h2>
<table><tr><th>파일</th><th>종류</th><th>들어가는 자리</th><th>카피</th></tr>{imgs}</table>
<script>
const b=document.getElementById('b');
b.innerHTML=b.innerHTML
 .replace(/【[^】]*번 사진】/g,m=>'<mark>'+m+'</mark>')
 .replace(/【여기에[^】]*】/g,m=>'<mark class="u">'+m+'</mark>')
 .replace(/(👉[^\\n]*\\n[^\\n]*savemoney[^\\n]*)/g,m=>'<mark class="t">'+m+'</mark>');
function cp(btn,id){{
 navigator.clipboard.writeText(document.getElementById(id).innerText).then(()=>{{
  const o=btn.textContent;btn.textContent='복사됨';
  setTimeout(()=>btn.textContent=o,1500);}});
}}
</script>"""


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
    (out / "네이버_스탠바이_홈판.html").write_text(
        render_html(d, body, chars, probs), encoding="utf-8")

    card_at = body.find(URL_SLOT) / len(body) * 100
    link = re.findall(r"https?://\S+", body)
    text_at = body.find(link[0]) / len(body) * 100 if link else 0
    print(f"본문 {chars:,}자 · 사진 {len(d['images'])}장 · 태그 {TAGS_PER_POST}개")
    print(f"중간 이미지 카드  {card_at:4.0f}% 지점")
    print(f"최하단 텍스트 링크 {text_at:4.0f}% 지점")
    print("문제 " + (f"{len(probs)}건" if probs else "0건"))
    for p in probs:
        print("  -", p)
    print(f"\n→ {out}")


if __name__ == "__main__":
    main()
