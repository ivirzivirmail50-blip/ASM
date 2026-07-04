"""Comprehensive integration test: every route, every POST flow, every form."""
from __future__ import annotations

import io
import json
import re
import sys

sys.path.insert(0, "/home/z/my-project/absolute-story-manager")

from app import create_app

app = create_app()
app.config["WTF_CSRF_ENABLED"] = False
app.config["TESTING"] = True
client = app.test_client()

PASS = 0
FAIL = 0
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILURES.append(f"{label}: {detail}")
        print(f"  ✗ {label} — {detail}")


def get(path: str):
    return client.get(path)


def post_json(path: str, body):
    return client.post(path, data=json.dumps(body), content_type="application/json")


def post_form(path: str, data: dict):
    return client.post(path, data=data)


# ============ 1. GET pages ============
print("\n=== 1. GET Pages ===")
for path in [
    "/", "/chapters/", "/chapters/new", "/chapters/upload", "/chapters/compare",
    "/characters/", "/characters/new", "/characters/graph",
    "/characters/graph/data", "/characters/compare",
    "/plans/", "/plans/new", "/plans/outline", "/plans/timeline",
    "/world/", "/world/new", "/world/map",
    "/search/", "/settings/", "/settings/ai", "/settings/validate",
    "/settings/backup", "/export/",
]:
    r = get(path)
    check(f"GET {path}", r.status_code == 200, f"got {r.status_code}")


# ============ 2. Detail pages (need IDs) ============
print("\n=== 2. Detail Pages ===")
r = get("/chapters/")
ch_id = (re.search(r"/chapters/([a-f0-9]{32})", r.data.decode()) or [None, None]).group(1) if re.search(r"/chapters/([a-f0-9]{32})", r.data.decode()) else None
r = get("/characters/")
char_id = (re.search(r"/characters/([a-f0-9]{32})", r.data.decode()) or [None, None]).group(1) if re.search(r"/characters/([a-f0-9]{32})", r.data.decode()) else None
r = get("/plans/")
plan_id = (re.search(r"/plans/([a-f0-9]{32})", r.data.decode()) or [None, None]).group(1) if re.search(r"/plans/([a-f0-9]{32})", r.data.decode()) else None
r = get("/world/")
wid = (re.search(r"/world/([a-f0-9]{32})", r.data.decode()) or [None, None]).group(1) if re.search(r"/world/([a-f0-9]{32})", r.data.decode()) else None

print(f"  chapter id: {ch_id[:8] if ch_id else None}")
print(f"  character id: {char_id[:8] if char_id else None}")
print(f"  plan id: {plan_id[:8] if plan_id else None}")
print(f"  world id: {wid[:8] if wid else None}")

for path in [
    f"/chapters/{ch_id}", f"/chapters/{ch_id}/edit", f"/chapters/{ch_id}/versions",
    f"/characters/{char_id}", f"/characters/{char_id}/edit",
    f"/plans/{plan_id}", f"/plans/{plan_id}/edit",
    f"/world/{wid}", f"/world/{wid}/edit", f"/world/{wid}/versions",
]:
    if "None" not in path:
        r = get(path)
        check(f"GET {path}", r.status_code == 200, f"got {r.status_code}")


# ============ 3. POST: create entities ============
print("\n=== 3. POST: Create Entities ===")
r = post_form("/chapters/new", {
    "title": "Test Chapter",
    "content": "This is test content. Word one two three four five.",
    "synopsis": "Test synopsis",
    "status": "draft",
    "target_word_count": "1000",
    "tags": "test, demo",
})
check("create chapter", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])
new_ch_id = json.loads(r.data).get("id") if r.status_code == 200 else None

r = post_form("/characters/new", {
    "name": "Test Character",
    "role": "supporting",
    "age": "25",
    "gender": "Female",
    "aliases": "TC, Test",
    "physical": "Test physical",
    "psychology": "Test psych",
})
check("create character", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])
new_char_id = json.loads(r.data).get("id") if r.status_code == 200 else None

r = post_form("/plans/new", {
    "title": "Test Plan",
    "description": "Test description",
    "status": "idea",
    "track": "Main Plot",
    "event_type": "plot_point",
})
check("create plan", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])
new_plan_id = json.loads(r.data).get("id") if r.status_code == 200 else None

r = post_form("/world/new", {
    "type": "location",
    "name": "Test Location",
    "category": "City",
    "description": "A test city",
    "content": "Full content of the test city.",
    "metadata_region": "North",
})
check("create world entry", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])
new_wid = json.loads(r.data).get("id") if r.status_code == 200 else None


