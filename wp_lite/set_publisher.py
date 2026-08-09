# -*- coding: utf-8 -*-
"""
set_publisher.py — savemoney119 '하루 1세트 거미줄' 발행 엔진 (2026-08-09 v1)

■ 무엇이 바뀌었나 (v6 하루 5개 → v7 하루 1세트)
기존: 관련 없는 글 5~10개를 매일 흩뿌림 → 345개 쌓였는데 검색 유입 0.
변경: 하루에 **한 소재를 3장짜리 거미줄 한 덩어리**로 만든다.

    메인허브 ─┬─ CTA① → 1차 (조회·대상 확인) ─┬─ CTA① → 2차
              │                                  └─ CTA② → 공식 사이트
              └─ CTA② → 2차 (신청·행동)      ─┬─ CTA① → 공식 사이트 A
                                                 └─ CTA② → 공식 사이트 B

네이버 블로그(구해돈) 세부키워드 10개는 전부 **그날 메인허브 한 곳으로만** 보낸다.
진입점을 하나로 모아야 신생 도메인에서 신호가 뭉친다.

■ 링크 배선은 이 모듈이 자동으로 한다
각 페이지 cfg에 CTA href를 직접 쓰지 않는다. `cta1_to` / `cta2_to`에
"t1" | "t2" | "hub" | "official:0" | "official:1" 같은 심볼만 적으면
publish_set()이 실제 URL로 바꿔 끼운다. 슬러그가 바뀌어도 링크가 깨지지 않는다.

■ 계층별 정책은 hub_builder.TIER_POLICY를 그대로 따른다
    메인허브 tier 1 : CTA 3회 + 광고 1개 (전환 우선)
    1차     tier 2 : CTA 2회 + 광고 2개 (체류·노출 우선)
    2차     tier 2 : CTA 2회 + 광고 2개
"""

import json
import os
import sys
from datetime import datetime

import requests
from requests.auth import HTTPBasicAuth

from hub_builder import build_hub, set_header_hub_link
from thumbnail_gen import make_thumbnail, make_og_thumbnail
from wp_publisher import (publish_full_post, upload_media,
                          patch_rank_math_meta_v2, patch_wordpress_post)

PAGE_KEYS = ("hub", "t1", "t2")
SLUG_SUFFIX = {"hub": "", "t1": "-check", "t2": "-apply"}


# ---------------------------------------------------------------- 유틸
def _env(path="/sessions/admiring-dazzling-mayer/mnt/wp_lite/.env.json"):
    e = json.load(open(path, encoding="utf-8"))
    return e["site_url"].rstrip("/"), e["username"], e["app_password"]


def _auth(u, p):
    return HTTPBasicAuth(u, p)


def find_by_slug(site, wp_id, wp_pw, slug):
    """같은 슬러그 글이 있으면 (id, link). 세트는 매일 새로 만들지 않고
    같은 소재를 이어갈 때 덮어쓰는 게 기본이다(누적 색인·백링크 유지)."""
    r = requests.get(site + "/wp-json/wp/v2/posts",
                     params={"slug": slug, "status": "publish,future,draft",
                             "_fields": "id,link"},
                     auth=_auth(wp_id, wp_pw), timeout=40)
    if r.ok and r.json():
        d = r.json()[0]
        return d["id"], d.get("link", "")
    return None, ""


def clear_previous_sticky(site, wp_id, wp_pw, keep_id=None):
    """어제 메인허브의 홈 고정을 해제한다. 안 하면 홈 상단에 계속 쌓인다."""
    r = requests.get(site + "/wp-json/wp/v2/posts",
                     params={"sticky": "true", "per_page": 20, "_fields": "id,title"},
                     auth=_auth(wp_id, wp_pw), timeout=40)
    cleared = []
    if r.ok:
        for p in r.json():
            if keep_id and p["id"] == keep_id:
                continue
            rr = requests.post(site + f"/wp-json/wp/v2/posts/{p['id']}",
                               json={"sticky": False}, auth=_auth(wp_id, wp_pw), timeout=40)
            if rr.ok:
                cleared.append(p["id"])
    return cleared


# ---------------------------------------------------------------- 링크 배선
def _resolve(symbol, urls, officials):
    """'t1' / 't2' / 'hub' / 'official:0' → 실제 URL"""
    if symbol.startswith("official:"):
        idx = int(symbol.split(":", 1)[1])
        return officials[idx][1]
    return urls[symbol]


