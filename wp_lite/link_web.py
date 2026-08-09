# -*- coding: utf-8 -*-
"""
link_web.py — 2차 글 → 1차 허브 역링크를 심어 거미줄을 완성한다.

대상은 전용 <style> 이 없는 일반 글이라 wp:html 로 감싸면 안 된다.
(wpautop 이 문단을 만들어줘야 하는 글이므로)
=> 인라인 style 속성 + 개행 0개 한 줄 블록으로만 삽입한다.

실행:  python3 link_web.py          (드라이런)
       python3 link_web.py --apply
"""
import base64
import json
import os
import re
import sys
import urllib.request

import hb_v2_lib as L

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, ".env.json"), encoding="utf-8"))
SITE = CFG["site_url"].rstrip("/")
AUTH = base64.b64encode(
    ("%s:%s" % (CFG["username"], CFG["app_password"])).encode()
).decode()
U = lambda s: "%s/%s/" % (SITE, s)

MARK = "hb-web-v2"  # 중복 삽입 방지 마커

CHUSEOK_BACKLINKS = [
    (U("chuseok-support-region-check"), "우리 동네 지급 여부 조회", "전국 지자체 30만~50만원 지급 지역 확인"),
    (U("chuseok-support-region-status"), "지역별 지급 현황 한눈에", "확정 · 추진중 · 무산 3단계 정리"),
    (U("chuseok-support-how-to-apply"), "신청 방법과 준비물", "온라인 · 방문 접수 경로와 필요 서류"),
]

PLAN = {
    4150: ("추석 민생지원금, 전국 현황도 확인하세요", CHUSEOK_BACKLINKS),
    4148: ("추석 민생지원금, 전국 현황도 확인하세요", CHUSEOK_BACKLINKS),
    4110: ("추석 민생지원금, 전국 현황도 확인하세요", CHUSEOK_BACKLINKS),
    4108: ("추석 민생지원금, 전국 현황도 확인하세요", CHUSEOK_BACKLINKS),
    4017: ("추석 민생지원금, 이어서 확인하세요", CHUSEOK_BACKLINKS),
}


def api(path, data=None):
    req = urllib.request.Request(
        SITE + path,
        data=json.dumps(data).encode() if data else None,
        headers={
            "Authorization": "Basic " + AUTH,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST" if data else "GET",
    )
    return json.load(urllib.request.urlopen(req, timeout=60))


def insert_before_schema(body: str, block: str) -> str:
    """JSON-LD 스키마 스크립트 앞에 넣는다. 없으면 맨 끝에 붙인다."""
    m = re.search(r'<script type="application/ld\+json">', body)
    if m:
        return body[: m.start()] + block + "\n" + body[m.start():]
    return body.rstrip() + "\n" + block


def main():
    apply = "--apply" in sys.argv
    print("MODE:", "APPLY" if apply else "DRY-RUN")
    for pid, (title, links) in PLAN.items():
        d = api("/wp-json/wp/v2/posts/%d?context=edit&_fields=content,slug" % pid)
        raw = d["content"]["raw"]

        if MARK in raw:
            print("%s  %-36s 이미 삽입됨 — 건너뜀" % (pid, d["slug"][:36]))
            continue
        if "<!-- wp:" in raw:
            print("%s  %-36s wp:html 글 — link_web 대상 아님" % (pid, d["slug"][:36]))
            continue

        block = L.build_related_inline(title, links).replace(
            "<div style=", '<div data-%s="1" style=' % MARK, 1
        )
        new = insert_before_schema(raw, block)

        # 자가검증: 블록 안에 개행이 끼면 wpautop 이 깨뜨린다
        assert "\n" not in block, "블록에 개행이 있으면 안 된다"
        print(
            "%s  %-36s old=%6d new=%6d links=%d"
            % (pid, d["slug"][:36], len(raw), len(new), len(links))
        )
        if apply:
            api("/wp-json/wp/v2/posts/%d" % pid, {"content": new})
            print("   -> 반영 완료")


if __name__ == "__main__":
    main()
