# -*- coding: utf-8 -*-
"""검색·홈판 트랙 썸네일 렌더러 — `N번 사진.jpg` 를 만든다.

## 왜 이 파일이 생겼나 (2026-08-13)

`build_homefeed.py` 는 본문(`0번 본문.txt`)만 만들고 사진은 만들지 않았다.
그래서 0813 스탠바이를 돌렸더니 목록에 전부 `[사진 0장]` 으로 찍혔다.
운영 문서 286줄이 `cu.build_thumbnail_svg(...)` 를 부르는데, 정작 그 모듈
(`common_utils.py`)이 이 저장소에 없어서 호출할 수가 없었다.

경제비버·카카이슬은 `build_posts.py` 안에 이 단계가 박혀 있다. 구해돈은
본문 빌더가 따로라 렌더링만 떼어 여기에 둔다. 규격은 경제비버와 같게 맞춘다
— 레터박스 제거 → 1080 정사각 → JPEG 품질 92.

## 파이프라인

    thumb 설정 → SVG (common_utils) → 헤드리스 크롬 스크린샷 → PNG
    → 마젠타 레터박스 제거 → 1080x1080 → `N번 사진.jpg`

## 사용

    python _engine/render_thumbs.py _engine/search_0813_s1.json
    python _engine/render_thumbs.py _engine/search_0813_*.json     # 여러 개
"""

import glob
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common_utils as cu

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIZE = 1080


def crop_letterbox(im):
    """스크린샷 가장자리의 마젠타(레터박스 키 색) 띠를 제거한다.

    경제비버 build_posts.py 의 같은 이름 함수를 그대로 옮겼다. 래퍼 배경을
    카드에 절대 없는 마젠타로 깔아두고 여기서 그 색만 걷어낸다. 세 번 재발한
    문제라 방어가 3중이다 — 비율 판정, 경계 여유 크롭, 잔여 픽셀 덮어쓰기.
    """
    im = im.convert("RGB")
    w, h = im.size
    px = im.load()

    def key(p):
        return p[0] > 180 and p[2] > 180 and p[1] < 110

    def col_ratio(x):
        ys = range(0, h, 5)
        return sum(1 for y in ys if key(px[x, y])) / len(list(ys))

    def row_ratio(y):
        xs = range(0, w, 5)
        return sum(1 for x in xs if key(px[x, y])) / len(list(xs))

    R = 0.80
    left = 0
    while left < w // 2 and col_ratio(left) >= R:
        left += 1
    right = w
    while right > w // 2 and col_ratio(right - 1) >= R:
        right -= 1
    top = 0
    while top < h // 2 and row_ratio(top) >= R:
        top += 1
    bottom = h
    while bottom > h // 2 and row_ratio(bottom - 1) >= R:
        bottom -= 1

    if (left, top, right, bottom) != (0, 0, w, h):
        PAD = 2
        box = (min(left + PAD, w // 2) if left else 0,
               min(top + PAD, h // 2) if top else 0,
               max(right - PAD, w // 2) if right < w else w,
               max(bottom - PAD, h // 2) if bottom < h else h)
        im = im.crop(box)
        w, h = im.size
        px = im.load()

    for y in range(h):
        for x in range(w):
            if not key(px[x, y]):
                continue
            fill = None
            for nx in range(x - 1, -1, -1):
                if not key(px[nx, y]):
                    fill = px[nx, y]
                    break
            if fill is None:
                for nx in range(x + 1, w):
                    if not key(px[nx, y]):
                        fill = px[nx, y]
                        break
            px[x, y] = fill or (10, 20, 40)
    return im


def render_one(src):
    d = json.loads(open(src, encoding="utf-8").read())
    th = d.get("thumb")
    if not th:
        print(f"  [건너뜀] {os.path.basename(src)} — thumb 설정 없음")
        return False

    photo = os.path.join(REPO, "assets", "photos", th["photo"])
    if not os.path.exists(photo):
        print(f"  [실패] 배경 사진 없음: {th['photo']}")
        return False

    svg = cu.build_thumbnail_svg(
        photo, th["line1"], th["line2"],
        accent_words=th.get("accent") or None,
        size=SIZE, dim=th.get("dim", 0.0),
        logo_path=th.get("logo"),
    )

    outdir = os.path.join(REPO, "output", str(d["date"]), str(d["seq"]))
    os.makedirs(outdir, exist_ok=True)
    dst = os.path.join(outdir, "1번 사진.jpg")

    tmpdir = tempfile.mkdtemp()
    svg_path = os.path.join(tmpdir, "t.svg")
    png_path = os.path.join(tmpdir, "t.png")
    try:
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg)
        if not cu.convert_svg_to_png(svg_path, png_path):
            print(f"  [실패] 렌더 실패: {os.path.basename(src)}")
            return False
        im = crop_letterbox(Image.open(png_path).convert("RGB"))
        if im.size != (SIZE, SIZE):
            im = im.resize((SIZE, SIZE), Image.LANCZOS)
        im.save(dst, "JPEG", quality=92, subsampling=1)
    finally:
        for p in (svg_path, png_path):
            if os.path.exists(p):
                os.remove(p)
        os.rmdir(tmpdir)

    print(f"  [완료] {d['date']}/{d['seq']}/1번 사진.jpg  ← {th['photo']}")
    return True


def rewrite_index(date):
    """0_목록.txt 의 사진 장수를 다시 센다.

    본문 빌더가 목록을 만드는데 그 시점엔 사진이 아직 없다. 그대로 두면
    사진을 다 구워놓고도 목록에는 [사진 0장]으로 남는다(2026-08-13 실측).
    사진을 만든 쪽이 마지막에 다시 세는 게 맞다.
    """
    day = os.path.join(REPO, "output", str(date))
    if not os.path.isdir(day):
        return
    rows = []
    for name in sorted(os.listdir(day), key=lambda x: x.zfill(3)):
        sub = os.path.join(day, name)
        body = os.path.join(sub, "0번 본문.txt")
        if os.path.isdir(sub) and os.path.exists(body):
            with open(body, encoding="utf-8") as f:
                first = f.read().split("\n", 1)[0]
            n_img = len([x for x in os.listdir(sub) if x.endswith("번 사진.jpg")])
            rows.append(f"{name:>3}. {first}   [사진 {n_img}장]")
    with open(os.path.join(day, "0_목록.txt"), "w", encoding="utf-8") as f:
        f.write(f"{date} 발행 목록\n" + "=" * 62 + "\n" + "\n".join(rows) + "\n")
    print(f"목록 갱신: output/{date}/0_목록.txt")


def main():
    if len(sys.argv) < 2:
        print("사용법: python _engine/render_thumbs.py _engine/search_MMDD_s*.json")
        sys.exit(2)

    srcs = []
    for pat in sys.argv[1:]:
        srcs.extend(sorted(glob.glob(pat)) or [pat])

    ok = sum(1 for s in srcs if render_one(s))

    dates = set()
    for s in srcs:
        try:
            dates.add(str(json.loads(open(s, encoding="utf-8").read())["date"]))
        except (OSError, ValueError, KeyError):
            pass
    for d in sorted(dates):
        rewrite_index(d)

    print(f"썸네일 {ok}/{len(srcs)}건 생성")
    sys.exit(0 if ok == len(srcs) else 1)


if __name__ == "__main__":
    main()
