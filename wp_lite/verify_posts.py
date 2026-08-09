# -*- coding: utf-8 -*-
"""
verify_posts.py — 발행 후 자동 검증 (보고 전용, 절대 수정하지 않는다)

왜 필요한가:
  2026-08-08~09 에 글 7개의 CSS가 통째로 죽은 채 이틀간 라이브에 방치됐다.
  발행 전 가드는 있었지만 '발행된 화면이 실제로 맞는지 보는 눈'이 없었다.
  이 스크립트가 그 눈이다.

설계 원칙 3가지:
  1) 절대 수정하지 않는다. 보고만 한다.
  2) [확실]과 [추정]을 반드시 구분해서 출력한다.
  3) 같은 문제가 여러 글에 걸리면 한 줄로 묶는다. 32줄 반복은 보고가 아니라 소음이다.

점검 항목:
  [확실] CSS 파괴   : 렌더링된 <style> 안에 </p><p> 나 <br> 가 끼어들었는가
  [확실] CSS 위험   : 원본 <style> 에 빈 줄이 있는데 wp:html 로 안 감쌌는가
  [확실] 내부링크   : 본문 내 자사 링크가 200 인가
  [확실] 블록 중복  : 관련글 블록이 두 번 이상 들어갔는가
  [확실] 예약 미전환: status=future 인데 예약 시각이 이미 지났는가
  [추정] 모바일 넘침: 고정폭 px 요소가 모바일 가용폭을 넘는가
  [추정] 광고 잘림  : 애드센스가 풀블리드 없이 좁은 본문에 갇혀 있는가
                     (테마 여백을 실제로 측정해서 판단한다. 못 재면 검사를 건너뛴다)

사용:
  python3 verify_posts.py                 # 최근 24시간, 두 사이트
  python3 verify_posts.py --hours 72
  python3 verify_posts.py --site trip --no-links
"""
import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))

NARROW_VIEWPORT = 360          # 가장 흔한 좁은 안드로이드 폭
ADSENSE_MAX_CREATIVE = 336     # 애드센스 반응형이 내보내는 최대 표준 폭
DUP_THRESHOLD = 3              # 같은 문제가 이 수를 넘으면 한 줄로 묶는다

SITES = [("savemoney", ".env.json"), ("trip", ".env.travel.json")]

_link_cache = {}


def load(fn):
    path = os.path.join(HERE, fn)
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None


def make_api(cfg):
    site = cfg["site_url"].rstrip("/")
    auth = base64.b64encode(
        ("%s:%s" % (cfg["username"], cfg["app_password"])).encode()
    ).decode()

    def api(path):
        req = urllib.request.Request(
            site + path,
            headers={"Authorization": "Basic " + auth, "User-Agent": "Mozilla/5.0"},
        )
        return json.load(urllib.request.urlopen(req, timeout=60))

    return site, api


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "ignore")


def link_status(url):
    if url in _link_cache:
        return _link_cache[url]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        code = urllib.request.urlopen(req, timeout=25).status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception:
        code = 0
    _link_cache[url] = code
    return code


# ── 테마 여백 실측 ───────────────────────────────────────────

def measure_content_width(post_url):
    """
    글 페이지의 실제 좌우 여백을 CSS에서 읽어 모바일 본문 가용폭을 계산한다.
    가정하지 않는다. 못 읽으면 None 을 돌려주고 관련 검사를 건너뛴다.
    """
    try:
        html = fetch(post_url)
    except Exception:
        return None, None

    css = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S))
    pad = None
    # 소스 순서대로 훑어 마지막에 적용되는 값을 남긴다 (동일 특이도 기준 근사)
    for m in re.finditer(r"([^{}]*inside-article[^{}]*)\{([^{}]*)\}", css):
        sel, decl = m.group(1), m.group(2)
        # 페이지(page) 전용 규칙만 제외한다.
        # 주의: 단순히 ".page" 로 걸면 ".page-header" 까지 잡혀서 정작 필요한
        #      .separate-containers .inside-article 규칙을 통째로 놓친다.
        if re.search(r"(?:^|[\s,])(?:body)?\.page(?=[\s.,{]|$)", sel):
            continue
        d = re.search(r"padding(?:-left)?\s*:\s*([0-9.]+)px", decl)
        if d:
            pad = float(d.group(1))
    if pad is None:
        return None, None
    return NARROW_VIEWPORT - pad * 2, pad


# ── 글 단위 점검 ─────────────────────────────────────────────

def check_css_broken(raw, rendered, ctx):
    for css in re.findall(r"<style[^>]*>(.*?)</style>", rendered, re.S):
        if "<p>" in css or "</p>" in css or "<br" in css:
            return ("확실", "CSS 파괴", "<style> 안에 문단 태그가 삽입돼 화면에 CSS 코드가 노출됨")
    return None


def check_css_risky(raw, rendered, ctx):
    if "<!-- wp:" in raw:
        return None
    for css in re.findall(r"<style[^>]*>(.*?)</style>", raw, re.S):
        if re.search(r"\n\s*\n", css):
            return ("확실", "CSS 위험",
                    "<style> 에 빈 줄이 있는데 wp:html 로 안 감쌈 — 다음 수정 때 깨진다")
    return None


def check_dup_blocks(raw, rendered, ctx):
    n = raw.count('class="hb-rel"')
    if n > 1:
        return ("확실", "관련글 블록 중복", "%d개 삽입됨 (1개여야 함)" % n)
    return None


