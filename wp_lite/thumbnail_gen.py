"""
thumbnail_gen.py
savemoney119 공용 썸네일 생성기.

디자인 규칙 (2026-07-22 v2 갱신, 사용자 피드백 반영):
- 배경은 카테고리와 무관하게 항상 네이비 그라데이션으로 고정한다
  (빨강 배경은 채택하지 않음 — 시안 비교 후 네이비가 더 낫다는 피드백).
- 좌상단에 빨간 알약(pill) 배지로 카테고리명 표시 + 옆에 연도.
- 제목은 굵은(Black) 폰트 + 짙은 네이비 외곽선(stroke)을 둘러 어떤 배경 위에서도
  또렷하게 보이도록 한다.
- v2: "한눈에 딱 보이는" 가독성을 최우선으로, 제목 폰트를 92pt까지 키우되
  fit-to-width/height 로직으로 제목이 길어도 박스를 벗어나거나 잘리지 않게
  자동으로 살짝 축소한다(최소 56pt).
- v2: 제목 중 숫자·핵심 키워드는 highlight_words로 지정하면 본문에서 쓰는
  포인트 레드(#e0301e)로 강조 — 브랜드 색상 통일 + 시선을 바로 핵심으로 유도.
- 부제목(있으면) 1줄, 우하단에 savemoney119 워터마크.
- 사이즈는 1200x630 (Open Graph / 카카오톡 링크 미리보기 표준 비율 1.91:1) 고정.
  정사각형(1:1)으로 바꾸지 않는다 — 카카오톡 공유 미리보기, 페이스북/트위터 링크
  카드가 전부 이 비율 기준이라 잘림 없이 온전히 보인다.

폰트 확보 순서 (이 샌드박스는 root 권한이 없어 apt-get install은 항상 실패하므로
사용하지 않는다):
  1) /tmp/fonts/NotoSansKR-{Black,Bold,Regular}.ttf 캐시가 있으면 그대로 사용.
  2) 없으면 /tmp/fonts/NotoSansKR-Variable.ttf(가변 폰트) 캐시 확인 후 사용,
     굵기는 set_variation_by_axes([weight])로 지정 (400/700/900).
  3) 위 캐시도 없으면 urllib.request로
     https://raw.githubusercontent.com/google/fonts/main/ofl/notosanskr/NotoSansKR%5Bwght%5D.ttf
     (User-Agent 헤더 필요)를 받아 /tmp/fonts/NotoSansKR-Variable.ttf로 저장 후 재사용.
  4) 그래도 실패하면 ImageFont.load_default()로 진행한다
     (한글이 깨지더라도 썸네일 자체가 없는 것보다 낫다).
"""
import os
import re
import urllib.request
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630

PRIMARY = (224, 48, 30)        # --sm-primary (레드 포인트: 배지, 하단 바, 제목 강조)
NAVY_TOP = (23, 60, 130)
NAVY_BOTTOM = (11, 32, 74)
STROKE_NAVY = (8, 22, 54)
STROKE_TITLE = (0, 0, 0)      # 2026-07-22 v3: 제목 외곽선은 네이비 대신 블랙으로 변경
                               # (두꺼운 네이비 외곽선이 "글자가 깨지는" 느낌을 줘서 사용자 피드백 반영,
                               # 5종 스타일 샘플 비교 후 black_outline 스타일로 최종 확정)
WHITE = (255, 255, 255)

FONT_DIR = "/tmp/fonts"
VARIABLE_FONT_PATH = f"{FONT_DIR}/NotoSansKR-Variable.ttf"
VARIABLE_FONT_URL = (
    "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanskr/"
    "NotoSansKR%5Bwght%5D.ttf"
)
WEIGHT_AXIS = {"Regular": 400, "Bold": 700, "Black": 900}

TITLE_MAX_WIDTH = W - 2 * 80     # 좌우 80px 여백을 넘지 않게
TITLE_MAX_HEIGHT_1LINE = 150
TITLE_MAX_HEIGHT_2LINE = 260
TITLE_START_SIZE = 92
TITLE_MIN_SIZE = 56


def _ensure_variable_font() -> bool:
    if os.path.exists(VARIABLE_FONT_PATH):
        return True
    try:
        os.makedirs(FONT_DIR, exist_ok=True)
        req = urllib.request.Request(VARIABLE_FONT_URL, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=20).read()
        with open(VARIABLE_FONT_PATH, "wb") as f:
            f.write(data)
        return True
    except Exception:
        return False