def wire_ctas(spec, urls):
    """각 페이지 cfg의 cta1/cta2에 실제 href를 채워 넣는다."""
    officials = spec["official"]
    for key in PAGE_KEYS:
        cfg = spec["pages"][key]
        for n in ("1", "2"):
            cta = cfg[f"cta{n}"]
            target = cta.pop("_to", None) or cta.get("href")
            if target and not target.startswith("http"):
                cta["href"] = _resolve(target, urls, officials)
            elif target:
                cta["href"] = target
    return spec


# ---------------------------------------------------------------- 검증
def validate(spec):
    errs = []
    if set(spec["pages"]) != set(PAGE_KEYS):
        errs.append(f"페이지 키가 {PAGE_KEYS}가 아님: {list(spec['pages'])}")
    seen = set()
    for key in PAGE_KEYS:
        c = spec["pages"][key]
        f = c["focus"]
        if f not in c["title"]:
            errs.append(f"[{key}] focus가 제목에 없음: {f} / {c['title']}")
        if f not in c["excerpt"]:
            errs.append(f"[{key}] focus가 excerpt에 없음: {f}")
        if not (110 <= len(c["excerpt"]) <= 180):
            errs.append(f"[{key}] excerpt 길이 {len(c['excerpt'])} (110~180 권장)")
        for h in (c["h2_1"], c["h2_2"], c["h2_3"]):
            if f not in h:
                errs.append(f"[{key}] focus가 H2에 없음: {h}")
        if len(c["faq"]) < 3:
            errs.append(f"[{key}] FAQ {len(c['faq'])}개 (3개 이상)")
        if len(c["thumb_lines"]) > 2:
            errs.append(f"[{key}] 썸네일 제목 3줄 이상")
        for hw in (c.get("thumb_hl") or []):
            if not any(hw in ln for ln in c["thumb_lines"]):
                errs.append(f"[{key}] highlight '{hw}'가 썸네일 제목줄에 없음")
        if key != "hub" and not c.get("doubt"):
            errs.append(f"[{key}] doubt(새 불확실성) 누락 — 다음 단계로 넘길 장치가 없음")
        if not c.get("bridge"):
            errs.append(f"[{key}] bridge(CTA 직전 문장) 누락")
        sl = spec["slug_base"] + SLUG_SUFFIX[key]
        if sl in seen:
            errs.append(f"슬러그 중복 {sl}")
        seen.add(sl)
    if len(spec.get("official", [])) < 1:
        errs.append("공식 사이트가 하나도 없음 — 거미줄 종착점이 필요하다")
    return errs