def check_dead_links(raw, rendered, ctx):
    if not ctx.get("check_links"):
        return None
    site = ctx["site"]
    urls = set(re.findall(r'href="(%s/[^"#?]+)"' % re.escape(site), rendered))
    dead = [(u, link_status(u)) for u in sorted(urls)]
    dead = [(u, c) for u, c in dead if c != 200]
    if dead:
        return ("확실", "내부링크 깨짐",
                ", ".join("%s(%s)" % (u.replace(site + "/", ""), c or "연결실패")
                          for u, c in dead[:3]))
    return None


def check_mobile_overflow(raw, rendered, ctx):
    w = ctx.get("content_width")
    if not w:
        return None
    body = re.sub(r"<style[^>]*>.*?</style>", "", rendered, flags=re.S)
    over = set()
    for m in re.finditer(r'style="[^"]*?\bwidth:\s*(\d{3,4})px', body):
        if int(m.group(1)) > w:
            over.add(int(m.group(1)))
    for m in re.finditer(r'\swidth="(\d{3,4})"', body):
        if int(m.group(1)) > w:
            over.add(int(m.group(1)))
    if over:
        return ("추정", "모바일 가로 넘침",
                "고정폭 %spx 요소 (가용폭 %dpx)"
                % (sorted(over, reverse=True)[:3], w))
    return None


def check_ad_clipping(raw, rendered, ctx):
    w = ctx.get("content_width")
    if not w or "adsbygoogle" not in raw:
        return None
    if w >= ADSENSE_MAX_CREATIVE:
        return None
    if "50vw" in raw or "100vw" in raw:
        return None  # 풀블리드 처리됨
    return ("추정", "광고 잘림 위험",
            "본문 가용폭 %dpx < 애드센스 최대 크리에이티브 %dpx, 풀블리드 처리 없음"
            % (w, ADSENSE_MAX_CREATIVE))


CHECKS = [check_css_broken, check_css_risky, check_dup_blocks,
          check_dead_links, check_mobile_overflow, check_ad_clipping]


# ── 사이트 검사 ──────────────────────────────────────────────

def verify_site(name, cfg, hours, check_links=True):
    site, api = make_api(cfg)
    since = (datetime.utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")
    findings = defaultdict(list)   # (등급, 항목) -> [(slug, 상세)]
    notes = []

    try:
        posts = api(
            "/wp-json/wp/v2/posts?per_page=40&context=edit&orderby=modified"
            "&modified_after=%s&_fields=id,slug,link,content" % since
        )
    except Exception as e:
        return 0, {("확실", "API 접근 실패"): [(name, str(e))]}, []

    if not posts:
        return 0, findings, ["최근 %d시간 내 신규·수정 글 없음" % hours]

    width, pad = measure_content_width(posts[0]["link"])
    if width:
        notes.append("본문 가용폭 실측 %dpx (좌우 여백 %gpx, %dpx 화면 기준)"
                     % (width, pad, NARROW_VIEWPORT))
    else:
        notes.append("본문 여백 측정 실패 — 광고/넘침 검사 건너뜀")

    ctx = {"site": site, "check_links": check_links, "content_width": width}

    for p in posts:
        for fn in CHECKS:
            r = fn(p["content"]["raw"], p["content"]["rendered"], ctx)
            if r:
                grade, label, detail = r
                findings[(grade, label)].append((p["slug"][:44], detail))

    # 예약 시각이 지났는데 아직 future 인 글
    try:
        now = datetime.utcnow()
        for f in api("/wp-json/wp/v2/posts?status=future&per_page=30"
                     "&_fields=slug,date_gmt"):
            if datetime.fromisoformat(f["date_gmt"]) < now:
                findings[("확실", "예약 미전환")].append(
                    (f["slug"][:44], f["date_gmt"]))
    except Exception:
        pass

    return len(posts), findings, notes


def render(name, checked, findings, notes):
    out = []
    for note in notes:
        out.append("    · %s" % note)
    for (grade, label), items in sorted(findings.items()):
        if len(items) > DUP_THRESHOLD:
            # 사이트 전반 이슈 — 한 줄로 묶는다
            sample = ", ".join(s for s, _ in items[:3])
            out.append("    [%s] %s — %d건 (사이트 전반). 예: %s 외 %d건"
                       % (grade, label, len(items), sample, len(items) - 3))
            out.append("           %s" % items[0][1])
        else:
            for slug, detail in items:
                out.append("    [%s] %s — %s : %s" % (grade, label, slug, detail))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--site", default="all")
    ap.add_argument("--no-links", action="store_true")
    args = ap.parse_args()

    summary, body, total_problems, certain = [], [], 0, 0

    for name, fn in SITES:
        if args.site not in ("all", name):
            continue
        cfg = load(fn)
        if not cfg:
            continue
        checked, findings, notes = verify_site(
            name, cfg, args.hours, check_links=not args.no_links)
        n = sum(len(v) for v in findings.values())
        certain += sum(len(v) for (g, _), v in findings.items() if g == "확실")
        total_problems += n
        summary.append("%s %d건(문제 %d)" % (name, checked, n))
        body.append("  [%s]" % name)
        body += render(name, checked, findings, notes)

    print("검증 %s / 최근 %d시간 / 확실 %d건 · 추정 %d건"
          % (" · ".join(summary) or "대상 없음", args.hours,
             certain, total_problems - certain))
    if body:
        print()
        print("\n".join(body))
    if total_problems:
        print("\n※ 보고만 했습니다. 수정한 것은 없습니다.")
    return 1 if certain else 0


if __name__ == "__main__":
    sys.exit(main())
