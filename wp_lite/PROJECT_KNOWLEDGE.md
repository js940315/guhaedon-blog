# savemoney119 워드프레스 자동발행 — 프로젝트 지식

Claude 앱 Projects의 "프로젝트 지식" / 커스텀 지시문에 그대로 붙여넣어 쓰는 요약본.
이 프로젝트는 대화 이력 없이도 이 문서 하나로 이어받아 작업할 수 있어야 한다.

## 한 줄 요약
개인 수익형 워드프레스 블로그 **savemoney119.com**(정부지원금·절약 정보,
40대+ 스마트폰 사용자 타겟)에 매일 글을 자동으로 조사·집필·발행하는 파이프라인.
Cowork 예약 작업으로 **매일 오전 8시 1회** 실행되며, 실행할 때마다 이 문서가 가리키는
`COWORK_TASK_PROMPT.md`의 절차를 처음부터 끝까지 그대로 따른다.

## 폴더 구조 (`wp_lite/`)
| 파일 | 역할 |
|---|---|
| `COWORK_TASK_PROMPT.md` | **최우선 참조 문서.** 실행 순서, 소재 선정 기준, 문체·구조 템플릿(공격수형/수비수형), 색상 강조 규칙, 썸네일 필수화, 발행 시각 분산 로직까지 전 과정의 단일 진실 소스(source of truth). 작업 전 반드시 전체를 읽는다. |
| `wp_publisher.py` | 워드프레스 REST API 발행 모듈. `publish_full_post()`가 썸네일 업로드→카테고리/태그 확인→발행→Rank Math 메타 PATCH를 한 번에 처리. `require_thumbnail=True`가 기본값이라 썸네일 없이는 발행 자체가 막힌다(의도된 안전장치). |
| `thumbnail_gen.py` | 공용 썸네일 생성기. `make_thumbnail()` 함수를 그대로 import해서 쓴다 — 새로 PIL 코드를 짜지 않는다. 네이비 고정 배경 + 좌상단 레드 배지 + 굵은 폰트·네이비 외곽선(stroke) 제목, 1200x630(1.91:1, OG/카카오톡 공유 표준 비율) 고정. |
| `fetch_sources.py` | 구글 뉴스 RSS를 모아 `candidates.json`을 만든다. 콘텐츠 집필 로직은 없음 — 소재 후보 수집만 담당. |
| `sources_config.json` | RSS 소스·키워드 카테고리 설정. |
| `mobile-readability-upgrade.css` | 워드프레스 커스터마이저(`Additional CSS`)에 배포된 모바일 가독성/CTA/광고슬롯/색상강조(`.sm-positive`/`.sm-negative`) 스타일. |
| `rank-math-rest-meta.php` | 서버 `wp-content/mu-plugins/`에 설치되어야 하는 mu-plugin. 없으면 글은 정상 발행되지만 Rank Math SEO 메타(focus keyword/description)만 조용히 반영 안 됨. |
| `.env.json` (커밋 금지) | `site_url` / `username`(이메일 아닌 워드프레스 Username) / `app_password`. 최초 1회 직접 채워넣는 자격증명. `.env.json.example`이 템플릿. |

## 매일 실행되는 작업 순서 (요약 — 전체는 COWORK_TASK_PROMPT.md)
1. `fetch_sources.py` 실행 → `candidates.json` 갱신.
2. WP REST API로 최근 발행 글 제목 조회 → 중복 소재 제외.
3. 오늘 다룰 3개 소재 선정 (기본 3개 모두 "공격수형"=정부지원금/할인정보, 주 1~2회는
   1개를 "수비수형"=경제 위인 스토리로 교체 — 체류시간·신뢰도용).
4. 타입별 구조 템플릿에 맞춰 100% 새로 집필 (원문 재구성 금지). 40대+ 가독성 원칙
   (문장당 정보 1개, 어려운 용어 괄호 설명, 질문형 소제목, 색상 강조, 나열형 정보
   줄바꿈) 적용.
5. `thumbnail_gen.make_thumbnail()`로 썸네일 생성 (필수, 생략 불가).
6. `wp_publisher.publish_full_post()`로 발행.
7. 대표 소재 1개는 즉시 발행, 나머지 2개는 `status="future"`로 오후/저녁 시간대에
   분산 예약 (매시간 자동발행·정형화된 패턴은 스팸 필터 위험 — 하루 3개로 제한).
8. 완료 후 제목·URL·발행상태·썸네일 성공 여부를 요약 리포트.

## 알아둬야 할 기술적 제약
- **샌드박스에 root 권한 없음** → `apt-get install`은 항상 실패한다. 한글 폰트는
  `thumbnail_gen.py`가 자동으로 `/tmp/fonts/` 캐시 → Google Fonts variable font
  다운로드 → `load_default()` 순으로 처리하므로 별도 조치 불필요.
- **파일 도구(Read/Write/Edit)와 bash 셸은 서로 다른 파일 뷰를 가질 때가 있다.**
  Write/Edit로 저장한 직후 bash에서 곧바로 실행하면 예전 버전이 보이는 경우가
  있었다 — 발행 스크립트처럼 즉시 실행이 필요한 코드는 bash heredoc(`cat > file
  << 'EOF' ... EOF`)으로 직접 써서 실행하는 편이 안전하다.
- CTA 버튼(`wide-btn`)에는 `target="_blank"` 금지 (전면 광고 노출 이슈).
- 원문 기사 15단어 이상 그대로 인용 금지.

## 현재 상태 (2026-07-21 기준)
- Cowork 예약 작업으로 매일 오전 8시 자동 실행 설정 완료.
- 테스트 발행 2건 완료: 4차 민생회복지원금(정부지원금), 여름 전기요금·에너지캐시백
  (생활 꿀팁) — 둘 다 새 네이비 썸네일 템플릿·색상 강조·줄바꿈 규칙 적용 확인됨.
- 다음에 이어받는 사람/세션은 이 문서 + `COWORK_TASK_PROMPT.md`만 읽으면 전체
  맥락 파악 가능하도록 유지하는 것이 원칙 — 규칙이 바뀌면 두 문서를 함께 갱신할 것.