def _font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    static_path = f"{FONT_DIR}/NotoSansKR-{weight}.ttf"
    if os.path.exists(static_path):
        return ImageFont.truetype(static_path, size)
    if _ensure_variable_font():
        f = ImageFont.truetype(VARIABLE_FONT_PATH, size)
        try:
            f.set_variation_by_axes([WEIGHT_AXIS.get(weight, 700)])
        except Exception:
            pass
        return f
    return ImageFont.load_default()


def _fit_title_font(
    draw: ImageDraw.ImageDraw, lines: list[str], *, weight: str = "Black",
    start_size: int = TITLE_START_SIZE, min_size: int = TITLE_MIN_SIZE,
    max_width: int = TITLE_MAX_WIDTH,
) -> tuple[ImageFont.FreeTypeFont, int]:
    """제목이 가로 폭/전체 높이를 넘지 않는 선에서 가장 큰 폰트 크기를 찾는다.

    "한눈에 딱 보이는" 사이즈를 우선하되, 짧은 제목이면 92pt 그대로,
    긴 제목이면 자동으로 축소해서 박스 밖으로 삐져나가거나 잘리지 않게 한다.
    """
    max_height = TITLE_MAX_HEIGHT_1LINE if len(lines) <= 1 else TITLE_MAX_HEIGHT_2LINE
    size = start_size
    while size > min_size:
        font = _font(weight, size)
        widths = []
        heights = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            widths.append(bbox[2] - bbox[0])
            heights.append(bbox[3] - bbox[1])
        gap = 28 if size >= 72 else 20
        total_height = sum(heights) + gap * max(0, len(lines) - 1)
        if (not widths or max(widths) <= max_width) and total_height <= max_height:
            return font, size
        size -= 2
    return _font(weight, min_size), min_size


def _split_highlight(line: str, highlight_words):
    """title 한 줄을 (일반 텍스트, 강조 텍스트) 세그먼트로 쪼갠다."""
    words = [w for w in (highlight_words or []) if w]
    if not words:
        return [(line, False)]
    pattern = "|".join(re.escape(w) for w in words)
    segments = []
    last = 0
    for m in re.finditer(pattern, line):
        if m.start() > last:
            segments.append((line[last:m.start()], False))
        segments.append((line[m.start():m.end()], True))
        last = m.end()
    if last < len(line):
        segments.append((line[last:], False))
    return segments or [(line, False)]


def _draw_title_line(draw, x, y, line, font, highlight_words=None):
    """한 줄을 좌측부터 그리되, highlight_words에 해당하는 구간만 레드로 그린다."""
    cursor_x = x
    for text, is_highlight in _split_highlight(line, highlight_words):
        if not text:
            continue
        color = PRIMARY if is_highlight else WHITE
        draw.text((cursor_x, y), text, font=font, fill=color,
                   stroke_width=3, stroke_fill=STROKE_TITLE)
        cursor_x += draw.textlength(text, font=font)


