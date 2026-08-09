import json
import requests
from requests.auth import HTTPBasicAuth

with open("/sessions/bold-practical-carson/mnt/wp_lite/.env.travel.json", "r", encoding="utf-8") as f:
    cfg = json.load(f)

site_url = cfg["site_url"]
username = cfg["username"]
app_password = cfg["app_password"]

auth = HTTPBasicAuth(username, app_password)
post_url = f"{site_url}/wp-json/wp/v2/posts/544"
posts_collection_url = f"{site_url}/wp-json/wp/v2/posts"

def section(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

# 1. GET before write
section("STEP 1: GET /wp-json/wp/v2/posts/544?_fields=id,meta,status (BEFORE PATCH)")
r1 = requests.get(post_url, params={"_fields": "id,meta,status"}, auth=auth)
print("HTTP status:", r1.status_code)
try:
    body1 = r1.json()
    print(json.dumps(body1, ensure_ascii=False, indent=2))
except Exception as e:
    print("Could not parse JSON:", e)
    print(r1.text[:2000])

# 2. PATCH (POST) to write meta
section("STEP 2: POST (PATCH) /wp-json/wp/v2/posts/544 writing rank_math_focus_keyword / rank_math_description")
payload = {
    "meta": {
        "rank_math_focus_keyword": "제주도 가을 여행 코스",
        "rank_math_description": "제주도 가을 여행, 어디부터 가야 할지 고민되시죠? 성산일출봉부터 새별오름 억새, 우도까지 3박4일 코스로 정리했어요."
    }
}
r2 = requests.post(post_url, json=payload, auth=auth)
print("HTTP status:", r2.status_code)
try:
    body2 = r2.json()
    print("Returned meta from PATCH response:")
    print(json.dumps(body2.get("meta", "NO META KEY IN RESPONSE"), ensure_ascii=False, indent=2))
except Exception as e:
    print("Could not parse JSON:", e)
    print(r2.text[:2000])

# 3. GET after write to check persistence
section("STEP 3: GET /wp-json/wp/v2/posts/544?_fields=id,meta (AFTER PATCH) - checking persistence")
r3 = requests.get(post_url, params={"_fields": "id,meta"}, auth=auth)
print("HTTP status:", r3.status_code)
try:
    body3 = r3.json()
    print(json.dumps(body3, ensure_ascii=False, indent=2))
    meta3 = body3.get("meta", {})
    fk = meta3.get("rank_math_focus_keyword", "<<KEY MISSING>>")
    desc = meta3.get("rank_math_description", "<<KEY MISSING>>")
    expected_fk = "제주도 가을 여행 코스"
    expected_desc = "제주도 가을 여행, 어디부터 가야 할지 고민되시죠? 성산일출봉부터 새별오름 억새, 우도까지 3박4일 코스로 정리했어요."
    print("\n--- Persistence check ---")
    print("rank_math_focus_keyword actual  :", repr(fk))
    print("rank_math_focus_keyword expected:", repr(expected_fk))
    print("MATCH:", fk == expected_fk)
    print("rank_math_description actual  :", repr(desc))
    print("rank_math_description expected:", repr(expected_desc))
    print("MATCH:", desc == expected_desc)
except Exception as e:
    print("Could not parse JSON:", e)
    print(r3.text[:2000])

# 4. OPTIONS schema check
section("STEP 4: OPTIONS /wp-json/wp/v2/posts - schema.meta.properties for rank_math_* keys")
r4 = requests.options(posts_collection_url, auth=auth)
print("HTTP status:", r4.status_code)
try:
    body4 = r4.json()
    meta_schema = body4.get("schema", {}).get("properties", {}).get("meta", {})
    print("Full meta schema entry:")
    print(json.dumps(meta_schema, ensure_ascii=False, indent=2))
    props = meta_schema.get("properties", {})
    print("\n--- rank_math_* keys found in schema.meta.properties ---")
    rank_math_keys = {k: v for k, v in props.items() if "rank_math" in k}
    if rank_math_keys:
        print(json.dumps(rank_math_keys, ensure_ascii=False, indent=2))
    else:
        print("NONE FOUND. All keys present in schema.meta.properties:", list(props.keys()))
except Exception as e:
    print("Could not parse JSON:", e)
    print(r4.text[:2000])

section("DONE")
