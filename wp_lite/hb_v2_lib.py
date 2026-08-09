# -*- coding: utf-8 -*-
"""
hb_v2_lib.py — savemoney119 본문 안전 발행 유틸 (v2)

핵심 2가지. 이거 안 지키면 CSS가 100% 깨진다.
  1) CSS는 개행 0개 한 줄로 압축한다.
     -> wpautop 이 <style> 안에 </p><p> 와 <br> 를 끼워넣는 걸 원천 차단.
  2) 본문 전체를 <!-- wp:html --> 로 감싼다.
     -> do_blocks() 가 wpautop 필터를 아예 제거한다 (WP 코어 동작).

둘 중 하나만 해도 막히지만, 둘 다 하는 게 정답이다.
"""
import os
import re

CSS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hb-v2.css")

_CACHE = {}


def minify_css(css: str) -> str:
    """개행이 단 하나도 없는 CSS 문자열로 압축한다."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)          # 주석 제거
    css = re.sub(r"\s+", " ", css)                            # 모든 공백류 -> 공백 1개
    css = re.sub(r"\s*([{};,])\s*", r"\1", css)               # 구두점 주변 공백 제거
    css = re.sub(r"([{;])\s*([a-zA-Z-]+)\s*:\s*", r"\1\2:", css)  # 선언부 콜론 공백 제거
    css = css.replace(";}", "}")
    assert "\n" not in css, "압축 실패: 개행이 남아 있으면 wpautop 이 CSS를 깬다"
    return css.strip()


def get_css() -> str:
    if "css" not in _CACHE:
        with open(CSS_PATH, encoding="utf-8") as f:
            _CACHE["css"] = minify_css(f.read())
    return _CACHE["css"]


def strip_old_style(html: str) -> str:
    """기존 <style> 블록을 전부 제거한다."""
    return re.sub(r"<style[^>]*>.*?</style>\s*", "", html, flags=re.S)


def build_related(title: str, links) -> str:
    """
    내부링크 거미줄 블록.
    links = [(url, 앵커텍스트, 보조설명), ...]
    """
    if not links:
        return ""
    out = ['<div class="hb-rel"><b>%s</b>' % title]
    for url, anchor, desc in links:
        d = '<i>%s</i>' % desc if desc else ""
        out.append('<a href="%s">%s%s</a>' % (url, anchor, d))
    out.append("</div>")
    return "".join(out)


def build_related_inline(title: str, links) -> str:
    """
    <style> 없이 인라인 style 속성만으로 만드는 관련글 블록.

    쓰는 곳: 전용 CSS가 없어서 wp:html 로 감쌀 수 없는 일반 글.
    (그런 글은 wpautop 이 문단을 만들어줘야 하므로 wp:html 로 감싸면 본문이 뭉개진다)
    반드시 개행 0개 한 줄로 뽑아야 wpautop 이 손대지 못한다.
    """
    if not links:
        return ""
    box = ("margin:30px 0 6px;border:2px solid #eaf0fb;border-radius:16px;"
           "overflow:hidden;font-family:inherit")
    head = ("display:block;background:#eaf0fb;color:#0e2a5e;font-size:15px;"
            "font-weight:800;padding:12px 17px")
    row = ("display:block;padding:14px 17px;border-top:1px solid #e3e8f0;"
           "font-size:16.5px;font-weight:700;line-height:1.5;"
           "text-decoration:none;color:#0e2a5e;background:#fff")
    sub = ("display:block;font-style:normal;font-size:13.5px;font-weight:500;"
           "color:#5a6472;margin-top:3px")
    out = ['<div style="%s"><b style="%s">%s</b>' % (box, head, title)]
    for i, (url, anchor, desc) in enumerate(links):
        r = row if i else row.replace("border-top:1px solid #e3e8f0;", "")
        d = '<i style="%s">%s</i>' % (sub, desc) if desc else ""
        out.append('<a href="%s" style="%s">%s ›%s</a>' % (url, r, anchor, d))
    out.append("</div>")
    html = "".join(out)
    assert "\n" not in html
    return html


REGION_FILTER = (
    '<div class="hb-filter">'
    '<label class="screen-reader-text" for="hbq">지역 검색</label>'
    '<input id="hbq" type="search" inputmode="search" autocomplete="off" '
    'placeholder="시·군·구 이름을 입력하세요 (예: 통영, 부안)">'
    '<div class="hb-chips">'
    '<button type="button" class="hb-chip" data-f="" aria-pressed="true">전체</button>'
    '<button type="button" class="hb-chip" data-f="확정" aria-pressed="false">확정</button>'
    '<button type="button" class="hb-chip" data-f="추진중" aria-pressed="false">추진중</button>'
    '<button type="button" class="hb-chip" data-f="무산" aria-pressed="false">무산·보류</button>'
    '</div>'
    '<p class="hb-note" id="hbcount" role="status"></p>'
    '</div>'
)

REGION_FILTER_JS = (
    '<script>(function(){'
    'var q=document.getElementById("hbq");if(!q)return;'
    'var list=document.querySelector(".hb .hb-list");if(!list)return;'
    'var items=[].slice.call(list.querySelectorAll(".hb-item"));'
    'var chips=[].slice.call(document.querySelectorAll(".hb-chip"));'
    'var cnt=document.getElementById("hbcount");var state="";'
    'function run(){var t=(q.value||"").trim();var n=0;'
    'items.forEach(function(el){var s=el.textContent||"";'
    'var okT=!t||s.indexOf(t)>-1;var okS=!state||s.indexOf(state)>-1;'
    'var ok=okT&&okS;el.hidden=!ok;if(ok)n++;});'
    'if(cnt)cnt.textContent=(t||state)?(n+"개 지역이 검색되었습니다."):"";}'
    'q.addEventListener("input",run);'
    'chips.forEach(function(c){c.addEventListener("click",function(){'
    'state=c.getAttribute("data-f")||"";'
    'chips.forEach(function(x){x.setAttribute("aria-pressed",String(x===c));});'
    'run();});});'
    '})();</script>'
)


def extract_css(html: str) -> str:
    """글에 원래 들어있던 CSS를 전부 뽑아 한 줄로 압축한다."""
    blocks = re.findall(r"<style[^>]*>(.*?)</style>", html, flags=re.S)
    return " ".join(minify_css(b) for b in blocks if b.strip())


def assemble(body_html: str, related_html: str = "", extra_js: str = "",
             css: str = None) -> str:
    """
    최종 본문을 만든다.
    - <style> 은 한 줄 압축본
    - 전체를 wp:html 블록으로 감싼다
    - css=None 이면 hb-v2 디자인시스템을 쓴다.
      .hb 래퍼가 없는 글(전용 위젯 글 등)은 반드시 원본 CSS를 넘겨야 한다.
    """
    body = strip_old_style(body_html).strip()

    if related_html:
        # 출처 문단 바로 앞에 관련글 블록을 넣는다
        if '<p class="hb-src">' in body:
            body = body.replace('<p class="hb-src">', related_html + '<p class="hb-src">', 1)
        else:
            idx = body.rfind("</div>")
            body = body[:idx] + related_html + body[idx:] if idx > -1 else body + related_html

    style = "<style>%s</style>" % (css if css is not None else get_css())
    inner = style + body + (extra_js or "")
    return "<!-- wp:html -->" + inner + "<!-- /wp:html -->"


def is_wpautop_safe(raw: str) -> bool:
    """발행 직전 자가검증. False면 발행하면 안 된다."""
    if "<!-- wp:html -->" not in raw:
        return False
    for m in re.finditer(r"<style[^>]*>(.*?)</style>", raw, flags=re.S):
        if "\n" in m.group(1):
            return False
    return True
