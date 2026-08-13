# -*- coding: utf-8 -*-
"""build_spokes.py — 네이버 스포크 10건 '복붙 스탠바이' 빌더

원본 규약: github.com/js940315/economy-blog `_engine/build_posts.py`
  · 네이버는 API 자동 발행을 막는다 → 자동화 범위는 "복붙 직전까지"
  · 엔진(이 파일)과 데이터(spokes_MMDD.json)를 분리한다. 매일 JSON만 갈아끼운다.

사용법 (반드시 저장소 루트에서):
    python _engine/build_spokes.py _engine/spokes_0809.json

산출:
    output/{MMDD}/네이버_스탠바이.html   ← 복사 버튼 달린 단일 파일
    build_report.json                    ← problems 가 빈 배열이어야 정상

빌더가 강제 보정하는 것:
  · 마크다운 기호 제거 (네이버 에디터가 해석 못 해 기호가 그대로 노출된다)
  · 문단 사이 점자 빈칸 U+2800 x3 (네이버 붙여넣기에서 살아남는 유일한 간격)
  · 각 원소 = 문장 하나. 문장 중간 줄바꿈은 넣지 않는다.
"""

import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import keyword_ledger

BRAILLE = "⠀⠀⠀"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 발행 전 자동 점검 기준 (NAVER_SPOKE_STRATEGY.md 3·4절)
MIN_CHARS, MAX_CHARS = 400, 900
LINKS_PER_POST = 2
TAGS_PER_POST = 8
BROAD_TAGS = {"#경제", "#뉴스", "#일상", "#정보", "#맞팔", "#소통"}

MD_PAT = re.compile(r"(\*\*|__|##+\s|`|^\s*[-*]\s)", re.M)


def strip_markdown(s):
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"__(.+?)__", r"\1", s)
    s = re.sub(r"`(.+?)`", r"\1", s)
    # 해시태그(#따릉이)는 건드리면 안 된다. 마크다운 헤딩은 '# ' 처럼 뒤에 공백이 온다.
    s = re.sub(r"^#{1,6}[ \t]+", "", s, flags=re.M)
    s = re.sub(r"^\s*[-*]\s+", "", s, flags=re.M)
    return s


def build_body(p, hub, disclaimer):
    """붙여넣기 3덩어리로 나눠 반환한다 → (본문A, 링크URL, 본문B)

    ■ 왜 3덩어리인가 (2026-08-09 실측)
    네이버는 대량 붙여넣기한 URL을 '파란 밑줄 텍스트 링크'로만 만든다.
    썸네일이 붙은 **링크 카드**가 되려면 URL 을 단독으로 넣고 엔터를 쳐야 한다.
    카드는 이미지가 크게 떠서 클릭률이 훨씬 높으므로, 마지막 링크만 따로 뺀다.

    ■ 링크는 전부 메인허브 하나로만 보낸다 (2026-08-09 설계 확정)
    스포크로 직접 보내면 광고 2개만 보고 끝난다.
    허브로 모으면 허브(광고 1) → CTA → 스포크(광고 2) 로 3개를 본다.
    백링크도 허브 한 곳에 뭉쳐야 신생 도메인에서 신호가 선다.
    """
    a = []
    a.append(" ".join(p["intro"]))
    a.append("\n".join(f"{k} : {v}" for k, v in p["table"]))
    a.append(p["sub1"])
    for i in range(0, len(p["body1"]), 2):           # 2문장씩 한 문단
        a.append(" ".join(p["body1"][i:i + 2]))
    lead, push, anchor, _ = p["cta_mid"]
    a.append(f"{lead} {push}")
    a.append(f"👉 {anchor}\n{hub['hub']}")           # 링크 1회차 = 본문 중간(텍스트)
    a.append("📌 이것만은 확인하세요")
    a.append("\n".join(p["warns"]))
    a.extend(p["outro"])
    anchor2 = p["cta_end"][0] if p.get("cta_end") else "전체 내용 보기"
    a.append(f"👉 {anchor2}")                        # 카드 바로 위 안내 문구

    b = [p["question"], disclaimer, " ".join(p["tags"])]

    return ([strip_markdown(x) for x in a],
            hub["hub"],                              # 링크 2회차 = 카드로 삽입
            [strip_markdown(x) for x in b])


def render(p, hub, disclaimer):
    """검증·미리보기용 전체 본문 (실제 붙여넣기는 3덩어리로 나눠서 한다)."""
    a, url, b = build_body(p, hub, disclaimer)
    return f"\n{BRAILLE}\n".join(a + [url] + b)


