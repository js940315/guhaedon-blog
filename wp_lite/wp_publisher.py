"""
wp_publisher.py (v2 — Cursor 프로젝트에서 실전 검증된 로직 흡수)
워드프레스 REST API 발행 전용 경량 모듈.

반영된 실전 교훈:
- Basic Auth는 requests.auth.HTTPBasicAuth 사용 (수동 헤더 조립 X)
- Rank Math meta는 최초 POST에 절대 넣지 않는다 (미등록 키면 전체 요청 거절되는 사이트 있음)
  → 발행 성공 후 별도 PATCH로만 반영
- 카테고리: 완전 일치 → 부분 일치(첫 항목) → 없으면 auto_create 시 생성
- 태그: 완전 일치만 매칭, 없으면 생성 (부분 일치 매칭 안 함 → 중복 생성 방지)
- 이미지 alt/caption 패치 실패는 업로드 성공으로 간주 (무시)
- SEO 파일명 지정 시 ASCII-safe 임시 파일로 복사 후 업로드, 끝나면 삭제
- 관리자 ID는 반드시 Username (이메일 아님) — 아니면 HTTP 401 rest_cannot_create
"""

import mimetypes
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional

import requests
from requests.auth import HTTPBasicAuth


# ---------- 내부 헬퍼 ----------

def _api(wp_url: str, endpoint: str) -> str:
    return f"{wp_url.rstrip('/')}/wp-json/wp/v2/{endpoint}"


def _rankmath_api(wp_url: str, endpoint: str) -> str:
    return f"{wp_url.rstrip('/')}/wp-json/rankmath/v1/{endpoint}"


def _auth(wp_id: str, wp_app_pw: str) -> HTTPBasicAuth:
    return HTTPBasicAuth(wp_id.strip(), wp_app_pw.strip())


def _err(r: requests.Response) -> dict[str, Any]:
    try:
        error = r.json()
    except Exception:
        error = {"message": r.text}
    return {"ok": False, "status_code": r.status_code, "error": error}


def _slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[\s_-]+", "-", text)


# ---------- 조회/생성 ----------

def get_category_id(
    wp_url: str, wp_id: str, wp_app_pw: str, category_name: str,
    *, auto_create: bool = False, timeout: int = 30,
) -> dict[str, Any]:
    r = requests.get(
        _api(wp_url, "categories"),
        params={"search": category_name.strip(), "per_page": 50},
        auth=_auth(wp_id, wp_app_pw), timeout=timeout,
    )
    if not r.ok:
        return _err(r)
    items: list[dict] = r.json()
    for item in items:
        if item.get("name", "").strip() == category_name.strip():
            return {"ok": True, "category_id": item["id"]}
    if items:  # 부분 일치 첫 항목
        return {"ok": True, "category_id": items[0]["id"]}
    if not auto_create:
        return {"ok": False, "status_code": 404,
                "error": {"message": f"카테고리 '{category_name}' 없음 (auto_create=False)"}}
    cr = requests.post(_api(wp_url, "categories"), json={"name": category_name.strip()},
                        auth=_auth(wp_id, wp_app_pw), timeout=timeout)
    if not cr.ok:
        return _err(cr)
    return {"ok": True, "category_id": cr.json()["id"]}


def get_or_create_tag_ids(
    wp_url: str, wp_id: str, wp_app_pw: str, tag_names: list[str], *, timeout: int = 30,
) -> dict[str, Any]:
    tags_url = _api(wp_url, "tags")
    auth = _auth(wp_id, wp_app_pw)
    tag_ids: list[int] = []
    for name in tag_names:
        name = name.strip()
        if not name:
            continue
        r = requests.get(tags_url, params={"search": name, "per_page": 20}, auth=auth, timeout=timeout)
        if not r.ok:
            return _err(r)
        matched = next((it for it in r.json() if it.get("name", "").strip() == name), None)
        if matched:
            tag_ids.append(matched["id"])
            continue
        cr = requests.post(tags_url, json={"name": name}, auth=auth, timeout=timeout)
        if not cr.ok:
            return _err(cr)
        tag_ids.append(cr.json()["id"])
    return {"ok": True, "tag_ids": tag_ids}


