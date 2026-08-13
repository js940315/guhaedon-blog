# -*- coding: utf-8 -*-
"""make_spokes.py — 허브 세트에서 스포크 10건 '초안'을 자동 추출한다.

    wp_lite/_set_YYYYMMDD.py  →  _engine/spokes_MMDD.json (초안)

■ 핵심 발상
그날 허브 세트에는 FAQ가 14개 들어 있다(hub 4 · t1 5 · t2 5).
이 FAQ는 이미 "사람들이 실제로 검색하는 질문" 형태다. 즉 세부키워드 후보 그 자체다.
답변 본문도 이미 사실 검증을 거친 문장이다. 새로 조사할 게 없다.

그래서 이 스크립트는 FAQ를 스포크 10건의 뼈대로 옮긴다.

■ ⚠️ 자동으로 안 되는 것 (반드시 사람이 손본다)
  1. 제목 — 자동 변환은 후보일 뿐이다. 실제 검색어는 지식iN·연관검색어를 봐야 나온다.
  2. 표 3줄 — 그대로 두면 10건이 전부 같은 표가 된다. 유사문서로 잡힌다.
     build_spokes.py 의 cross_check() 가 3회 이상 반복 문장을 잡아주니 그걸 보고 고친다.
  3. 여운형 질문 — 템플릿에서 돌려 쓰므로 소재에 맞게 바꾼다.
각 post 의 `_todo` 필드에 뭘 고쳐야 하는지 적어 둔다. 다 고쳤으면 `_todo` 를 지운다.

■ 사용법 (저장소 루트에서)
    python _engine/make_spokes.py ../_set_20260809.py 0809
    python _engine/build_spokes.py _engine/spokes_0809.json
"""

import importlib.util
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://savemoney119.com"

# 소재 유형별 배분 (NAVER_SPOKE_STRATEGY.md 2절)
QUOTA = {
    "A": [("지역형", 5), ("대상형", 3), ("상황·문제형", 2)],
    "B": [("상황·문제형", 4), ("대상형", 4), ("절차·금액형", 2)],
}

# FAQ 질문 → 유형 판정 힌트
TYPE_HINTS = {
    "대상형": ["대상", "회원", "명의", "가입", "해당", "포함"],
    "절차·금액형": ["얼마", "금액", "비용", "무료", "돈", "만원", "신청", "절차", "기한", "소멸"],
    "상황·문제형": ["안 ", "못 ", "왜", "언제", "어떻게", "진짜", "안돼", "없는데", "아직"],
}

# 같은 문장이 10건에 반복되면 유사문서로 잡힌다. 아래 풀에서 돌려 쓴다.
PUSHES = [
    "몇 번 고르면 결과가 바로 나옵니다.",
    "가입 시기만 넣으면 1분 안에 판정됩니다.",
    "본인 상황에 맞는 답만 골라 정리해뒀습니다.",
    "화면에서 바로 갈라지니 헷갈릴 일이 없습니다.",
    "조건별로 나눠놨으니 해당하는 것만 보시면 됩니다.",
    "표로 비교해뒀으니 한 번에 보입니다.",
    "여기서 확인하고 다음 단계를 정하시면 됩니다.",
    "복잡한 절차를 순서대로만 정리했습니다.",
    "지금 확인해두면 나중에 다시 찾을 일이 없습니다.",
    "놓치기 쉬운 부분까지 같이 짚어뒀습니다.",
]

LEADS = [
    "여기서 갈리는 부분이라 본인 상황부터 확인하는 게 빠릅니다.",
    "사람마다 답이 달라서 일반론으로는 판단이 안 됩니다.",
    "이 질문의 답은 본인 조건에 따라 완전히 달라집니다.",
    "말로 설명하는 것보다 직접 확인하는 쪽이 정확합니다.",
    "헷갈리는 지점이라 기준부터 잡고 가는 게 좋습니다.",
    "여기까지 읽으셨다면 본인 케이스가 궁금하실 겁니다.",
    "결론은 조건에 달려 있어서 확인이 먼저입니다.",
    "이 부분은 추측하지 말고 확인하시는 게 안전합니다.",
    "판단 기준이 하나가 아니라 나눠서 봐야 합니다.",
    "지금 상황이 어느 쪽인지부터 정하고 가야 합니다.",
]

# 마지막 링크는 전부 메인허브로 간다. 앵커도 허브가 실제로 주는 것을 말해야 한다.
END_ANCHORS = [
    "대상 여부와 지급 일정 한 번에 보기",
    "조건별로 나눈 결과 확인하기",
    "판별 기준까지 정리해서 보기",
    "내 경우가 어디에 해당하는지 보기",
    "기준과 예외까지 확인하기",
    "확인 방법과 다음 단계 보기",
    "쿠폰 말고 받을 수 있는 것까지 보기",
    "기한 계산과 선택지 한 번에 보기",
    "선택지별 금액과 비용 비교 보기",
    "전체 흐름 한 화면에서 보기",
]

