# savemoney-spoke

네이버 블로그(구해돈) → 워드프레스 허브(savemoney119.com) 유입용
**복붙 스탠바이 생성기.**

네이버는 API 자동 발행을 막는다. 그래서 자동화 범위는 **"복붙 직전까지"** 다.

## 매일 하는 일

```bash
# 1) 그날 허브 세트에서 초안 10건 자동 추출 (FAQ → 세부키워드)
python _engine/make_spokes.py ../_set_20260809.py 0809 B

# 2) 초안의 _todo 를 처리하고 spokes_0809.json 으로 rename

# 3) 빌드
python _engine/build_spokes.py _engine/spokes_0809.json
```

→ `output/{MMDD}/네이버_스탠바이.html` 생성.
브라우저로 열고 **제목 복사 / 본문 복사** 버튼을 눌러 네이버에 붙여넣으면 끝.

`build_report.json` 의 `problems` 와 `cross_problems` 가 **둘 다 빈 배열**이어야 정상.

## 폴더

```
_engine/
  make_spokes.py             허브 세트 → 스포크 초안 자동 추출
  build_spokes.py            빌더 (엔진 — 손대지 않는다)
  spokes_MMDD.json           그날 데이터 (매일 이것만 교체)
  HANDOFF_스포크_운영.md      ⭐ 제목·본문 뽑는 규칙 / 함정 / 체크리스트
output/{MMDD}/
  네이버_스탠바이.html         복사 버튼 달린 결과물
state/
  seen_keywords.json         이미 쓴 키워드 (중복 회피)
build_report.json            빌드 검증 결과
```

## 처음 세팅하는 사람

`_engine/HANDOFF_스포크_운영.md` 부터 읽는다. 특히 8절(함정)과 9절(체크리스트).

⚠️ GitHub에 올릴 때 **Claude GitHub App을 이 repo에 개별 설치**해야 한다.
인증만으론 push가 403(`Resource not accessible by integration`)으로 막힌다.