# ============ 4. POST: edit entities ============
print("\n=== 4. POST: Edit Entities ===")
if new_ch_id:
    r = post_form(f"/chapters/{new_ch_id}/edit", {
        "title": "Updated Chapter Title",
        "content": "Updated content here.",
        "status": "revised",
        "synopsis": "Updated synopsis",
        "tags": "updated",
    })
    check("edit chapter", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])

if new_char_id:
    r = post_form(f"/characters/{new_char_id}/edit", {
        "name": "Updated Char",
        "role": "protagonist",
        "age": "30",
        "physical": "Updated physical",
    })
    check("edit character", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])

if new_plan_id:
    r = post_form(f"/plans/{new_plan_id}/edit", {
        "title": "Updated Plan",
        "description": "Updated desc",
        "status": "planned",
    })
    check("edit plan", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])

if new_wid:
    r = post_form(f"/world/{new_wid}/edit", {
        "type": "location",
        "name": "Updated Location",
        "category": "Town",
        "description": "Updated desc",
        "content": "Updated content",
    })
    check("edit world entry", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])


# ============ 5. POST: autosave, reorder, status, subtasks ============
print("\n=== 5. POST: Workflow Operations ===")
if new_ch_id:
    r = post_json(f"/chapters/{new_ch_id}/autosave", {"content": "Autosaved content."})
    check("autosave chapter", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])

if ch_id and new_ch_id:
    r = post_json("/chapters/reorder", {"order": [new_ch_id, ch_id]})
    check("reorder chapters", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])

if ch_id and new_ch_id:
    r = post_json("/chapters/bulk-status", {"ids": [new_ch_id], "status": "final"})
    check("bulk-status chapters", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])

if new_plan_id:
    r = post_json(f"/plans/{new_plan_id}/status", {"status": "writing"})
    check("change plan status", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])

if new_plan_id:
    r = post_json(f"/plans/{new_plan_id}/subtasks", {"title": "Subtask 1"})
    check("add subtask", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])
    subtask_id = json.loads(r.data).get("id")
    if subtask_id:
        r = post_json(f"/plans/subtasks/{subtask_id}/toggle", {})
        check("toggle subtask", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])
        r = post_json(f"/plans/{new_plan_id}/subtasks/reorder", {"order": [subtask_id]})
        check("reorder subtasks", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])
        r = post_json(f"/plans/subtasks/{subtask_id}/delete", {})
        check("delete subtask", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])

if new_plan_id:
    r = post_json("/plans/reorder", {"idea": [], "planned": [new_plan_id], "writing": [], "draft_done": [], "revised": [], "final": []})
    check("reorder plans (kanban)", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])


# ============ 6. POST: character relationships + graph ============
print("\n=== 6. POST: Character Relationships ===")
if char_id and new_char_id:
    r = post_json("/characters/relationships/new", {
        "from_id": char_id, "to_id": new_char_id,
        "type": "friend_of", "description": "Test friendship",
        "bidirectional": True,
    })
    check("create relationship", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])
    rel_id = json.loads(r.data).get("id")
    if rel_id:
        r = post_json(f"/characters/relationships/{rel_id}/delete", {})
        check("delete relationship", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])

if new_char_id:
    r = post_json("/characters/graph/save-position", {"id": new_char_id, "x": 100, "y": 200})
    check("save graph position", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])


# ============ 7. POST: world map, relations, duplicate ============
print("\n=== 7. POST: World Operations ===")
if new_wid:
    r = post_json("/world/map/pin", {"id": new_wid, "x": 45.5, "y": 30.2, "label": "Test"})
    check("set world map pin", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])

    # Pin removal (null coords)
    r = post_json("/world/map/pin", {"id": new_wid, "x": None, "y": None})
    check("remove world map pin", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])

    r = post_json(f"/world/{new_wid}/duplicate", {})
    check("duplicate world entry", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])


# ============ 8. POST: settings ============
print("\n=== 8. POST: Settings ===")
r = post_json("/settings/save", {"daily_word_goal": 750, "theme": "dark", "story_title": "Test Story"})
check("save settings", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])

r = post_json("/settings/save", {"ai.enabled": "true", "ai.provider": "ollama", "ai.model": "llama3"})
check("save AI settings", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])

r = get("/settings/validate")
check("validate data health", r.status_code == 200, f"got {r.status_code}")

r = post_json("/settings/validate/fix-word-counts", {})
check("fix word counts", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])

r = post_json("/settings/backup", {})
check("create backup", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])


