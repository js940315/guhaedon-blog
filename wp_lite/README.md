# wp_lite — savemoney119 워드프레스 발행 엔진

구해돈 네이버 블로그가 사람을 보내는 **허브 사이트(savemoney119.com)** 를 만드는 코드다.
2026-08-10에 OneDrive에서 이 저장소로 옮겼다 — 그전까지 버전 관리가 안 돼서
누가 뭘 고쳤는지 추적이 안 됐고, 클라우드에 올릴 때마다 zip 왕복을 했다.

## ⚠️ 자격증명은 이 저장소에 없다 (Public 이다)

`.env.json` 은 **커밋하지 않는다.** `.gitignore` 가 막고 있다.
로컬 `OneDrive/바탕 화면/wp_lite/.env.json` 에 있고, 클라우드 세션에서는
마운트 경로에 있다. 형식은 이렇다:

```json
{
  "site_url": "https://...",
  "username": "...",
  "app_password": "..."
}
```

`set_publisher.publish_set(spec, env_path="...")` 로 경로를 넘길 수 있다.
넘기지 않으면 클라우드 세션 기본 경로를 본다.

> 워드프레스 앱 비밀번호는 관리자 권한이다. 절대 코드·커밋·로그에 값을 넣지 않는다.
> 네이버 광고 API 키가 든 `.env.travel.json` 도 마찬가지다(그건 여행 프로젝트 것이라
> 여기 옮기지 않았다).

## 파일

| 파일 | 역할 |
|---|---|
| `set_publisher.py` | **핵심.** 세트 3장(허브·1차·2차) 검증 → 링크배선 → 발행 → 홈고정 → 헤더갱신 |
| `wp_publisher.py` | WP REST 저수준 (발행·미디어 업로드·Rank Math 메타 패치) |
| `hub_builder.py` | 허브 HTML 생성. **직접 HTML을 짜지 않는다** |
| `thumbnail_gen.py` | 썸네일 · og:image (`make_og_thumbnail`) |
| `hb_v2_lib.py` `fix_hb_v2.py` | 허브 v2 블록 |
| `link_web.py` | 거미줄(체인) 배선 |
| `fetch_sources.py` `sources_config.json` `candidates.json` | 소재 수집 |
| `verify_posts.py` `verify_rankmath_meta.py` | 발행 후 검증 |
| `run_range.py` | 범위 일괄 처리 |
| `naver_ads_keywordtool.py` | 네이버 검색광고 키워드 조회 |
| `_set_20260809.py` | 세트 데이터 **형식 예시** (매일 새로 쓰는 파일) |

## 문서

- `COWORK_TASK_PROMPT.md` — **클라우드 루틴 프롬프트 원본.** 최신 버전이 맨 위다(현재 v8)
- `NAVER_SPOKE_STRATEGY.md` — 세부키워드·링크 규칙의 원전
- `HANDOFF_20260809_네이버유입.md` — 유입 파이프라인 인수인계
- `PROJECT_KNOWLEDGE.md` `CLAUDE_CODE_HANDOFF.md` — 배경

## 하루 발행 (2026-08-10 v8 — 2세트)

```python
import sys; sys.path.insert(0, "<경로>/wp_lite")
from set_publisher import publish_set, verify_set
from _set_YYYYMMDD_a import SET as SET_A     # A = 이슈
from _set_YYYYMMDD_b import SET as SET_B     # B = 롱테일

urls_a = publish_set(SET_A)                                    # 홈고정·헤더 = A
urls_b = publish_set(SET_B, sticky=False, update_header=False) # B는 건드리지 않는다
verify_set(urls_a); verify_set(urls_b)
```

`sticky=False` 를 빼먹으면 **B가 A의 홈 고정을 풀어버린다.**
`clear_previous_sticky()` 가 `keep_id` 하나만 남기고 나머지를 전부 해제하기 때문이다.

## 옮기지 않은 것

- **여행 프로젝트(trip_119)** 파일 — `*_travel.*`, `TRAVEL_*.md`. 별개 사업이라 뺐다
- **일회성 데이터** — `_ap*.py` `_autopublish*.py` `_report_*.json` (39개+)
- **생성물** — `thumb_*/` `og_시안/` (36MB). 매번 다시 만들어진다
