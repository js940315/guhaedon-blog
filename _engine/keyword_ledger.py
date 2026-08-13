# -*- coding: utf-8 -*-
"""seen_keywords.json 자동 갱신 — 검색 트랙과 홈판 트랙이 같이 쓴다.

## 왜 이 파일이 생겼나 (2026-08-13)

`state/seen_keywords.json` 은 "이미 쓴 세부키워드"를 모아두는 장부다.
같은 키워드로 또 쓰면 네이버가 자기복제로 보고, 유입도 안 는다.

그런데 이 장부를 **갱신하는 코드가 어디에도 없었다.** 사람이 손으로 적는
구조라 실제로 0810·0811 분이 통째로 빠졌고, 장부에는 0809 열 건만 남아
있었다. 중복 방지가 사실상 꺼져 있던 셈이다.

그래서 빌더가 끝날 때마다 자동으로 적게 만든다. **사람 손을 타면 또 깨진다.**

## 트랙을 나누지 않고 한 장부에 모으는 이유

검색 트랙과 홈판 트랙은 규격은 다르지만 **같은 블로그(구해돈)에 올라간다.**
트랙별로 장부를 따로 두면 "홈판에서 쓴 근로장려금 키워드를 검색 트랙이 또 쓰는"
사고가 난다. 그래서 날짜별로 한 곳에 모으고, 어느 트랙이 썼는지만 표시한다.
"""

import json
import os
import tempfile


def _path(root):
    return os.path.join(root, "state", "seen_keywords.json")


def load(root):
    """장부 전체를 읽는다. 없으면 빈 dict."""
    p = _path(root)
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # 장부가 깨져도 빌드는 계속돼야 한다. 중복 검사만 못 할 뿐이다.
        return {}


def all_keywords(root):
    """지금까지 쓴 키워드 전부. 중복 검사용."""
    out = []
    for day in load(root).values():
        out.extend(day.get("keywords", []))
    return out


def find_duplicates(root, keywords, exclude_date=None):
    """이번에 쓰려는 키워드 중 이미 장부에 있는 것을 돌려준다.

    exclude_date 를 주면 그 날짜 기록은 빼고 본다. 안 그러면 같은 글을 다시
    빌드할 때 직전 실행이 적어둔 자기 자신을 중복으로 잡는다. 빌더는 위반이
    0이 될 때까지 여러 번 돌리는 게 정상이라 이 오탐이 매번 뜬다.
    """
    seen = set()
    for date, day in load(root).items():
        if exclude_date is not None and date == exclude_date:
            continue
        seen.update(day.get("keywords", []))
    return [k for k in keywords if k in seen]


def record(root, date, topic, keywords, track, set_type=""):
    """그날 쓴 키워드를 장부에 적는다.

    같은 날 두 번 돌려도 합집합으로 합쳐지므로 재실행해도 안전하다.
    쓰기는 tmp → os.replace 로 원자적으로 한다. OneDrive 가 파일을 NUL 로
    손상시킨 사례가 있어서다(인수인계서 8절).
    """
    if not keywords:
        return

    data = load(root)
    entry = data.get(date, {})

    old = entry.get("keywords", [])
    merged = list(old)
    for k in keywords:
        if k not in merged:
            merged.append(k)

    tracks = entry.get("tracks", [])
    if track not in tracks:
        tracks.append(track)

    entry["topic"] = topic or entry.get("topic", "")
    entry["tracks"] = tracks
    entry["keywords"] = merged
    if set_type:
        entry["set_type"] = set_type
    data[date] = entry

    p = _path(root)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, p)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise

    return len(merged) - len(old)


if __name__ == "__main__":
    # 자체 테스트 — 임시 폴더에서 돌린다. 실제 장부는 건드리지 않는다.
    import shutil

    tmpdir = tempfile.mkdtemp()
    try:
        assert load(tmpdir) == {}
        assert all_keywords(tmpdir) == []

        added = record(tmpdir, "0101", "테스트주제", ["가", "나"], "spoke", "B")
        assert added == 2, added
        assert all_keywords(tmpdir) == ["가", "나"]

        # 같은 날 다시 — 합집합, 중복은 안 늘어난다
        added = record(tmpdir, "0101", "테스트주제", ["나", "다"], "homefeed")
        assert added == 1, added
        assert all_keywords(tmpdir) == ["가", "나", "다"]
        assert load(tmpdir)["0101"]["tracks"] == ["spoke", "homefeed"]
        assert load(tmpdir)["0101"]["set_type"] == "B"   # 빈 값으로 안 지워진다

        assert find_duplicates(tmpdir, ["나", "라"]) == ["나"]
        # 재빌드 오탐 방지 — 같은 날짜 기록은 빼고 본다
        assert find_duplicates(tmpdir, ["나"], exclude_date="0101") == []
        record(tmpdir, "0102", "다른날", ["나"], "spoke")
        assert find_duplicates(tmpdir, ["나"], exclude_date="0101") == ["나"]
        assert record(tmpdir, "0102", "x", [], "spoke") is None   # 빈 입력은 무시

        print("keyword_ledger 자체 테스트 통과")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