def check(p, text):
    probs = []
    n = len(re.sub(r"\s", "", text))
    if not (MIN_CHARS <= n <= MAX_CHARS):
        probs.append(f"본문 {n}자 (권장 400~700)")
    if "댓글" in text:
        probs.append("'댓글' 단어 포함 — 네이버 규칙 위반")
    if MD_PAT.search(text):
        probs.append("마크다운 기호 잔존")
    links = re.findall(r"https?://\S+", text)
    if len(links) != LINKS_PER_POST:
        probs.append(f"링크 {len(links)}회 (정확히 {LINKS_PER_POST}회)")
    # 2026-08-09: 링크는 전부 메인허브 하나로 통일한다. 같은 URL 2회는 허용,
    # 3회 이상이 저품질 신호다. 서로 다른 도메인이 섞이면 잡는다.
    if len(set(links)) > 1:
        probs.append(f"링크가 {len(set(links))}종 — 메인허브 하나로만 보내야 한다")
    if links and text.find(links[0]) < len(text) * 0.25:
        probs.append("첫 링크가 글 앞부분 — 외부 유출 목적으로 읽힐 수 있음")
    for u in links:
        if any(s in u for s in ("bit.ly", "me2.do", "vo.la", "han.gl")):
            probs.append(f"단축 URL 사용 {u}")
    if len(p["tags"]) != TAGS_PER_POST:
        probs.append(f"해시태그 {len(p['tags'])}개 ({TAGS_PER_POST}개 규칙)")
    for t in p["tags"]:
        if t in BROAD_TAGS:
            probs.append(f"광범위 태그 {t}")
    return probs


def cross_check(texts):
    """유사문서 회피 — 여러 글에 같은 문장이 반복되면 네이버가 복제글로 본다."""
    from collections import Counter
    c = Counter()
    for t in texts:
        for s in re.split(r"(?<=[.?!])\s+|\n", t):
            s = s.strip()
            if len(s) >= 18 and not s.startswith(("http", "👉", "#", "※")):
                c[s] += 1
    return [f"반복 문장 x{v}: {k[:40]}" for k, v in c.items() if v >= 3]