# ---------------------------------------------------------------- 발행
def publish_set(spec, env_path=None, thumb_dir=None, dry_run=False,
                sticky=True, update_header=True):
    """세트 3장(hub/t1/t2)을 발행한다.

    sticky / update_header (2026-08-10 v8 — 하루 2세트로 늘리면서 추가)
      하루에 A(이슈)·B(롱테일) 두 세트를 발행하면 홈 상단과 헤더 진입로를
      서로 빼앗는다. clear_previous_sticky() 는 keep_id 하나만 남기고
      나머지 고정을 전부 푸는데, B를 그냥 발행하면 **A의 홈 고정이 풀린다.**
      헤더 진입로도 마지막에 발행한 쪽으로 덮인다.

      홈 상단과 헤더는 '지금 화제인 것'이 차지해야 하므로 A만 True 로 둔다.
          publish_set(SET_A)                                  # 고정·헤더 A
          publish_set(SET_B, sticky=False, update_header=False)
    """
    site, wp_id, wp_pw = _env(env_path) if env_path else _env()
    thumb_dir = thumb_dir or f"/tmp/thumb_set_{datetime.now():%Y%m%d}"
    os.makedirs(thumb_dir, exist_ok=True)

    errs = validate(spec)
    if errs:
        print("사전 검증 실패:")
        for e in errs:
            print("  -", e)
        return {"ok": False, "errors": errs}
    print(f"사전 검증 통과 — 소재: {spec['topic']}")

    # 1) 슬러그 → URL 확정 (발행 전에 미리 계산해야 상호 링크가 걸린다)
    slugs = {k: spec["slug_base"] + SLUG_SUFFIX[k] for k in PAGE_KEYS}
    urls = {k: f"{site}/{v}/" for k, v in slugs.items()}
    wire_ctas(spec, urls)

    if dry_run:
        for k in PAGE_KEYS:
            c = spec["pages"][k]
            print(f"  [{k}] {urls[k]}")
            print(f"        CTA1 → {c['cta1']['href']}")
            print(f"        CTA2 → {c['cta2']['href']}")
        return {"ok": True, "dry_run": True, "urls": urls}

    # 2) 발행 (2차 → 1차 → 메인허브 순: 링크 대상이 먼저 존재하도록)
    report = []
    tier_of = {"hub": 1, "t1": 2, "t2": 2}
    for key in ("t2", "t1", "hub"):
        c = spec["pages"][key]
        slug = slugs[key]
        # 2026-08-09 v4: 썸네일은 네이버 링크 카드(og:image) 기준으로 만든다.
        # 카드가 제목·설명을 이미 보여주므로 이미지는 제목을 반복하지 않고
        # "눌러야 하는 이유"만 담당한다. 자세한 근거는 thumbnail_gen 하단 주석.
        # thumb_hook / thumb_cta 가 없으면 기존 필드에서 자동 폴백한다.
        hook = c.get("thumb_hook") or c["thumb_lines"]
        cta_txt = c.get("thumb_cta") or (c.get("cta1") or {}).get("text", "")
        thumb = make_og_thumbnail(os.path.join(thumb_dir, f"thumb_{slug}.jpg"),
                                  eyebrow=c.get("thumb_eyebrow") or c.get("eyebrow", ""),
                                  hook_lines=hook,
                                  cta_text=cta_txt)
        html = build_hub(c, tier=tier_of[key])
        pid, _ = find_by_slug(site, wp_id, wp_pw, slug)

        if pid:  # 덮어쓰기
            up = upload_media(site, wp_id, wp_pw, thumb,
                              alt_text=f"{c['focus']} 안내 이미지", seo_filename=slug)
            body = {"title": c["title"], "content": html,
                    "excerpt": c["excerpt"], "status": "publish"}
            if up.get("ok"):
                body["featured_media"] = up["media_id"]
            pr = patch_wordpress_post(site, wp_id, wp_pw, pid, body)
            rm = patch_rank_math_meta_v2(site, wp_id, wp_pw, pid,
                                         focus_keyword=c["focus"], seo_description=c["excerpt"],
                                         seo_title=c["title"], og_image_url=up.get("media_url", ""),
                                         og_image_id=up.get("media_id"),
                                         og_title=c.get("og_title", ""),
                                         og_description=c.get("og_desc", ""))
            res = {"ok": pr.get("ok"), "post_id": pid, "post_url": urls[key],
                   "rank_math_meta_patch": rm, "mode": "update"}
        else:    # 신규
            res = publish_full_post(
                wp_url=site, wp_id=wp_id, wp_app_pw=wp_pw,
                title=c["title"], content_html=html,
                category_name=c.get("category", "정부지원금"), tag_names=c["tags"],
                thumbnail_path=thumb, thumbnail_alt=f"{c['focus']} 안내 이미지",
                seo_filename=slug, status="publish", slug=slug,
                excerpt=c["excerpt"], focus_keyword=c["focus"], seo_description=c["excerpt"])
            res["mode"] = "create"

            # 🔴 2026-08-10 실측 — 신규 발행에서 og:image 가 사이트 로고로 나갔다.
            #   publish_full_post 안에서도 rank math 를 패치하지만 og_image_url 로
            #   넘어가는 media_url 이 비어 있어 `if og_image_url.strip():` 에서
            #   조용히 건너뛴다. 대표이미지는 정상 설정되는데 og:image 만 폴백된다.
            #   또 신규 경로는 og_title/og_desc 를 아예 넘기지 않아 카드 문구가 SEO 제목
            #   그대로 나간다(v4 규칙 위반).
            #   → 발행된 글에서 featured_media 를 되짚어 URL 을 확보하고 다시 박는다.
            #     덮어쓰기 경로와 동일한 상태로 맞추는 보정이다.
            if res.get("ok") and res.get("post_id"):
                og_url = ""
                try:
                    fm = requests.get(site + f"/wp-json/wp/v2/posts/{res['post_id']}",
                                      params={"_fields": "featured_media"},
                                      auth=_auth(wp_id, wp_pw), timeout=40).json()
                    mid = fm.get("featured_media")
                    if mid:
                        og_url = requests.get(site + f"/wp-json/wp/v2/media/{mid}",
                                              params={"_fields": "source_url"},
                                              auth=_auth(wp_id, wp_pw), timeout=40
                                              ).json().get("source_url", "")
                except (requests.RequestException, ValueError, KeyError):
                    mid = None
                if og_url or c.get("og_title") or c.get("og_desc"):
                    res["rank_math_meta_patch"] = patch_rank_math_meta_v2(
                        site, wp_id, wp_pw, int(res["post_id"]),
                        og_image_url=og_url, og_image_id=mid,
                        og_title=c.get("og_title", ""),
                        og_description=c.get("og_desc", ""))

        rm = res.get("rank_math_meta_patch")
        rec = {"key": key, "tier": tier_of[key], "slug": slug, "title": c["title"],
               "mode": res.get("mode"), "ok": res.get("ok"), "post_id": res.get("post_id"),
               "url": urls[key], "rank_math": bool(rm and rm.get("ok")),
               "cta1": c["cta1"]["href"], "cta2": c["cta2"]["href"],
               "error": "" if res.get("ok") else json.dumps(res, ensure_ascii=False)[:300]}
        report.append(rec)
        print(("  OK  " if rec["ok"] else "  FAIL"), key, rec["mode"], urls[key], rec["error"])

    # 3) 메인허브를 홈 최상단 고정 + 어제 것 해제
    #    sticky=False 면 건너뛴다 — B(롱테일) 세트가 A(이슈)의 고정을 뺏지 않게.
    hub_rec = next(r for r in report if r["key"] == "hub")
    if sticky and hub_rec["ok"] and hub_rec["post_id"]:
        cleared = clear_previous_sticky(site, wp_id, wp_pw, keep_id=hub_rec["post_id"])
        requests.post(site + f"/wp-json/wp/v2/posts/{hub_rec['post_id']}",
                      json={"sticky": True}, auth=_auth(wp_id, wp_pw), timeout=40)
        print(f"  홈 고정: 새 메인허브 ON / 이전 {len(cleared)}건 해제")
    elif not sticky:
        print("  홈 고정: 건너뜀 (sticky=False)")

    # 4) 헤더 진입로를 오늘 메인허브로 교체 (이 사이트는 테마 네비가 꺼져 있어 필수)
    if update_header:
        hr = set_header_hub_link(site, wp_id, wp_pw, urls["hub"], spec["header_label"])
        print("  헤더 진입로:", "OK" if hr.get("ok") else hr)
    else:
        hr = {"ok": True, "skipped": True}
        print("  헤더 진입로: 건너뜀 (update_header=False)")

    return {"ok": all(r["ok"] for r in report), "topic": spec["topic"],
            "urls": urls, "report": report, "header": hr}


