# -*- coding: utf-8 -*-
"""
naver_ads_keywordtool.py
네이버 검색광고(Search Ad) API — 키워드 도구(/keywordstool) 조회 전용 경량 모듈.

용도: 여행 소재 선정 시(2번 단계) 후보 키워드들의 월간 검색량(PC/모바일)과
경쟁강도를 조회해 우선순위를 정하는 데 쓴다 (TRAVEL_COWORK_TASK_PROMPT.md 9-6 참고).

인증 방식: HMAC-SHA256 서명
- sign_key = f"{timestamp}.{method}.{uri}"
- signature = base64(HMAC-SHA256(secret_key, sign_key))
- 헤더: X-Timestamp / X-API-KEY(=액세스라이선스) / X-Customer(=CUSTOMER_ID) / X-Signature

자격증명은 wp_lite/.env.travel.json의 naver_ads_customer_id / naver_ads_api_key /
naver_ads_secret_key 세 값을 사용한다 (2026-07-26 사용자가 직접 발급).
"""

import base64
import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import Any

import requests

BASE_URL = "https://api.naver.com"


def _signature(timestamp: str, method: str, uri: str, secret_key: str) -> str:
    message = f"{timestamp}.{method}.{uri}"
    digest = hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _headers(method: str, uri: str, customer_id: str, api_key: str, secret_key: str) -> dict[str, str]:
    timestamp = str(int(time.time() * 1000))
    return {
        "Content-Type": "application/json; charset=UTF-8",
        "X-Timestamp": timestamp,
        "X-API-KEY": api_key,
        "X-Customer": str(customer_id),
        "X-Signature": _signature(timestamp, method, uri, secret_key),
    }


def load_naver_ads_credentials(env_path: str | Path = "wp_lite/.env.travel.json") -> dict[str, str]:
    """.env.travel.json에서 naver_ads_* 세 값을 읽어온다."""
    data = json.loads(Path(env_path).read_text(encoding="utf-8"))
    required = ["naver_ads_customer_id", "naver_ads_api_key", "naver_ads_secret_key"]
    missing = [k for k in required if not data.get(k)]
    if missing:
        raise ValueError(f".env.travel.json에 다음 키가 없습니다: {missing}")
    return {
        "customer_id": data["naver_ads_customer_id"],
        "api_key": data["naver_ads_api_key"],
        "secret_key": data["naver_ads_secret_key"],
    }


def get_keyword_stats(
    keywords: list[str],
    *,
    customer_id: str,
    api_key: str,
    secret_key: str,
    timeout: int = 30,
) -> dict[str, Any]:
    """
    /keywordstool 호출 — 최대 5개 키워드(콤마 구분, 공백 제거)까지 한 번에 조회 가능
    (네이버 API 제약). 반환값의 keywordList 항목마다 다음 필드가 들어있다:
    relKeyword(연관키워드), monthlyPcQcCnt(PC 월간검색량), monthlyMobileQcCnt(모바일
    월간검색량), monthlyAvePcClkCnt/monthlyAveMobileClkCnt(평균 클릭수),
    monthlyAvePcCtr/monthlyAveMobileCtr(평균 클릭률), plAvgDepth(평균 노출 순위),
    compIdx(경쟁정도: 낮음/중간/높음).

    주의: 이 엔드포인트는 CPC(입찰가)를 직접 주지 않는다 — 검색량·경쟁정도로
    상대적 우선순위를 매기는 용도로 쓴다 (실제 CPC 입찰가가 필요하면 별도로
    광고그룹을 만들어 입찰가 제안 API를 따로 호출해야 하나, 이 파이프라인은
    소재 우선순위 판단이 목적이라 검색량+경쟁정도만으로 충분하다).
    """
    if not keywords:
        raise ValueError("keywords가 비어있습니다.")
    if len(keywords) > 5:
        raise ValueError("네이버 API 제약상 한 번에 최대 5개 키워드까지만 조회 가능합니다.")

    uri = "/keywordstool"
    method = "GET"
    hint_keywords = ",".join(k.replace(" ", "") for k in keywords)

    r = requests.get(
        BASE_URL + uri,
        params={"hintKeywords": hint_keywords, "showDetail": "1"},
        headers=_headers(method, uri, customer_id, api_key, secret_key),
        timeout=timeout,
    )
    if not r.ok:
        return {"ok": False, "status_code": r.status_code, "error": _safe_json(r)}
    return {"ok": True, "data": r.json()}


def _safe_json(r: requests.Response) -> Any:
    try:
        return r.json()
    except Exception:
        return {"message": r.text}


if __name__ == "__main__":
    # 간단 자가 테스트: 자격증명이 유효한지 실제 키워드 하나로 확인.
    creds = load_naver_ads_credentials()
    result = get_keyword_stats(["제주도여행"], **creds)
    print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