# ---------- 미디어 ----------

def upload_media(
    wp_url: str, wp_id: str, wp_app_pw: str, image_path: str | Path,
    *, alt_text: str = "", caption: str = "", seo_filename: str = "", timeout: int = 120,
) -> dict[str, Any]:
    path = Path(image_path)
    if not path.is_file():
        return {"ok": False, "status_code": -1, "error": {"message": f"파일 없음: {path}"}}

    upload_path = path
    tmp: Optional[Path] = None
    if seo_filename.strip():
        ext = path.suffix or ".jpg"
        safe_name = re.sub(r"[^a-zA-Z0-9\-]", "-", seo_filename.strip()).strip("-")
        tmp = Path(tempfile.gettempdir()) / f"wp_upload_{safe_name}{ext}"
        shutil.copy2(path, tmp)
        upload_path = tmp

    mime_type = mimetypes.guess_type(str(upload_path))[0] or "application/octet-stream"
    try:
        with upload_path.open("rb") as f:
            image_bytes = f.read()
        r = requests.post(
            _api(wp_url, "media"),
            headers={"Content-Disposition": f'attachment; filename="{upload_path.name}"',
                     "Content-Type": mime_type},
            data=image_bytes, auth=_auth(wp_id, wp_app_pw), timeout=timeout,
        )
    finally:
        if tmp is not None and tmp.is_file():
            try:
                tmp.unlink()
            except OSError:
                pass

    if not r.ok:
        return _err(r)
    data = r.json()
    media_id: int = data.get("id", 0)
    media_url: str = data.get("source_url", "")

    if (alt_text or caption) and media_id:
        patch_body: dict[str, str] = {}
        if alt_text:
            patch_body["alt_text"] = alt_text
        if caption:
            patch_body["caption"] = caption
        try:
            requests.post(_api(wp_url, f"media/{media_id}"), json=patch_body,
                          auth=_auth(wp_id, wp_app_pw), timeout=30)
        except Exception:
            pass  # alt/caption 실패는 업로드 성공으로 간주

    return {"ok": True, "media_id": media_id, "media_url": media_url}



# ---------- 발행 전 안전장치 ----------

def sanitize_wpautop(content_html: str) -> str:
    """
    wpautop 사고 방지. 막되, 죽이지는 않는다.

    실측으로 확인한 정확한 조건 (2026-08-09):
      wpautop 이 <style> 을 깨뜨리는 건 '개행이 있을 때'가 아니라
      '빈 줄(\n\n)이 있을 때'다. wpautop 은 빈 줄 기준으로 문단을 쪼개면서
      </p><p> 를 끼워넣는데, <style> 은 <pre>/<script> 와 달리 보호 대상이 아니다.
      - savemoney119 허브 CSS : 섹션 구분 빈 줄 있음 -> 전멸
      - trip 사이트 CSS       : 빈 줄 0개          -> 179개 글 모두 멀쩡

    그래서 예외를 던져 새벽 자동발행을 중단시키는 대신,
    <style> 안의 빈 줄만 조용히 접어서 안전하게 만든다.
    """
    import re as _re

    if "<!-- wp:" in content_html:
        return content_html  # 블록 콘텐츠는 do_blocks 가 wpautop 을 제거한다

    def _fix(m):
        css = _re.sub(r"\n\s*\n+", "\n", m.group(1))
        return "<style>" + css + "</style>"

    fixed = _re.sub(r"<style[^>]*>(.*?)</style>", _fix, content_html, flags=_re.S)
    if fixed != content_html:
        print("[wpautop 가드] <style> 안 빈 줄을 제거했습니다 (CSS 파괴 방지)")
    return fixed


