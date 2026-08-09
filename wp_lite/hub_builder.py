# -*- coding: utf-8 -*-
"""
hub_builder.py — savemoney119 허브앤스포크 '기능형 허브 페이지' 빌더
v2 (2026-08-08) : 모바일 가독성 전면 정리 + 애드센스 수동 광고 슬롯 통합

설계 근거 (벤치마크 event.affluentneighbor.com 분석 결과):
- CTA는 정확히 2개만. 3개 이상이면 선택 마비로 이탈률이 오른다.
- 같은 CTA를 상단/중단/하단 3회 반복한다 (문구·링크 동일).
- H2는 정확히 3개로 제한한다 → ez-toc 목차가 자동 생성되지 않아
  허브가 '랜딩'처럼 깔끔하게 유지된다 (ez-toc 기본 임계값 4개).
- '불확실성 훅'(CHECK 1/2/3)으로 "내 경우엔 다를 수 있다"를 먼저 심는다.

벤치마크와 결정적으로 다른 점 (= 우리가 이기는 지점):
- 벤치마크는 정보를 일부러 안 주는 doorway 구조라 구글 색인 삭제 리스크가 있다.
  우리는 '지역 선택 위젯'이라는 실제 기능을 넣어 페이지 자체가 도구가 되게 한다.

────────────────────────────────────────────────────────────────
🔬 2026-08-08 v3 — 벤치마크 3계층 체인 해부 결과 반영

분석한 실제 체인 (같은 애드센스 계정 ca-pub-2396942856311452, 광고 슬롯 1개 재사용):
  1차 event.affluentneighbor.com (복지24)      광고 1개 · H2 4개 · CTA 2회 · Rank Math SEO 완비
   └→ 2차 good.health-research-life.com (정책24) 광고 3개 · H2 2개 · CTA 1회(맨 아래) · SEO 아예 안 함
       └→ 3차 wellbeinghow.com (웰빙하우)        광고 2개 · H2 2개 · CTA 1회 · 종착 = nhis.or.kr 공식

이 구조에서 실제로 배울 것은 '내용을 비우는 것'이 아니라 아래 4가지다.

① **답을 하나 주고, 새 질문을 하나 심는다** (가장 중요)
   1차: 제도 설명 + 자격표를 다 줌 → "우리 동네 포함인지는 조회로만 확인됩니다"
   2차: 조회 방법 5단계를 스크린샷까지 붙여 다 줌 → "근데 그 지역에 안 살면 소용없습니다"
   3차: 전국 지역표를 다 줌 → "지역이 맞아도 대상자로 선정돼야 받습니다"
   → 정보를 감추는 게 아니라, 준 정보가 **다음 불안을 만들도록 배치**한다.
   → 이 빌더의 `doubt`(새 불확실성 박스)가 그 장치다.

② **CTA 직전에 '브릿지 문장'을 넣는다**
   "나도 모르게 놓치고 있는 12만원! 지금 바로 확인하세요."
   "잠깐! 건강검진 결과가 기준에 맞아도 '이곳'에 살지 않으면 신청이 불가합니다."
   → 버튼만 덩그러니 놓지 않는다. 이 빌더의 `bridge`가 그 장치다.

③ **계층이 깊어질수록 CTA는 줄이고 광고는 늘린다**
   1차는 아직 이탈 가능성이 커서 CTA를 위아래로 여러 번, 광고는 1개만.
   2차부터는 이미 클릭해서 들어온 사람이라 이탈이 적으므로 **다 읽게 만든 뒤**
   맨 아래에서만 넘긴다 → 체류시간과 광고 노출을 먼저 확보한다.
   → `tier` 값이 CTA 반복 횟수와 광고 개수를 자동으로 결정한다.

④ **1차만 SEO를 한다**
   벤치마크의 2차는 meta description조차 없다. 검색 유입용이 아니라 순수
   페이지뷰 부풀리기용이기 때문. 우리는 단일 도메인이라 전 계층 SEO를 하되,
   **검색 진입점은 1차(허브)로 몰아주는 내부링크 설계**로 같은 효과를 낸다.

우리가 따라 하지 않는 것: 여러 도메인에 내용 없는 랜딩을 체인으로 까는 것.
구글이 doorway/PBN으로 판정하면 통째로 색인 삭제된다. 우리는 단일 도메인 안에서
계층을 만들고, 각 계층이 실제로 다른 정보를 담아 그 선을 넘지 않는다.
────────────────────────────────────────────────────────────────
🔴 광고 배치 원칙 (v2 신설 — 반드시 지킬 것)
애드센스 게재위치 정책은 "버튼 등 상호작용 요소 바로 옆/근처에 광고를 두어
오클릭을 유발하는 배치"를 명시적으로 금지한다. 계정 정지 사유다.
→ 그래서 이 빌더는 **CTA 블록 앞뒤로는 절대 광고를 넣지 않는다.**
   대신 CTA로부터 최소 한 개 섹션(카드 3개 + 요약박스, 또는 본문 5문단) 이상
   떨어진 두 지점에만 넣는다:
     · 광고 A : 요약박스 다음 ~ H2① 앞  (상단 CTA로부터 충분히 이격)
     · 광고 B : H2② 본문 끝 ~ H2③ FAQ 앞 (중단 CTA로부터 충분히 이격)
   허브 최상단(히어로 위)에는 광고를 넣지 않는다 — CTA를 첫 화면 밖으로
   밀어내서 전환율을 직접 깎아먹기 때문이다. (일반 정보성 글은 반대로
   최상단 광고를 유지하는 게 맞다 — 그건 '읽으러 온' 페이지라 성격이 다르다.)
────────────────────────────────────────────────────────────────
"""