# ---------------------------------------------------------------- 사후 검증
def verify_set(urls, extra_links=()):
    """발행 후 실제로 열어보고 거미줄이 끊기지 않았는지 확인한다."""
    import re
    UA = {"User-Agent": "Mozilla/5.0"}
    out = []
    for k, u in urls.items():
        try:
            h = requests.get(u + "?v=verify", timeout=60, headers=UA).text
        except Exception as e:
            out.append({"page": k, "ok": False, "error": str(e)})
            continue
        body = h[h.find('class="hb"'):]
        ads = [m.start() for m in re.finditer(r'class="hb-ad"', body)]
        ctas = [m.start() for m in re.finditer(r'class="hb-ctabox"', body)]
        sep = min((min(abs(a - c) for c in ctas) for a in ads), default=None)
        out.append({"page": k, "ok": True, "ads": len(ads), "ctas": len(ctas),
                    "bridges": len(re.findall(r'class="hb-bridge"', body)),
                    "doubt": len(re.findall(r'class="hb-doubt"', body)),
                    "min_ad_cta_gap": sep,
                    "h2": len(re.findall(r"<h2", body))})
    for name, link in extra_links:
        try:
            code = requests.get(link, timeout=40, headers=UA, allow_redirects=True).status_code
        except Exception:
            code = 0
        out.append({"page": f"링크:{name}", "ok": code == 200, "status": code})
    return out