HTML_TPL = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>네이버 스탠바이 {date} · {topic}</title>
<style>
:root{{--bg:#0f1116;--card:#181b23;--line:#2a2f3a;--txt:#e8eaf0;--mut:#8b93a7;--ac:#3ddc97;}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--txt);font-family:'Malgun Gothic','맑은 고딕',system-ui,sans-serif;line-height:1.7}}
.wrap{{max-width:840px;margin:0 auto;padding:28px 18px 80px}}
h1{{font-size:21px;margin:0 0 6px}}
.sub{{color:var(--mut);font-size:13px;margin-bottom:18px}}
.guide{{background:#131722;border:1px solid var(--line);border-radius:10px;padding:14px 16px;font-size:13px;color:#c3c9d8;margin-bottom:22px}}
.guide b{{color:var(--ac)}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:16px}}
.head{{display:flex;align-items:flex-start;gap:10px;flex-wrap:wrap}}
.no{{background:var(--ac);color:#0f1116;font-weight:700;border-radius:6px;padding:1px 8px;font-size:13px}}
.ty{{color:var(--mut);font-size:12px;border:1px solid var(--line);border-radius:20px;padding:1px 9px}}
.ti{{font-weight:700;font-size:15px;flex:1 1 100%;margin-top:4px}}
.meta{{color:var(--mut);font-size:12px;margin:8px 0 10px}}
.ok{{color:var(--ac)}} .bad{{color:#ff7a7a}}
textarea{{width:100%;height:250px;background:#0d1017;color:#d7dbe6;border:1px solid var(--line);
border-radius:8px;padding:12px;font-family:inherit;font-size:13px;line-height:1.75;resize:vertical;white-space:pre-wrap}}
textarea.t{{height:44px}} textarea.s{{height:110px}}
.step{{margin:14px 0 6px;font-size:12px;font-weight:700;color:var(--ac)}}
.step em{{font-style:normal;font-weight:400;color:var(--mut);margin-left:6px}}
.row{{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}}
button{{background:var(--ac);color:#0f1116;border:0;border-radius:8px;padding:9px 16px;font-weight:700;font-size:13px;cursor:pointer;font-family:inherit}}
button.g{{background:#242a36;color:#c3c9d8}}
</style></head><body><div class="wrap">
<h1>네이버 스탠바이 {n}건 · {topic}</h1>
<div class="sub">{date} 세트 · {stype}형 배분 · 전부 savemoney119 허브로 유입</div>
<div class="guide">
<b>쓰는 법</b> — 글 1개당 복사 버튼 4개를 <b>1 → 2 → 3 → 4 순서</b>로 누릅니다.<br>
문단 간격은 점자 빈칸(U+2800)이라 붙여넣어도 살아남습니다. 지우지 마세요.<br>
<b>표 3줄</b>은 그대로 둬도 되고, 네이버 표 도구로 3행 2열에 옮기면 더 좋습니다.<br>
<b>발행 간격</b> — 한 번에 올리지 말고 하루에 걸쳐 60~90분 간격으로 흩어서.<br>
<b>링크 규칙</b> — 글당 정확히 2회, 둘 다 <b>메인허브 하나로만</b>. 스포크는 허브의 CTA가 보낸다.<br>복사 버튼을 <b>1→2→3→4 순서대로</b> 누릅니다. 3번 URL은 붙여넣고 엔터를 쳐야 카드가 뜬다.
</div>
{cards}
<script>
function cp(i){{
 var t=document.getElementById(i); t.select(); t.setSelectionRange(0,999999);
 navigator.clipboard.writeText(t.value).then(function(){{
   var b=document.getElementById('b_'+i); var o=b.textContent; b.textContent='복사됨';
   setTimeout(function(){{b.textContent=o}},1200);
 }});
}}
</script></div></body></html>"""

CARD_TPL = """<div class="card">
<div class="head"><span class="no">{no}</span><span class="ty">{ty}</span>
<span class="ti">{title}</span></div>
<div class="meta">{chars}자 · 링크 {links}개 · 점검 {verdict}</div>

<div class="step">1</div><textarea class="t" id="t{no}" readonly>{title}</textarea>
<div class="row"><button id="b_t{no}" onclick="cp('t{no}')">제목 복사</button></div>

<div class="step">2</div><textarea id="c{no}" readonly>{bodyA}</textarea>
<div class="row"><button id="b_c{no}" onclick="cp('c{no}')">본문 앞부분 복사</button></div>

<div class="step">3 <em>붙여넣고 엔터 → 썸네일 카드가 뜬다</em></div>
<textarea class="t" id="u{no}" readonly>{url}</textarea>
<div class="row"><button id="b_u{no}" onclick="cp('u{no}')">허브 링크 복사</button></div>

<div class="step">4</div><textarea class="s" id="d{no}" readonly>{bodyB}</textarea>
<div class="row"><button id="b_d{no}" onclick="cp('d{no}')">마무리 복사</button>
<button class="g" onclick="window.open('{url}','_blank')">허브 열기</button></div>
</div>"""


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "_engine/spokes_0809.json"
    d = json.load(open(src, encoding="utf-8"))
    hub, dis, date = d["hub"], d["disclaimer"], d["date"]

    cards, report, texts = [], [], []
    for i, p in enumerate(d["posts"], 1):
        bodyA, url, bodyB = build_body(p, hub, dis)
        t = render(p, hub, dis)
        texts.append(t)
        probs = check(p, t)
        report.append({"no": i, "title": p["title"], "problems": probs})
        links = re.findall(r"https?://\S+", t)
        verdict = ('<span class="ok">통과</span>' if not probs
                   else '<span class="bad">' + " / ".join(probs) + "</span>")
        sep = "\n" + BRAILLE + "\n"
        cards.append(CARD_TPL.format(
            no=i, ty=p["type"], title=html.escape(p["title"]),
            bodyA=html.escape(sep.join(bodyA)), url=url,
            bodyB=html.escape(sep.join(bodyB)),
            chars=len(re.sub(r"\s", "", t)), links=len(links), verdict=verdict))

    xprobs = cross_check(texts)
    outdir = os.path.join(ROOT, "output", date)
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "네이버_스탠바이.html"), "w", encoding="utf-8") as f:
        f.write(HTML_TPL.format(date=date, topic=html.escape(d["topic"]),
                                stype=d.get("set_type", "B"), n=len(d["posts"]),
                                cards="\n".join(cards)))
    with open(os.path.join(ROOT, "build_report.json"), "w", encoding="utf-8") as f:
        json.dump({"date": date, "topic": d["topic"], "posts": report,
                   "cross_problems": xprobs}, f, ensure_ascii=False, indent=1)

    # 세부키워드 장부 — 예전엔 사람이 손으로 적는 구조라 0810·0811 분이 통째로
    # 빠져 중복 방지가 꺼져 있었다(2026-08-13 실측). 이제 빌드가 끝나면 자동으로
    # 쌓이고, 이미 쓴 키워드는 아래에서 경고한다.
    titles = [r["title"] for r in report]
    dups = keyword_ledger.find_duplicates(ROOT, titles)
    keyword_ledger.record(ROOT, date, d["topic"], titles, "spoke",
                          d.get("set_type", ""))

    bad = sum(1 for r in report if r["problems"])
    print(f"생성 {len(report)}건 · 문제 {bad}건 · 교차문제 {len(xprobs)}건")
    if dups:
        print(f"⚠ 이미 쓴 키워드 {len(dups)}건 — 각도를 바꾸거나 교체하세요:")
        for k in dups:
            print(f"     · {k}")
    print(f"→ output/{date}/네이버_스탠바이.html")
    for r in report:
        print(f"  {r['no']:2d}. {'OK ' if not r['problems'] else 'NG '} {r['title']}")
        for x in r["problems"]:
            print(f"        - {x}")
    for x in xprobs:
        print(f"  [교차] {x}")


if __name__ == "__main__":
    main()