import html as _html
import json as _json


# ---------------------------------------------------------------- 애드센스
AD_CLIENT = "ca-pub-5017062655370511"
AD_SLOT_INARTICLE = "9489988926"


def ad_slot(slot_id=AD_SLOT_INARTICLE, client=AD_CLIENT, note=""):
    """본문 중간 수동 광고 1개.

    원본 코드 대비 고친 것:
    1) min-height 250px 지정 — 광고가 늦게 뜨면서 본문을 밀어내는
       레이아웃 시프트(CLS)를 막는다. 모바일 코어 웹 바이탈 점수와 직결된다.
    2) 화면에 보이는 '광고' 라벨 추가 — 구글 권장 사항이고, 사용자가 본문과
       광고를 구분하게 해줘서 오클릭 신고 리스크를 낮춘다.
       (기존 '💡 중간 | 수동 | 디스플레이'는 편집자용 메모라 프론트에는
        display:none으로 숨겨져 있었다. 사용자에게 보이는 라벨이 아니다.)
    3) 위아래 여백을 32px로 띄워 CTA·본문과 물리적으로 분리한다.
    """
    memo = f"<!-- {note} -->" if note else ""
    return f"""{memo}
<div class="hb-ad">
  <span class="hb-ad-label">광고</span>
  <ins class="adsbygoogle" style="display:block;min-height:250px"
       data-ad-client="{client}"
       data-ad-slot="{slot_id}"
       data-ad-format="auto"
       data-full-width-responsive="true"></ins>
  <script>(adsbygoogle=window.adsbygoogle||[]).push({{}});</script>
</div>"""


# ---------------------------------------------------------------- 스타일
# hb-v2.css 를 "개행 0개 한 줄"로 압축해서 쓴다.
# 개행이 하나라도 남으면 wpautop 이 <style> 안에 </p><p> 와 <br> 를 끼워넣어
# CSS 가 통째로 죽는다 (2026-08-08~09 실제 사고). 절대 되돌리지 말 것.
import hb_v2_lib as _hb

HUB_CSS = "<style>" + _hb.get_css() + "</style>"


def _esc(t):
    return _html.escape(str(t), quote=True)


# ---------------------------------------------------------------- 헤더 진입로
# 이 사이트(GeneratePress)는 테마 설정에서 '네비게이션 없음'으로 되어 있어
# 워드프레스 메뉴를 primary 위치에 붙여도 화면에 렌더링되지 않는다
# (2026-08-08 실측 확인). 대신 '헤더' 위젯 영역의 block-25가 사실상 사이트
# 전역 메뉴 역할을 하고 있으므로, 그날의 허브 링크를 여기에 꽂아야 한다.
HEADER_WIDGET_ID = "block-25"