def assert_wpautop_safe(content_html: str) -> None:
    """검사만 하는 버전. 위험하면 ValueError."""
    import re as _re
    if "<!-- wp:" in content_html:
        return
    for m in _re.finditer(r"<style[^>]*>(.*?)</style>", content_html, flags=_re.S):
        if _re.search(r"\n\s*\n", m.group(1)):
            raise ValueError("발행 거부: <style> 안에 빈 줄이 있어 wpautop 이 CSS를 깨뜨린다")


# ---------- 발행 ----------

def post_to_wordpress(
    wp_url: str, wp_id: str, wp_app_pw: str, title: str, content_html: str,
    *, category_ids: list[int] | None = None, tag_ids: list[int] | None = None,
    featured_media_id: int | None = None, status: str = "publish", slug: str = "",
    excerpt: str = "", comment_status: str = "closed", date: str = "", timeout: int = 120,
) -> dict[str, Any]:
    content_html = sanitize_wpautop(content_html)
    body: dict[str, Any] = {
        "title": title, "content": content_html, "status": status,
        "comment_status": comment_status, "slug": _slugify(slug or title),
    }
    if category_ids:
        body["categories"] = category_ids
    if tag_ids:
        body["tags"] = tag_ids
    if featured_media_id:
        body["featured_media"] = featured_media_id
    if excerpt:
        body["excerpt"] = excerpt
    if date:
        # status="future" + date(사이트 로컬시간, "YYYY-MM-DDTHH:MM:SS")로 예약발행.
        # status="publish"와 함께 과거/현재 시각을 주면 즉시 발행되니 주의.
        body["date"] = date
    # Rank Math meta는 여기 넣지 않는다 (별도 PATCH로 처리 — 미등록 키 사이트 대비)

    r = requests.post(_api(wp_url, "posts"), json=body, auth=_auth(wp_id, wp_app_pw), timeout=timeout)
    if not r.ok:
        return _err(r)
    data = r.json()
    return {"ok": True, "post_id": data.get("id"), "post_url": data.get("link", "")}


def patch_wordpress_post(
    wp_url: str, wp_id: str, wp_app_pw: str, post_id: int, patch_body: dict, *, timeout: int = 90,
) -> dict[str, Any]:
    r = requests.post(_api(wp_url, f"posts/{post_id}"), json=patch_body,
                       auth=_auth(wp_id, wp_app_pw), timeout=timeout)
    if not r.ok:
        return _err(r)
    return {"ok": True}


def patch_post_rank_math_meta(
    wp_url: str, wp_id: str, wp_app_pw: str, post_id: int,
    *, focus_keyword: str = "", seo_description: str = "",
) -> dict[str, Any]:
    """
    서버 wp-content/mu-plugins/rank-math-rest-meta.php 설치가 선행되어야
    실제로 반영된다 (함께 제공된 mu-plugin 파일 참고).
    """
    meta: dict[str, str] = {}
    if focus_keyword.strip():
        meta["rank_math_focus_keyword"] = focus_keyword.strip()
    if seo_description.strip():
        meta["rank_math_description"] = seo_description.strip()
    if not meta:
        return {"ok": True, "skipped": True}
    return patch_wordpress_post(wp_url, wp_id, wp_app_pw, post_id, {"meta": meta})