QUESTIONS = [
    "여러분은 어느 쪽에 해당하셨나요?",
    "이런 경우, 주변에도 꽤 있으시죠?",
    "확인해보니 어떠셨나요?",
    "이 부분, 미리 알고 계셨나요?",
    "같은 상황 겪어보신 적 있으신가요?",
    "어디까지 알아보실 생각이신가요?",
    "생각보다 헷갈리는 지점 아닌가요?",
    "이번엔 놓치지 않으실 수 있겠죠?",
    "다들 어떻게 처리하고 계신가요?",
    "이런 안내, 충분하다고 보시나요?",
]


def strip_tags(s):
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def sentences(text):
    """한국어 문장 분리. '~다.' '~요.' 뒤에서만 자른다."""
    t = strip_tags(text)
    parts = re.split(r"(?<=[다요])\.\s+", t)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        out.append(p if p.endswith((".", "?", "!")) else p + ".")
    return out


def _stub_hub_builder():
    """_set_*.py 는 wp_lite/hub_builder.py 의 위젯 헬퍼를 import 한다.

    우리는 SET 딕셔너리의 텍스트만 쓰고 위젯 HTML은 안 쓴다. 그래서 hub_builder 가
    옆에 없어도(저장소를 다른 PC로 옮긴 경우) 추출이 죽지 않도록 스텁을 끼워 넣는다.
    """
    import types
    stub = types.ModuleType("hub_builder")
    for name in ("steps_visual", "status_list", "point_box", "bridge",
                 "cta_pair", "build_hub", "set_header_hub_link"):
        setattr(stub, name, lambda *a, **k: "")
    sys.modules.setdefault("hub_builder", stub)