# ============ 9. POST: chapter versions, restore ============
print("\n=== 9. POST: Chapter Versions ===")
if new_ch_id:
    r = get(f"/chapters/{new_ch_id}/versions")
    check("get versions list", r.status_code == 200, f"got {r.status_code}")

    # Get a version id
    m = re.search(r"restoreVersion\('([a-f0-9]+)'\)", r.data.decode())
    if m:
        v_id = m.group(1)
        # Note: restore only works if version isn't current
        versions = re.findall(r"restoreVersion\('([a-f0-9]+)'\)", r.data.decode())
        if len(versions) > 1:
            r = post_json(f"/chapters/{new_ch_id}/versions/{versions[-1]}/restore", {})
            check("restore version", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])


# ============ 10. POST: delete entities ============
print("\n=== 10. POST: Delete Entities ===")
if new_ch_id:
    r = post_json(f"/chapters/{new_ch_id}/delete", {})
    check("delete chapter", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])

if new_char_id:
    r = post_json(f"/characters/{new_char_id}/delete", {})
    check("delete character", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])

if new_plan_id:
    r = post_json(f"/plans/{new_plan_id}/delete", {})
    check("delete plan", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])

if new_wid:
    r = post_json(f"/world/{new_wid}/delete", {})
    check("delete world entry", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])


# ============ 11. File upload ============
print("\n=== 11. File Upload ===")
txt_content = b"Chapter title here.\n\nFirst paragraph of the chapter.\n\nSecond paragraph here."
r = client.post("/chapters/upload", data={
    "file": (io.BytesIO(txt_content), "test.txt"),
    "title": "Uploaded Chapter",
    "status": "draft",
}, content_type="multipart/form-data")
check("upload TXT file", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])
uploaded_ch_id = json.loads(r.data).get("id") if r.status_code == 200 else None
if uploaded_ch_id:
    r = post_json(f"/chapters/{uploaded_ch_id}/delete", {})
    check("cleanup uploaded chapter", r.status_code == 200, "")

# Re-upload on existing chapter
if ch_id:
    r = client.post(f"/chapters/{ch_id}/reupload", data={
        "file": (io.BytesIO(b"Re-uploaded content."), "reupload.txt"),
    }, content_type="multipart/form-data")
    check("reupload chapter", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])

# Split: create a multi-paragraph chapter first
r = post_form("/chapters/new", {
    "title": "Splittable Chapter",
    "content": "Para 1.\n\nPara 2.\n\nPara 3.\n\nPara 4.",
})
split_ch_id = json.loads(r.data).get("id") if r.status_code == 200 else None
if split_ch_id:
    r = post_json(f"/chapters/{split_ch_id}/split", {"at": 2})
    check("split chapter", r.status_code == 200 and json.loads(r.data).get("ok"), r.data[:200])


# ============ 12. Exports ============
print("\n=== 12. Exports ===")
for path in [
    "/export/manuscript/txt", "/export/manuscript/md", "/export/manuscript/html",
    "/export/manuscript/docx", "/export/manuscript/pdf", "/export/manuscript/epub",
    "/export/world-bible/txt", "/export/world-bible/pdf", "/export/world-bible/docx",
    "/export/full-project/pdf", "/export/full-project/docx",
    "/settings/export-json",
]:
    r = get(path)
    check(f"export {path}", r.status_code == 200 and len(r.data) > 100, f"got {r.status_code}, {len(r.data)}b")


# ============ 13. Search (FTS5) ============
print("\n=== 13. Search (FTS5) ===")
for q in ["veil", "elara", "hollowmere", "aethelgard", "malachar"]:
    r = get(f"/search/?q={q}")
    check(f"search '{q}'", r.status_code == 200, f"got {r.status_code}")


# ============ 14. AI endpoints (opt-in) ============
print("\n=== 14. AI Endpoints ===")
r = get("/ai/status")
check("AI status (enabled in test 8)", r.status_code in (200, 404), f"got {r.status_code}")
# AI test would fail without a real provider, but route should respond
r = post_json("/ai/suggest-tags", {"text": "Sample text"})
check("AI suggest-tags route", r.status_code in (200, 502, 404), f"got {r.status_code}")


# ============ 15. Error pages ============
print("\n=== 15. Error Pages ===")
r = get("/nonexistent-page-12345")
check("404 page", r.status_code == 404, f"got {r.status_code}")

r = get("/chapters/nonexistent-id-12345")
check("404 chapter detail", r.status_code == 404, f"got {r.status_code}")


# ============ Summary ============
print("\n" + "=" * 60)
print(f"TOTAL: {PASS + FAIL}  |  PASS: {PASS}  |  FAIL: {FAIL}")
print("=" * 60)
if FAILURES:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f"  - {f}")