def patch_rank_math_meta_v2(
    wp_url: str, wp_id: str, wp_app_pw: str, post_id: int,
    *, focus_keyword: str = "", seo_description: str = "", seo_title: str = "",
    og_image_url: str = "", og_image_id: int | None = None,
    og_title: str = "", og_description: str = "", timeout: int = 30,
) -> dict[str, Any]:
    """Rank Math가 공식 제공하는 REST 엔드포인트(/wp-json/rankmath/v1/updateMeta)로
    focus keyword / meta description을 반영한다 (2026-07-29 도입).

    기존 patch_post_rank_math_meta()는 wp-content/mu-plugins/rank-math-rest-meta.php가
    실제로 서버에 설치되어 있어야만 동작했는데, 2026-07-29 점검 결과 이 mu-plugin이
    한 번도 서버에 설치된 적이 없어서 지난 자동발행 글들의 focus keyword/설명이
    전부 조용히 누락되고 있었던 것으로 확인됨 (PATCH 자체는 200 OK를 반환하지만,
    REST에 등록 안 된 meta 키는 WP 코어가 값을 버림 — 에러 없이 무시되는 것이 함정).

    이 함수는 Rank Math 플러그인이 자체적으로 등록해 둔 REST 라우트를 사용하므로
    별도 mu-plugin 설치 없이도 바로 동작한다 (사이트에 Rank Math가 설치·활성화만
    되어 있으면 됨 — /wp-json/ 루트에서 'rankmath/v1' 네임스페이스 존재로 확인 가능).
    """
    meta: dict[str, str] = {}
    if focus_keyword.strip():
        meta["rank_math_focus_keyword"] = focus_keyword.strip()
    if seo_description.strip():
        meta["rank_math_description"] = seo_description.strip()
    if seo_title.strip():
        # SEO Title(rank_math_title)을 명시적으로 채워둔다. 안 채우면 사이트 전역
        # 제목 템플릿에 의존하게 되는데, 템플릿이 기대와 다르게 풀리면 Rank Math
        # 분석기가 "SEO 제목에 포커스 키워드가 없음"으로 오판할 수 있다
        # (2026-07-29 실사례로 확인됨 — focus_keyword를 제대로 넣었는데도
        # 제목/본문 매칭이 전부 실패로 뜬 원인 중 하나였음).
        meta["rank_math_title"] = seo_title.strip()
    if og_image_url.strip():
        # 2026-08-08 추가: Rank Math의 og:image 폴백은 '본문 첫 이미지'라서,
        # 본문에 <img>가 하나도 없는 허브/랜딩형 글은 대표 썸네일을 지정해뒀는데도
        # og:image가 사이트 기본 로고로 나가버린다(카톡·페북 공유 미리보기 품질 저하).
        # → facebook/twitter 이미지 메타를 명시적으로 박아 넣는다.
        meta["rank_math_facebook_image"] = og_image_url.strip()
        meta["rank_math_twitter_image"] = og_image_url.strip()
        if og_image_id:
            meta["rank_math_facebook_image_id"] = str(og_image_id)
            meta["rank_math_twitter_image_id"] = str(og_image_id)

    # 2026-08-09 추가: 카드용 제목·설명을 SEO용과 분리한다.
    #
    # 왜 필요한가 — 네이버 블로그에 URL을 넣으면 링크 카드가 뜨는데, 그 카드는
    # [이미지 + og:title + og:description + 도메인] 네 조각으로 되어 있다.
    # 사람은 이미지에서 멈추고 제목·설명을 읽은 뒤 클릭 여부를 정한다.
    # 그런데 SEO용 제목·설명은 검색엔진용이라 길고 키워드 위주다.
    #   · 실측: og:description 117자 → 네이버 카드에서 뒤가 '…'로 잘렸다
    #   · 앞 40자에 후크가 없으면 그 글은 스크롤로 지나간다
    # → SEO 값은 그대로 두고, 카드에만 다른 문구를 내보낸다.
    if og_title.strip():
        meta["rank_math_facebook_title"] = og_title.strip()
        meta["rank_math_twitter_title"] = og_title.strip()
    if og_description.strip():
        meta["rank_math_facebook_description"] = og_description.strip()
        meta["rank_math_twitter_description"] = og_description.strip()
    if not meta:
        return {"ok": True, "skipped": True}
    body = {"objectType": "post", "objectID": post_id, "meta": meta}
    r = requests.post(_rankmath_api(wp_url, "updateMeta"), json=body,
                       auth=_auth(wp_id, wp_app_pw), timeout=timeout)
    if not r.ok:
        return _err(r)
    return {"ok": True, "response": r.json()}