def set_header_hub_link(wp_url, wp_id, wp_app_pw, hub_url, hub_label,
                        keep_url="https://open.savemoney119.com/hub/",
                        keep_label="👉 실시간 돈 정보", timeout=40):
    """헤더 위젯을 '오늘의 허브 + 기존 링크' 2버튼 바로 교체한다."""
    import requests
    from requests.auth import HTTPBasicAuth
    content = (
        '<div style="display:flex;gap:7px;flex-wrap:wrap;justify-content:center;'
        'align-items:center;padding:4px 0;">'
        f'<a href="{hub_url}" style="display:inline-block;background:#d92d20;color:#fff;'
        "font-size:16px;font-weight:800;text-decoration:none;padding:11px 17px;"
        f'border-radius:999px;line-height:1.2;">{hub_label}</a>'
        f'<a href="{keep_url}" style="display:inline-block;background:#f2f4f8;color:#173c82;'
        "font-size:15px;font-weight:700;text-decoration:none;padding:11px 16px;"
        f'border-radius:999px;line-height:1.2;">{keep_label}</a>'
        "</div>"
    )
    r = requests.post(
        wp_url.rstrip("/") + f"/wp-json/wp/v2/widgets/{HEADER_WIDGET_ID}",
        json={"id": HEADER_WIDGET_ID, "sidebar": "header", "id_base": "block",
              "instance": {"raw": {"content": content}}},
        auth=HTTPBasicAuth(wp_id, wp_app_pw), timeout=timeout)
    return {"ok": r.ok, "status_code": r.status_code,
            "error": None if r.ok else r.text[:300]}


# ---------------------------------------------------------------- 파츠
def cta_pair(cta1, cta2):
    """CTA 2개 묶음. 페이지 내 3회 반복해서 쓴다. 앞뒤로 광고 금지."""
    return (
        '<div class="hb-ctabox">'
        f'<a class="hb-cta hb-cta-1" href="{cta1["href"]}" title="{_esc(cta1["title"])}">'
        f'{cta1["text"]}<small>{cta1["sub"]}</small></a>'
        f'<a class="hb-cta hb-cta-2" href="{cta2["href"]}" title="{_esc(cta2["title"])}">'
        f'{cta2["text"]}<small>{cta2["sub"]}</small></a>'
        "</div>"
    )


def hero_fact(amount, deadline):
    return (f'<div class="hb-fact"><p class="a">{amount}</p>'
            f'<p class="d">{deadline}</p></div>')


def check_cards(items):
    out = ['<div class="hb-checks">']
    for i, t in enumerate(items, 1):
        out.append(f'<div class="hb-check"><b>CHECK {i}</b><span>{t}</span></div>')
    out.append("</div>")
    return "".join(out)


def summary_box(lead, rows):
    li = "".join(f"<li>{r}</li>" for r in rows)
    return f'<div class="hb-sum"><p>{lead}</p><ul>{li}</ul></div>'


_STATE = {"ok": ("확정", "hb-ok"), "wait": ("추진중", "hb-wait"), "no": ("무산·보류", "hb-no")}


def status_list(items):
    """지자체 현황 목록. 모바일에서 가로 스크롤이 생기는 <table> 대신 카드형 flex.

    items: [{"name","amount","note","state","link"}, ...]
    """
    out = ['<div class="hb-list">']
    for it in items:
        label, cls = _STATE.get(it.get("state", "wait"), _STATE["wait"])
        nm = it["name"]
        if it.get("link"):
            nm = f'<a href="{it["link"]}">{nm}</a>'
        note = f'<div class="m">{it["note"]}</div>' if it.get("note") else ""
        out.append(
            f'<div class="hb-item"><div class="l"><div class="n">{nm}</div>{note}</div>'
            f'<div class="r"><div class="amt">{it.get("amount","")}</div>'
            f'<span class="hb-badge {cls}">{label}</span></div></div>'
        )
    out.append("</div>")
    return "".join(out)