def load_set(path):
    sys.path.insert(0, os.path.dirname(os.path.abspath(path)) or ".")
    try:
        import hub_builder  # noqa: F401  (옆에 있으면 진짜를 쓴다)
    except Exception:
        _stub_hub_builder()
    spec = importlib.util.spec_from_file_location("_setmod", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def guess_type(q, set_type):
    allowed = [t for t, _ in QUOTA[set_type]]
    best, score = allowed[0], -1
    for t, words in TYPE_HINTS.items():
        if t not in allowed:
            continue
        s = sum(1 for w in words if w in q)
        if s > score:
            best, score = t, s
    return best


def make_title(q, head, focus):
    """FAQ 질문 → 제목 후보. 어디까지나 후보다."""
    q = q.strip().rstrip("?").strip()
    cands = []
    if head in q:
        cands.append(q)
    else:
        cands.append(f"{head} {q}")
    long = f"{focus} {q}"
    if len(long) <= 42:
        cands.append(long)
    cands.append(f"{head} {q}, 확인 방법")
    seen, out = set(), []
    for c in cands:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def main():
    if len(sys.argv) < 3:
        print("사용법: python _engine/make_spokes.py <_set_YYYYMMDD.py> <MMDD> [A|B]")
        sys.exit(1)
    set_path, date = sys.argv[1], sys.argv[2]
    set_type = sys.argv[3].upper() if len(sys.argv) > 3 else "B"

    m = load_set(set_path)
    S = m.SET
    slug = S["slug_base"]
    hub_urls = {"hub": f"{SITE}/{slug}/",
                "check": f"{SITE}/{slug}-check/",
                "apply": f"{SITE}/{slug}-apply/"}

    pages = S["pages"]
    head = S["topic"].split()[0]                      # 예: '따릉이'
    # ── 반복 회피용 풀. 10건에 같은 문장이 3번 이상 들어가면 유사문서로 잡힌다.
    warn_pool = [s for s in sentences(pages["hub"]["warn"]) if len(s) > 12]
    for key in ("hub", "t1", "t2"):
        p = pages.get(key)
        if not p:
            continue
        for k in ("deadline", "amount"):
            if p.get(k):
                warn_pool.append(strip_tags(p[k]) + ".")
        for c in p.get("checks", []):
            warn_pool.append(strip_tags(c) if c.endswith(".") else strip_tags(c) + ".")
    warn_pool = list(dict.fromkeys(warn_pool))

    row_pool = []
    for key in ("hub", "t1", "t2"):
        p = pages.get(key)
        if not p:
            continue
        for r in p.get("sum_rows", []):
            t = strip_tags(r)
            row_pool.append(t.split(" : ", 1) if " : " in t else ["구분", t])
    row_pool = [r for i, r in enumerate(row_pool)
                if r not in row_pool[:i]]

    # FAQ 수집 — 출처 페이지가 마지막 링크(cta_end) 목적지를 결정한다
    pool = []
    for key in ("hub", "t1", "t2"):
        p = pages.get(key)
        if not p:
            continue
        end = "apply" if key == "t2" else "check"
        for q, a in p.get("faq", []):
            pool.append({"q": q, "a": a, "focus": p["focus"],
                         "tags": p["tags"], "end": end})

    # 유형별 할당량에 맞춰 고른다
    picked, used = [], set()
    for typ, n in QUOTA[set_type]:
        got = 0
        for i, f in enumerate(pool):
            if i in used or got >= n:
                continue
            if guess_type(f["q"], set_type) == typ:
                f["type"] = typ
                picked.append(f)
                used.add(i)
                got += 1
        for i, f in enumerate(pool):        # 모자라면 아무거나 채운다
            if got >= n:
                break
            if i not in used:
                f["type"] = typ
                picked.append(f)
                used.add(i)
                got += 1

    posts = []
    for i, f in enumerate(picked[:10]):
        sents = sentences(f["a"])
        cands = make_title(f["q"], head, f["focus"])

        # 1행은 이 글 고유(답변에서 숫자가 든 문장), 2·3행은 풀에서 겹치지 않게
        # 도입 / 본문 / 표가 같은 문장을 돌려 쓰지 않도록 구간을 나눈다
        intro = sents[:2] if len(sents) >= 2 else sents
        rest = sents[2:]
        thin = len(rest) < 2                       # 답변이 짧아 겹침이 불가피한 경우
        body = rest if not thin else sents[1:]

        pick = rest or sents
        key_fact = next((s for s in pick if re.search(r"\d", s)), pick[0] if pick else "")
        second = next((s for s in pick if s != key_fact and len(s) > 14),
                      pick[-1] if pick else "")
        table = [["핵심", key_fact[:52].rstrip(".")],
                 ["확인", second[:52].rstrip(".")]]
        if row_pool:
            table.append(row_pool[i % len(row_pool)])

        base = [t.lstrip("#") for t in f["tags"]]
        tags = ["#" + t for t in base]
        focus_words = [w for w in f["focus"].replace(head, "").split() if len(w) > 1]
        extra = ([f"#{head}{w}" for w in focus_words] +
                 [f"#{head}보상", f"#{head}대상자", f"#{head}쿠폰",
                  f"#{head}확인", "#개인정보유출", "#피해구제"])
        for e in extra:
            if len(tags) >= 8:
                break
            if e not in tags:
                tags.append(e)
        posts.append({
            "type": f["type"],
            "title": cands[0],
            "_title_candidates": cands,
            "intro": intro if len(intro) >= 2 else intro + ["아래에서 순서대로 정리했습니다."],
            "table": table,
            "sub1": "📌 " + f["q"].rstrip("?"),
            "body1": body[:4] if body else sents,
            "cta_mid": [LEADS[i % len(LEADS)], PUSHES[i % len(PUSHES)],
                        f"{S['topic']} 조회", "hub"],
            "warns": ([warn_pool[i % len(warn_pool)],
                       warn_pool[(i + 5) % len(warn_pool)]]
                      if len(warn_pool) >= 6 else warn_pool[:2]),
            "outro": [sents[-1] if sents else "자세한 내용은 아래에서 확인하실 수 있습니다."],
            "cta_end": [END_ANCHORS[i % len(END_ANCHORS)], "hub"],
            "question": QUESTIONS[i % len(QUESTIONS)],
            "tags": tags[:8],
            "_todo": (["제목을 지식iN·연관검색어로 확정",
                       "표 '핵심·확인' 2줄이 본문 문장과 겹친다 — 숫자·기한 위주로 줄여 쓸 것",
                       "여운형 질문을 소재에 맞게 교체"]
                      + (["⚠ 원본 FAQ 답변이 짧아 도입·본문 문장이 겹친다. 본문을 보강할 것"]
                         if thin else [])),
        })

    out = {"date": date, "topic": S["topic"], "set_type": set_type,
           "hub": hub_urls,
           "disclaimer": "※ 이 글은 공개된 보도와 공공기관 발표를 정리한 정보 안내이며, 법률 자문이 아닙니다.",
           "_draft": True,
           "posts": posts}
    path = os.path.join(ROOT, "_engine", f"spokes_{date}_draft.json")
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=1)

    print(f"초안 {len(posts)}건 추출 → _engine/spokes_{date}_draft.json")
    print(f"FAQ 풀 {len(pool)}개 중 {len(picked[:10])}개 사용")
    print()
    for i, p in enumerate(posts, 1):
        print(f"  {i:2d}. [{p['type']}] {p['title']}")
    print()
    print("⚠️ 이건 초안이다. 각 post 의 _todo 3개를 처리한 뒤")
    print("   spokes_%s.json 으로 이름을 바꾸고 build_spokes.py 를 돌린다." % date)
    print("⚠️ 허브 URL 3개가 실제로 200인지 브라우저로 먼저 확인할 것:")
    for k, v in hub_urls.items():
        print(f"     {k:6} {v}")


if __name__ == "__main__":
    main()
