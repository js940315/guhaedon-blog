# -*- coding: utf-8 -*-
"""
fix_hb_v2.py — wpautop 로 깨진 글을 v2 CSS + wp:html 로 일괄 복구하고
내부링크 거미줄(1차·2차)을 심는다.

실행:  python3 fix_hb_v2.py          (드라이런, 변경 없음)
       python3 fix_hb_v2.py --apply  (실제 반영)
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

U = lambda slug: "%s/%s/" % (SITE, slug)


def api(path, data=None, method=None):
    req = urllib.request.Request(
        SITE + path,
        data=json.dumps(data).encode() if data else None,
        headers={
            "Authorization": "Basic " + AUTH,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
        method=method or ("POST" if data else "GET"),
    )
    return json.load(urllib.request.urlopen(req, timeout=60))


# ── 내부링크 거미줄 설계 ─────────────────────────────────────
# 추석 클러스터  : 허브 4188(지역 조회) ─ 1차 4184(지역현황) / 4186(신청방법)
#                                      └ 2차 통영·영동·고창·부안 개별 글
# 따릉이 클러스터 : 허브 4215(대상 조회) ─ 1차 4213(확인방법) / 4211(손배청구)
CHUSEOK_2ND = [
    (U("tongyeong-minsaeng-recovery-350000"), "경남 통영시 35만원", "409억원 투입 · 지급 확정"),
    (U("yeongdong-minsaeng-support-300000"), "충북 영동군 30만원", "8월 17일 온라인 신청 시작"),
    (U("buan-minsaeng-support-300000"), "전북 부안군 30만원", "전 군민 선불카드 · 추석 전"),
    (U("gochang-gunmin-vitality-fund"), "전북 고창군 30만원", "군민활력지원금 대상·지급방법"),
]

PLAN = {
    # ── 추석 민생지원금 클러스터
    4188: dict(
        title="추석 민생지원금, 이어서 확인하세요",
        links=[
            (U("chuseok-support-region-status"), "지역별 지급 현황 전체 보기", "확정 · 추진중 · 무산 3단계 정리"),
            (U("chuseok-support-how-to-apply"), "신청 방법과 준비물", "온라인 · 방문 접수 경로와 필요 서류"),
            (U("local-currency-gift-certificate-links"), "지역화폐 앱 · 가맹점 확인", "지역사랑상품권 등록과 사용처"),
        ],
        region_filter=True,
    ),
    4184: dict(
        title="우리 동네를 찾으셨다면 다음 단계",
        links=[
            (U("chuseok-support-how-to-apply"), "신청 방법과 준비물", "온라인 · 방문 접수 경로와 필요 서류"),
            (U("chuseok-support-region-check"), "우리 동네 지급 여부 조회", "30만~50만원 지급 지역 확인"),
        ]
        + CHUSEOK_2ND,
        region_filter=True,
    ),
    4186: dict(
        title="신청 전에 같이 보면 좋은 글",
        links=[
            (U("chuseok-support-region-status"), "지역별 지급 현황 전체 보기", "확정 · 추진중 · 무산 3단계 정리"),
            (U("chuseok-support-region-check"), "우리 동네 지급 여부 조회", "30만~50만원 지급 지역 확인"),
            (U("local-currency-gift-certificate-links"), "지역화폐 앱 · 가맹점 확인", "지역사랑상품권 등록과 사용처"),
        ],
        region_filter=False,
    ),
    # ── 따릉이 개인정보 유출 클러스터
    4215: dict(
        title="따릉이 개인정보 유출, 이어서 확인하세요",
        links=[
            (U("ttareungi-privacy-leak-compensation-check"), "대상자 확인 방법", "내 계정이 포함됐는지 조회하는 법"),
            (U("ttareungi-privacy-leak-compensation-apply"), "손해배상 청구 4가지 방법", "5천원 쿠폰 말고 받는 방법 비교"),
        ],
        region_filter=False,
    ),
    4213: dict(
        title="확인이 끝났다면 다음 단계",
        links=[
            (U("ttareungi-privacy-leak-compensation-apply"), "손해배상 청구 4가지 방법", "분쟁조정 · 공동소송 비용과 기간 비교"),
            (U("ttareungi-privacy-leak-compensation"), "유출 대상 462만명 전체 정리", "무엇이 유출됐고 누가 대상인지"),
        ],
        region_filter=False,
    ),
    4211: dict(
        title="청구 전에 같이 보면 좋은 글",
        links=[
            (U("ttareungi-privacy-leak-compensation-check"), "내가 대상자인지 먼저 확인", "조회 방법과 통지 확인 절차"),
            (U("ttareungi-privacy-leak-compensation"), "유출 대상 462만명 전체 정리", "무엇이 유출됐고 누가 대상인지"),
        ],
        region_filter=False,
    ),
    # ── 단독 글
    3076: dict(
        title="교통비 환급, 같이 보면 좋은 글",
        links=[
            (U("gitongcard-moduui-card-2026"), "기후동행카드 → 모두의카드 전환", "9월 1일부터 청년 39세까지 환급"),
            (U("paju-pafriends-teen-transport-refund"), "청소년 교통비 환급 사례", "지역화폐로 돌려받는 방법"),
        ],
        region_filter=False,
    ),
}


def insert_region_filter(body: str) -> str:
    """지역 목록 바로 앞에 검색·필터 바를 넣는다. 이미 있으면 건드리지 않는다."""
    if 'id="hbq"' in body or '<div class="hb-list">' not in body:
        return body
    return body.replace('<div class="hb-list">', L.REGION_FILTER + '<div class="hb-list">', 1)


def main():
    apply = "--apply" in sys.argv
    print("MODE:", "APPLY" if apply else "DRY-RUN")
    for pid, spec in PLAN.items():
        d = api("/wp-json/wp/v2/posts/%d?context=edit&_fields=content,title,slug" % pid)
        raw = d["content"]["raw"]
        body = L.strip_old_style(raw)
        # 재실행 시 관련글 블록이 중복 누적되지 않게 기존 것을 먼저 제거
        # (hb-rel 안에는 중첩 div 가 없으므로 첫 </div> 에서 끊는 게 정확하다)
        body = re.sub(r'<div class="hb-rel">(?:(?!</div>).)*</div>', "", body, flags=re.S)

        if spec["region_filter"]:
            body = insert_region_filter(body)

        rel = L.build_related(spec["title"], spec["links"])
        js = L.REGION_FILTER_JS if spec["region_filter"] else ""

        # .hb 디자인시스템을 쓰지 않는 글은 원본 CSS를 반드시 보존한다.
        # (안 그러면 전용 위젯 CSS가 통째로 날아간다 — 3076에서 실제로 겪음)
        use_hb = 'class="hb"' in body or "class='hb'" in body
        css = None if use_hb else L.extract_css(raw)
        if not use_hb and not css:
            print("%s  건너뜀 — .hb 래퍼도 없고 원본 CSS도 없음" % pid)
            continue

        new = L.assemble(body, rel, js, css=css)

        ok = L.is_wpautop_safe(new)
        print(
            "%s  %-46s old=%6d new=%6d safe=%s links=%d"
            % (pid, d["slug"][:46], len(raw), len(new), ok, len(spec["links"]))
        )
        if not ok:
            print("   !! 안전검증 실패 — 건너뜀")
            continue
        if apply:
            api("/wp-json/wp/v2/posts/%d" % pid, {"content": new})
            print("   -> 반영 완료")


if __name__ == "__main__":
    main()