def region_tool(regions, tool_id="hbRegion", label="① 내가 사는 시·도를 고르세요",
                empty_msg="시·도를 선택하면 우리 지역 현황이 바로 나옵니다."):
    """지역 선택 → 해당 시·도의 지자체별 현황을 즉시 표시하는 위젯."""
    data = _json.dumps(regions, ensure_ascii=False)
    opts = "".join(f'<option value="{_esc(k)}">{_esc(k)}</option>' for k in regions)
    return f"""<div class="hb-tool">
<label for="{tool_id}">{label}</label>
<select id="{tool_id}"><option value="">— 시·도 선택 —</option>{opts}</select>
<div class="hb-out" id="{tool_id}Out"><div class="hb-empty">{empty_msg}</div></div>
<p class="hb-note">※ 지자체 발표에 따라 수시로 바뀝니다. 신청 전 반드시 관할 시·군·구 공고를 확인하세요.</p>
</div>
<script>
(function(){{
var D={data};
var S=document.getElementById("{tool_id}"),O=document.getElementById("{tool_id}Out");
var L={{ok:["확정","hb-ok"],wait:["추진중","hb-wait"],no:["무산·보류","hb-no"]}};
if(!S||!O)return;
S.addEventListener("change",function(){{
  var v=S.value,a=D[v];
  if(!v||!a){{O.innerHTML='<div class="hb-empty">{empty_msg}</div>';return;}}
  var h="";
  for(var i=0;i<a.length;i++){{
    var r=a[i],m=L[r.state]||L.wait;
    var nm=r.link?('<a href="'+r.link+'">'+r.name+'</a>'):r.name;
    h+='<div class="hb-row"><i>'+nm+'</i><span>'+(r.amount||"")+
       '<span class="hb-badge '+m[1]+'">'+m[0]+'</span></span></div>';
  }}
  O.innerHTML=h;
}});
}})();
</script>"""


def bridge(text):
    """CTA 직전에 놓는 한 줄. 벤치마크 전환율의 핵심 장치.
    강조하고 싶은 구간은 <em>로 감싸면 빨간색이 된다."""
    return f'<p class="hb-bridge">{text}</p>'


def doubt_box(title, body):
    """'답은 줬는데 아직 이게 남았습니다' — 다음 계층으로 넘기는 새 불확실성.
    벤치마크 2차의 "잠깐! 기준에 맞아도 '이곳'에 살지 않으면 신청 불가"와 같은 역할."""
    return f'<div class="hb-doubt"><b>{title}</b><p>{body}</p></div>'


def point_box(label, text):
    return f'<div class="hb-point"><b>{label}</b><span>{text}</span></div>'


def steps_visual(items):
    """번호 단계. items: [(설명, 이미지URL 또는 ""), ...]"""
    out = ['<div class="hb-steps">']
    for i, (t, img) in enumerate(items, 1):
        pic = f'<img src="{img}" alt="{_esc(t)[:60]}" loading="lazy">' if img else ""
        out.append(f'<div class="hb-step"><div class="h"><b>{i}</b><span>{t}</span></div>{pic}</div>')
    out.append("</div>")
    return "".join(out)


def faq_mini(pairs):
    out = ['<dl class="hb-faq">']
    for q, a in pairs:
        out.append(f"<dt>Q. {q}</dt><dd>{a}</dd>")
    out.append("</dl>")
    return "".join(out)


def faq_ld(pairs):
    data = {
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": q,
                        "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in pairs],
    }
    return ('\n<script type="application/ld+json">'
            + _json.dumps(data, ensure_ascii=False) + "</script>")


# ---------------------------------------------------------------- 조립
# 계층별 배치 정책 (벤치마크 해부 결과를 그대로 수치화한 것)
#   tier 1 (허브)   : 아직 이탈 위험이 큼 → CTA 3회, 광고 1개. 전환 우선.
#   tier 2 (스포크) : 이미 클릭해서 들어온 사람 → 다 읽게 만든 뒤 아래에서만 넘김.
#                     CTA 2회(중·하), 광고 2개. 체류·노출 우선.
#   tier 3 (상세)   : 종착 직전 → CTA 1회(하), 광고 2개.
TIER_POLICY = {
    1: {"cta_top": True,  "cta_mid": True,  "cta_bot": True,  "ads": 1},
    2: {"cta_top": False, "cta_mid": True,  "cta_bot": True,  "ads": 2},
    3: {"cta_top": False, "cta_mid": False, "cta_bot": True,  "ads": 2},
}