def make_thumbnail(
    out_path: str,
    badge_text: str,
    title_lines: list[str],
    subtitle_text: str = "",
    year_text: str = "",
    highlight_words=None,
) -> str:
    """네이비 고정 배경 + 레드 배지 + 외곽선 제목 썸네일을 그려 out_path에 저장한다.

    title_lines: 최대 2줄 권장 (그 이상이면 글자가 작아지거나 잘릴 수 있음).
    highlight_words: 제목 중 이 단어/구간과 정확히 일치하는 부분만 포인트 레드로
        강조해서 그린다 (예: ["최대 100% 환급", "5년"]). 지정하지 않으면 전체 흰색.
    """
    img = Image.new("RGB", (W, H), NAVY_TOP)
    draw = ImageDraw.Draw(img)

    for y in range(H):
        t = y / H
        r = int(NAVY_TOP[0] * (1 - t) + NAVY_BOTTOM[0] * t)
        g = int(NAVY_TOP[1] * (1 - t) + NAVY_BOTTOM[1] * t)
        b = int(NAVY_TOP[2] * (1 - t) + NAVY_BOTTOM[2] * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    bar_h = 14
    draw.rectangle([0, H - bar_h, W, H], fill=PRIMARY)

    font_badge = _font("Bold", 30)
    font_year = _font("Black", 44)
    font_sub = _font("Bold", 40)
    font_brand = _font("Bold", 30)

    bbox = draw.textbbox((0, 0), badge_text, font=font_badge)
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 24, 14
    badge_w, badge_h = bw + pad_x * 2, bh + pad_y * 2
    badge_x, badge_y = 80, 72
    draw.rounded_rectangle(
        [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
        radius=badge_h // 2, fill=PRIMARY,
    )
    draw.text((badge_x + pad_x, badge_y + pad_y - bbox[1]), badge_text, font=font_badge, fill=WHITE)

    if year_text:
        draw.text((badge_x + badge_w + 20, badge_y + 2), year_text, font=font_year, fill=WHITE,
                   stroke_width=2, stroke_fill=STROKE_NAVY)

    lines = title_lines[:2]
    title_font, title_size = _fit_title_font(draw, lines)
    line_gap = 28 if title_size >= 72 else 20

    ty = badge_y + badge_h + 58
    for line in lines:
        _draw_title_line(draw, 78, ty, line, title_font, highlight_words=highlight_words)
        bbox2 = draw.textbbox((0, 0), line, font=title_font)
        ty += (bbox2[3] - bbox2[1]) + line_gap

    if subtitle_text:
        draw.text((80, ty + 10), subtitle_text, font=font_sub, fill=(255, 220, 210),
                   stroke_width=2, stroke_fill=STROKE_NAVY)

    bb = draw.textbbox((0, 0), "savemoney119", font=font_brand)
    bw2 = bb[2] - bb[0]
    draw.text((W - bw2 - 50, H - bar_h - 55), "savemoney119", font=font_brand, fill=WHITE)

    fmt = "PNG" if out_path.lower().endswith(".png") else "JPEG"
    save_kwargs = {} if fmt == "PNG" else {"quality": 92}
    img.save(out_path, fmt, **save_kwargs)
    return out_path


if __name__ == "__main__":
    make_thumbnail(
        "/tmp/thumbnail_gen_selftest.png",
        badge_text="정부지원금",
        title_lines=["예시 제목 1줄", "예시 제목 2줄"],
        subtitle_text="부제목 예시 텍스트",
        year_text="2026",
        highlight_words=["1줄"],
    )
    print("SELFTEST_OK")


# ====================================================================
# OG 카드 전용 썸네일 (2026-08-09 v4 — 네이버 외부유입 최우선)
# ====================================================================
# 왜 별도 함수인가
#   네이버 블로그에 URL을 넣으면 링크 카드가 뜬다. 그 카드는 이미지 아래에
#   og:title 과 og:description 을 이미 보여준다. 그래서 이미지가 제목을 한 번 더
#   반복하면 같은 말이 두 번 나오고, 클릭할 이유가 안 생긴다.
#   → 이미지는 제목을 반복하지 않고 "눌러야 하는 이유" 하나만 담당한다.
#
# 실측으로 확정한 규격 (2026-08-09, 실제 네이버 카드 렌더 확인)
#   · 네이버 링크 카드는 og:image 의 좌우를 잘라낸다. 우하단 브랜드명이 잘렸다.
#     → 모든 핵심 요소를 가운데 정사각형(630x630) 안에 넣는다.
#     → 브랜드·배지는 그 밖에 둔다. 잘려도 상관없는 것만 바깥에.
#   · 카드 이미지는 본문 폭 전체로 크게 뜬다. 큰 글씨가 유리하다.
#
# 구성 (B안 자기대입형)
#   윗줄 작게 : 규모·근거 (예: "462만명 유출")
#   큰 글씨 2줄 : 자기대입 질문 (예: "나도" / "대상일까?")
#   흰 알약 버튼 : 행동 문구 + ▶ (예: "가입 시기로 1분 확인 ▶")

# 실측(2026-08-09): 네이버 링크 카드는 og:image 우측을 약 5% 잘라냈다
# (savemoney119 → savemoney11). 1:1 통짜 크롭은 관측되지 않았다.
# 따라서 후크는 760px 까지 허용하고, 버튼은 그보다 안쪽에 둔다.
# ※ 다른 화면에서 1:1 크롭이 확인되면 이 값을 640 으로 줄인다.
OG_HOOK_W = 760
OG_SAFE_W = 700
OG_EYEBROW = (160, 205, 255)
# v4.1 실측: 폰(360px)으로 축소하면 네이비 위 빨강(255,90,70)은 배경에 먹혀 흐려진다.
# 노랑이 대비가 확실히 세다. 강조색은 노랑으로 고정한다.
OG_ACCENT = (255, 214, 0)


def _fit_center(draw, text, weight, start, minimum, max_w):
    """max_w 안에 들어갈 때까지 폰트를 줄인다. (글꼴, 폭, 좌측 x, 상단 오프셋)"""
    size = start
    while size > minimum:
        f = _font(weight, size)
        b = draw.textbbox((0, 0), text, font=f)
        if b[2] - b[0] <= max_w:
            return f, b
        size -= 2
    f = _font(weight, minimum)
    return f, draw.textbbox((0, 0), text, font=f)


# 블록 사이 간격 (v4.2 — 고정 y좌표를 쓰다가 글자가 버튼을 12px 파고든 사고를 고침)
GAP_EYEBROW = 46
GAP_HOOK = 30
GAP_CTA = 54
BTN_H = 116
OG_MARGIN = 34           # 위아래 최소 여백


def make_og_thumbnail(out_path: str, eyebrow: str, hook_lines: list,
                      cta_text: str = "", brand: str = "savemoney119",
                      debug: bool = False) -> str:
    """네이버 링크 카드용 썸네일. hook_lines 2줄째가 포인트 컬러로 강조된다.

    ⚠ 고정 y좌표를 쓰지 않는다. 폰트가 자동 축소되면 실제 글자 높이가 달라져서
      아래 요소를 파고든다(실제로 -12px 겹침 사고가 났다). 그래서 모든 블록의
      실측 높이를 먼저 재고, 간격을 더해 세로 중앙에 배치한다.
    """
    img = Image.new("RGB", (W, H), NAVY_TOP)
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        draw.line([(0, y), (W, y)],
                  fill=tuple(int(NAVY_TOP[i] * (1 - t) + NAVY_BOTTOM[i] * t)
                             for i in range(3)))
    cx = W // 2

    lines = [l for l in (hook_lines or []) if l][:2]
    if cta_text:
        # ➜ ➔ → » 는 Noto Sans KR 에 글리프가 없어 두부(□)로 깨진다. ▶ 로 통일한다.
        cta_text = re.sub(r"[\s➜➔→»>▶]+$", "", cta_text).strip() + " ▶"

    # ── 1) 먼저 전부 측정한다 (그리지 않는다).
    #      가로만 맞추면 세로가 넘친다. 후크 크기를 줄여가며 세로까지 들어오게 맞춘다.
    def measure(hook_max):
        bl = []
        if eyebrow:
            f, b = _fit_center(draw, eyebrow, "Bold", 62, 36, OG_SAFE_W)
            bl.append(["t", eyebrow, f, b, b[3] - b[1], OG_EYEBROW, GAP_EYEBROW])
        for i, ln in enumerate(lines):
            f, b = _fit_center(draw, ln, "Black", hook_max, 78, OG_HOOK_W)
            gap = GAP_HOOK if i < len(lines) - 1 else GAP_CTA
            bl.append(["t", ln, f, b, b[3] - b[1],
                       OG_ACCENT if i == 1 else WHITE, gap])
        if cta_text:
            f, b = _fit_center(draw, cta_text, "Black", 60, 38, OG_SAFE_W - 60)
            bl.append(["btn", cta_text, f, b, BTN_H, (11, 32, 74), 0])
        tot = sum(x[4] for x in bl) + sum(x[6] for x in bl[:-1])
        return bl, tot

    avail = H - OG_MARGIN * 2
    hook_max = 156
    blocks, total = measure(hook_max)
    while total > avail and hook_max > 78:
        hook_max -= 4
        blocks, total = measure(hook_max)

    y = max(OG_MARGIN, (H - total) // 2)

    # ── 2) 잰 대로 그린다
    for kind, text, f, b, h, fill, gap in blocks:
        if kind == "btn":
            draw.rounded_rectangle([cx - OG_SAFE_W // 2 - 20, y,
                                    cx + OG_SAFE_W // 2 + 20, y + BTN_H],
                                   radius=BTN_H // 2, fill=WHITE)
            ty = y + (BTN_H - (b[3] - b[1])) / 2 - b[1]
            draw.text((cx - (b[2] - b[0]) / 2 - b[0], ty), text, font=f, fill=fill)
        else:
            draw.text((cx - (b[2] - b[0]) / 2 - b[0], y - b[1]), text, font=f, fill=fill)
            if debug:
                draw.rectangle([cx - (b[2] - b[0]) / 2, y,
                                cx + (b[2] - b[0]) / 2, y + h],
                               outline=(0, 255, 120), width=2)
        y += h + gap

    # brand 워터마크는 넣지 않는다 (2026-08-09 사용자 결정).
    # 카드 하단에 도메인(savemoney119.com)이 네이버 쪽에서 이미 표시되므로 중복이고,
    # 폰 크기로 줄이면 7.8px 라 읽히지도 않으면서 시선만 분산시킨다.
    # brand 인자는 호환을 위해 남겨두되 사용하지 않는다.
    _ = brand

    img.save(out_path, "JPEG", quality=92, optimize=True)
    return out_path