def publish_full_post(
    *, wp_url: str, wp_id: str, wp_app_pw: str, title: str, content_html: str,
    category_name: str = "", tag_names: list[str] | None = None,
    thumbnail_path: str | Path | None = None, thumbnail_alt: str = "", seo_filename: str = "",
    status: str = "publish", slug: str = "", excerpt: str = "", date: str = "",
    focus_keyword: str = "", seo_description: str = "", auto_create_category: bool = True,
    require_thumbnail: bool = True,
) -> dict[str, Any]:
    """올인원: 썸네일 업로드 → 카테고리/태그 확인 → 발행 → Rank Math 메타 PATCH.

    require_thumbnail=True(기본값)일 때 thumbnail_path가 비어있으면 발행 자체를
    거부한다 (썸네일 누락 방지 안전장치 — 반드시 이미지를 먼저 생성해서 넘길 것).
    정말 썸네일 없이 발행해야 하는 예외 상황에서만 require_thumbnail=False로 호출한다.
    """
    if require_thumbnail and not thumbnail_path:
        return {
            "ok": False, "status_code": -1,
            "error": {"message": "썸네일 누락: thumbnail_path 없이는 발행하지 않음 "
                                  "(require_thumbnail=True가 기본값). 썸네일 이미지를 "
                                  "먼저 생성한 뒤 다시 호출할 것."},
        }

    media_id: int | None = None
    media_url: str = ""
    category_id: int | None = None
    resolved_tag_ids: list[int] = []

    if thumbnail_path:
        res = upload_media(wp_url, wp_id, wp_app_pw, thumbnail_path,
                            alt_text=thumbnail_alt or title, seo_filename=seo_filename or _slugify(title))
        if not res["ok"]:
            return res  # 썸네일 실패 시 발행 중단할지, 계속할지는 호출부에서 try/except로 감쌀 것
        media_id = res["media_id"]
        media_url = res.get("media_url", "")

    if category_name:
        res = get_category_id(wp_url, wp_id, wp_app_pw, category_name, auto_create=auto_create_category)
        if not res["ok"]:
            return res
        category_id = res["category_id"]

    if tag_names:
        res = get_or_create_tag_ids(wp_url, wp_id, wp_app_pw, tag_names)
        if not res["ok"]:
            return res
        resolved_tag_ids = res["tag_ids"]

    res = post_to_wordpress(
        wp_url, wp_id, wp_app_pw, title, content_html,
        category_ids=[category_id] if category_id else None,
        tag_ids=resolved_tag_ids or None, featured_media_id=media_id,
        status=status, slug=slug or title, excerpt=excerpt, date=date,
    )
    if not res["ok"]:
        return res

    post_id = res.get("post_id")
    if post_id and (focus_keyword.strip() or seo_description.strip() or media_url):
        # 2026-07-29부터: mu-plugin 미설치 문제로 항상 조용히 실패하던 구버전 대신
        # Rank Math 공식 REST 엔드포인트를 우선 사용. 혹시 사이트에서 이 라우트가
        # 막혀 있으면(플러그인 비활성 등) 구버전 mu-plugin 방식으로 폴백한다.
        rm = patch_rank_math_meta_v2(wp_url, wp_id, wp_app_pw, int(post_id),
                                      focus_keyword=focus_keyword, seo_description=seo_description or excerpt,
                                      seo_title=title, og_image_url=media_url, og_image_id=media_id)
        if not rm.get("ok"):
            rm_fallback = patch_post_rank_math_meta(wp_url, wp_id, wp_app_pw, int(post_id),
                                                      focus_keyword=focus_keyword, seo_description=seo_description or excerpt)
            rm = {"ok": rm_fallback.get("ok", False), "primary_error": rm, "fallback": rm_fallback}
        res["rank_math_meta_patch"] = rm  # PATCH 실패해도 글 발행 결과는 성공 유지

    return {**res, "media_id": media_id, "category_id": category_id, "tag_ids": resolved_tag_ids}