def build_hub(cfg, ads=True, tier=None):
    """기능형 페이지 HTML 조립 (허브 = tier 1, 스포크 = tier 2, 상세 = tier 3).

    광고는 CTA 블록과 최소 한 개 섹션 이상 떨어진 지점에만 들어간다.
    tier에 따라 CTA 반복 횟수와 광고 개수가 자동으로 정해진다.

    cfg 선택 키:
      tier   : 1|2|3 (기본 1)
      bridge : CTA 직전 한 줄 (문자열 또는 {"top","mid","bot"} 딕셔너리)
      doubt  : ("제목", "본문") — 마지막 CTA 직전에 넣는 '새 불확실성' 박스
    """
    c = cfg
    t = tier if tier is not None else c.get("tier", 1)
    pol = TIER_POLICY.get(t, TIER_POLICY[1])
    n_ads = pol["ads"] if ads else 0

    cta = cta_pair(c["cta1"], c["cta2"])
    br = c.get("bridge") or {}
    if isinstance(br, str):
        br = {"top": br, "mid": br, "bot": br}

    def _cta(pos):
        """브릿지 문장 + CTA. 브릿지가 없으면 CTA만."""
        out = ""
        if br.get(pos):
            out += bridge(br[pos])
        return out + cta

    P = [HUB_CSS, '<div class="hb">']

    # ── 히어로
    P.append(f'<span class="hb-eyebrow">{c["eyebrow"]}</span>')
    P.append(f'<h1 class="hb-h1">{c["h1"]}</h1>')
    P.append(f'<p class="hb-lead">{c["lead"]}</p>')
    P.append(hero_fact(c["amount"], c["deadline"]))
    if pol["cta_top"]:
        P.append(_cta("top"))
    P.append(check_cards(c["checks"]))
    P.append(summary_box(c["sum_lead"], c["sum_rows"]))

    if n_ads >= 1:
        P.append(ad_slot(note="광고A: 요약박스 다음 — CTA로부터 카드3+박스만큼 이격"))

    # ── H2 ① 기능(도구) / 본론
    P.append(f'<h2>{c["h2_1"]}</h2>')
    P.append(c["body_1"])
    P.append(c.get("tool_html") or region_tool(c["regions"]))
    if pol["cta_mid"]:
        P.append(_cta("mid"))

    # ── H2 ② 설명
    P.append(f'<h2>{c["h2_2"]}</h2>')
    P.append(c["body_2"])

    if n_ads >= 2:
        P.append(ad_slot(note="광고B: 본문 끝 — CTA로부터 본문 5문단만큼 이격"))

    # ── H2 ③ FAQ
    P.append(f'<h2>{c["h2_3"]}</h2>')
    P.append(faq_mini(c["faq"]))

    # ── 새 불확실성 → 마지막 CTA (벤치마크의 핵심 전환 장치)
    if c.get("doubt"):
        P.append(doubt_box(c["doubt"][0], c["doubt"][1]))
    if pol["cta_bot"]:
        P.append(_cta("bot"))

    P.append(f'<div class="hb-warn">{c["warn"]}</div>')
    src = " · ".join(f'<a href="{u}" rel="noopener nofollow">{l}</a>' for l, u in c["sources"])
    P.append(f'<p class="hb-src">참고: {src}</p>')
    P.append("</div>")
    if c.get("related"):
        P.append(_hb.build_related(c.get("related_title", "함께 보면 좋은 글"), c["related"]))
    html = "".join(P) + faq_ld(c["faq"])
    # wp:html 로 감싸야 wpautop 이 CSS/마크업을 건드리지 않는다
    out = "<!-- wp:html -->" + html + "<!-- /wp:html -->"
    assert _hb.is_wpautop_safe(out), "wpautop 안전검증 실패 — 발행 금지"
    return out
