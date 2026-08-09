# -*- coding: utf-8 -*-
"""savemoney119 2026-08-06 자동발행 러너 (구간 실행판 — 샌드박스 45초 제한 대응)."""
import json, os, random, sys
from datetime import datetime, timedelta

BASE = "/tmp/sm0806"
sys.path.insert(0, BASE)

from thumbnail_gen import make_thumbnail
from wp_publisher import publish_full_post
from _ap0805_lib import build_attack, build_defense, related_cards
from _ap0806sm_data_a import ARTICLES_A
from _ap0806sm_data_b import ARTICLES_B

ARTICLES = ARTICLES_A + ARTICLES_B

env = json.load(open(os.path.join(BASE, ".env.json"), encoding="utf-8"))
WP_URL, WP_ID, WP_PW = env["site_url"], env["username"], env["app_password"]

DATE_STR = datetime.now().strftime("%Y-%m-%d")
SLOTS_F = os.path.join(BASE, "_slots.json")
REPORT_F = os.path.join(BASE, "_report_20260806_savemoney.json")

# ---------- 발행 시각 10개 (최초 1회 계산 후 고정) ----------
if os.path.isfile(SLOTS_F):
    slots = [datetime.strptime(s, "%Y-%m-%dT%H:%M:%S") for s in json.load(open(SLOTS_F))]
else:
    random.seed()
    t = datetime.strptime(DATE_STR + " 07:00:00", "%Y-%m-%d %H:%M:%S")
    slots = [t]
    for _ in range(9):
        t = t + timedelta(minutes=random.uniform(60, 90))
        slots.append(t.replace(second=0, microsecond=0))
    json.dump([s.strftime("%Y-%m-%dT%H:%M:%S") for s in slots], open(SLOTS_F, "w"))

# ---------- 사전 검증 ----------
errors, seen = [], set()
if len(ARTICLES) != 10:
    errors.append(f"기사 개수 {len(ARTICLES)}개")
for a in ARTICLES:
    if a["focus"] not in a["title"]:
        errors.append(f"focus 미포함(제목): {a['focus']}")
    if a["focus"] not in a["excerpt"]:
        errors.append(f"focus 미포함(excerpt): {a['focus']}")
    if not (115 <= len(a["excerpt"]) <= 170):
        errors.append(f"excerpt 길이 {len(a['excerpt'])}: {a['title']}")
    if a["slug"] in seen:
        errors.append(f"slug 중복: {a['slug']}")
    seen.add(a["slug"])
    if a["type"] == "attack":
        if len(a["faq"]) != 5:
            errors.append(f"FAQ {len(a['faq'])}개: {a['title']}")
        h2s = [h for h, _ in a["sections"]]
        for h in h2s:
            if a["focus"] not in h:
                errors.append(f"H2 focus 없음: {h}")
        if a["cta_after"] not in h2s:
            errors.append(f"cta_after 불일치: {a['title']}")
if ARTICLES[0]["type"] == "defense":
    errors.append("수비수형이 07:00 슬롯")
if sum(1 for a in ARTICLES if a["type"] == "defense") < 2:
    errors.append("목요일인데 수비수형 2개 미만")
if errors:
    print("사전 검증 실패:")
    [print(" -", e) for e in errors]
    sys.exit(1)

report = json.load(open(REPORT_F, encoding="utf-8")) if os.path.isfile(REPORT_F) else []
done = {r["idx"] for r in report if r.get("ok")}

start, end = int(sys.argv[1]), int(sys.argv[2])
THUMB_DIR = "/tmp/thumb_savemoney_20260806"
os.makedirs(THUMB_DIR, exist_ok=True)

for i in range(start, end):
    a, when, idx = ARTICLES[i], slots[i], i + 1
    if idx in done:
        print(f"[{idx}] skip (완료됨)")
        continue
    rec = {"idx": idx, "title": a["title"], "type": a["type"], "focus_keyword": a["focus"],
           "category": a["category"], "scheduled": when.strftime("%Y-%m-%dT%H:%M:%S"),
           "status": "", "ok": False, "link": "", "post_id": None, "thumb": False,
           "rank_math": None, "error": ""}

    thumb_path = None
    for attempt in range(2):
        try:
            thumb_path = make_thumbnail(
                os.path.join(THUMB_DIR, f"thumb_{a['slug']}.jpg"),
                badge_text=a["badge"], title_lines=a["thumb_lines"],
                subtitle_text=a.get("thumb_sub", ""), year_text="2026",
                highlight_words=a.get("thumb_hl"))
            rec["thumb"] = os.path.isfile(thumb_path)
            break
        except Exception as exc:
            thumb_path = None
            rec["error"] = f"썸네일 생성 실패({attempt+1}회): {exc}"
    if not thumb_path:
        report = [r for r in report if r["idx"] != idx] + [rec]
        json.dump(report, open(REPORT_F, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"[{idx}] 썸네일 실패 → 발행 중단")
        continue

    rel = related_cards(WP_URL, WP_ID, WP_PW, a["related_kw"], exclude_titles=(a["title"],))
    html = build_attack(a, rel) if a["type"] == "attack" else build_defense(a, rel)
    status = "future" if when > datetime.now() else "publish"
    rec["status"] = status

    res = publish_full_post(
        wp_url=WP_URL, wp_id=WP_ID, wp_app_pw=WP_PW,
        title=a["title"], content_html=html, category_name=a["category"],
        tag_names=a["tags"], thumbnail_path=thumb_path,
        thumbnail_alt=f"{a['focus']} 안내 이미지", seo_filename=a["slug"],
        status=status, slug=a["slug"], excerpt=a["excerpt"],
        date=when.strftime("%Y-%m-%dT%H:%M:%S"),
        focus_keyword=a["focus"], seo_description=a["excerpt"])

    if res.get("ok"):
        rec.update(ok=True, link=res.get("post_url", ""), post_id=res.get("post_id"))
        rm = res.get("rank_math_meta_patch")
        rec["rank_math"] = bool(rm and rm.get("ok"))
        print(f"[{idx}] OK {status} {when:%H:%M} {a['title']}")
    else:
        rec["error"] = json.dumps(res, ensure_ascii=False)[:400]
        print(f"[{idx}] 실패: {rec['error']}")

    report = [r for r in report if r["idx"] != idx] + [rec]
    report.sort(key=lambda r: r["idx"])
    json.dump(report, open(REPORT_F, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print("진행:", sum(1 for r in report if r["ok"]), "/ 10")
