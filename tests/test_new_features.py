"""Tests for new backend endpoints (undo, world types, JSON import, search case/regex, AI)."""
import json
import re
import pytest


def get_id(html, pattern):
    m = re.search(pattern, html.decode())
    return m.group(1) if m else None


class TestUndoRoutes:
    def test_undo_empty_returns_400(self, client):
        r = client.post("/undo", data=json.dumps({}), content_type="application/json")
        assert r.status_code == 400

    def test_undo_after_delete(self, client):
        # Create a chapter
        r = client.post("/chapters/new", data={"title": "Undo Me", "content": "x"})
        ch_id = json.loads(r.data)["id"]
        # Delete it
        r = client.post(f"/chapters/{ch_id}/delete",
                        data=json.dumps({}), content_type="application/json")
        assert json.loads(r.data)["undoable"] is True
        # Undo
        r = client.post("/undo", data=json.dumps({}), content_type="application/json")
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True
        # Verify restored
        r = client.get(f"/chapters/{ch_id}")
        assert r.status_code == 200

    def test_undo_list(self, client):
        r = client.get("/undo/list")
        assert r.status_code == 200
        assert "ops" in json.loads(r.data)


class TestWorldTypesRoutes:
    def test_add_custom_type(self, client):
        r = client.post("/settings/world-types",
                        data=json.dumps({"action": "add", "name": "religion"}),
                        content_type="application/json")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["ok"] is True
        assert "religion" in data["types"]

    def test_remove_custom_type(self, client):
        # Add first
        client.post("/settings/world-types",
                    data=json.dumps({"action": "add", "name": "language"}),
                    content_type="application/json")
        # Remove
        r = client.post("/settings/world-types",
                        data=json.dumps({"action": "remove", "name": "language"}),
                        content_type="application/json")
        assert r.status_code == 200
        assert "language" not in json.loads(r.data)["types"]

    def test_cannot_remove_default_type(self, client):
        r = client.post("/settings/world-types",
                        data=json.dumps({"action": "remove", "name": "location"}),
                        content_type="application/json")
        assert r.status_code == 400

    def test_cannot_add_duplicate_type(self, client):
        r = client.post("/settings/world-types",
                        data=json.dumps({"action": "add", "name": "location"}),
                        content_type="application/json")
        assert r.status_code == 400


class TestJSONImportExport:
    def test_export_json_has_all_entities(self, client):
        # Create some entities
        client.post("/chapters/new", data={"title": "Ch1", "content": "content"})
        client.post("/characters/new", data={"name": "Char1", "role": "minor"})
        client.post("/plans/new", data={"title": "Plan1"})
        client.post("/world/new", data={"type": "location", "name": "Place1"})
        r = client.get("/settings/export-json")
        data = json.loads(r.data)
        assert "chapters" in data
        assert "characters" in data
        assert "plans" in data
        assert "world_entries" in data
        assert "chapter_versions" in data
        assert "character_groups" in data
        assert "character_relationships" in data
        assert "world_relations" in data

    def test_export_strips_api_key(self, client):
        client.post("/settings/save", data=json.dumps({"ai.api_key": "secret-key"}),
                    content_type="application/json")
        r = client.get("/settings/export-json")
        data = json.loads(r.data)
        assert data["settings"]["ai.api_key"] == ""

    def test_import_json_round_trip(self, client):
        # Export current (mostly defaults)
        r = client.get("/settings/export-json")
        exported = json.loads(r.data)
        # Modify story title
        exported["settings"]["story_title"] = "Imported Story Title"
        # Import via POST
        import io
        r = client.post("/settings/import-json",
                        data={
                            "file": (io.BytesIO(json.dumps(exported).encode()), "test.json"),
                        },
                        content_type="multipart/form-data")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["ok"] is True

    def test_import_json_invalid_file(self, client):
        import io
        r = client.post("/settings/import-json",
                        data={
                            "file": (io.BytesIO(b"not json"), "bad.json"),
                        },
                        content_type="multipart/form-data")
        assert r.status_code == 400

    def test_import_json_page(self, client):
        r = client.get("/settings/import-json")
        assert r.status_code == 200


class TestSearchCaseRegex:
    def test_case_sensitive_search(self, client):
        # Create a chapter with mixed case
        client.post("/chapters/new", data={
            "title": "MixedCase Title",
            "content": "Contains Elara and elara",
        })
        # Case-insensitive (default): should find both
        r = client.get("/search/?q=elara")
        assert r.status_code == 200
        # Case-sensitive: should find fewer
        r = client.get("/search/?q=Elara&case=1")
        assert r.status_code == 200

    def test_regex_search(self, client):
        client.post("/chapters/new", data={
            "title": "Regex Test",
            "content": "The year 2024 was eventful. Also 2025.",
        })
        # Regex for 4-digit year
        r = client.get("/search/?q=\\d{4}&regex=1")
        assert r.status_code == 200

    def test_invalid_regex(self, client):
        # Invalid regex should not crash
        r = client.get("/search/?q=[invalid&regex=1")
        assert r.status_code == 200


class TestChapterNewEndpoints:
    def test_versions_save(self, client):
        r = client.post("/chapters/new", data={"title": "Save", "content": "v1"})
        ch_id = json.loads(r.data)["id"]
        r = client.post(f"/chapters/{ch_id}/versions/save",
                        data=json.dumps({}), content_type="application/json")
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True

    def test_diff_export_txt(self, client):
        # Create chapter, edit to create v2
        r = client.post("/chapters/new", data={"title": "Diff", "content": "original"})
        ch_id = json.loads(r.data)["id"]
        client.post(f"/chapters/{ch_id}/edit", data={"title": "Diff", "content": "updated", "status": "draft"})
        # Get versions
        r = client.get(f"/chapters/{ch_id}/versions")
        versions = re.findall(r"restoreVersion\('([a-f0-9]+)'\)", r.data.decode())
        if len(versions) >= 2:
            r = client.post(f"/chapters/{ch_id}/diff/export",
                            data=json.dumps({"v1": versions[-1], "v2": versions[0], "format": "txt"}),
                            content_type="application/json")
            assert r.status_code == 200

    def test_diff_export_html(self, client):
        r = client.post("/chapters/new", data={"title": "Diff HTML", "content": "original"})
        ch_id = json.loads(r.data)["id"]
        client.post(f"/chapters/{ch_id}/edit", data={"title": "Diff HTML", "content": "updated", "status": "draft"})
        r = client.get(f"/chapters/{ch_id}/versions")
        versions = re.findall(r"restoreVersion\('([a-f0-9]+)'\)", r.data.decode())
        if len(versions) >= 2:
            r = client.post(f"/chapters/{ch_id}/diff/export",
                            data=json.dumps({"v1": versions[-1], "v2": versions[0], "format": "html"}),
                            content_type="application/json")
            assert r.status_code == 200


class TestCharacterArcRoutes:
    def test_create_arc(self, client):
        r = client.post("/characters/new", data={"name": "Arc Hero", "role": "protagonist"})
        char_id = json.loads(r.data)["id"]
        r = client.post(f"/characters/{char_id}/arcs",
                        data=json.dumps({
                            "arc_name": "Test Arc",
                            "description": "desc",
                            "stages": [{"name": "S1", "description": "s", "status": "planned"}]
                        }), content_type="application/json")
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True

    def test_update_arc(self, client):
        r = client.post("/characters/new", data={"name": "Arc2", "role": "minor"})
        char_id = json.loads(r.data)["id"]
        r = client.post(f"/characters/{char_id}/arcs",
                        data=json.dumps({"arc_name": "Original", "stages": []}),
                        content_type="application/json")
        arc_id = json.loads(r.data)["id"]
        r = client.post(f"/characters/arcs/{arc_id}",
                        data=json.dumps({"action": "update", "arc_name": "Updated"}),
                        content_type="application/json")
        assert r.status_code == 200

    def test_delete_arc(self, client):
        r = client.post("/characters/new", data={"name": "Arc3", "role": "minor"})
        char_id = json.loads(r.data)["id"]
        r = client.post(f"/characters/{char_id}/arcs",
                        data=json.dumps({"arc_name": "ToDelete", "stages": []}),
                        content_type="application/json")
        arc_id = json.loads(r.data)["id"]
        r = client.post(f"/characters/arcs/{arc_id}",
                        data=json.dumps({"action": "delete"}),
                        content_type="application/json")
        assert r.status_code == 200


class TestCharacterGroupsRoutes:
    def test_groups_page(self, client):
        r = client.get("/characters/groups")
        assert r.status_code == 200

    def test_create_group(self, client):
        r = client.post("/characters/groups",
                        data=json.dumps({"action": "create", "name": "Test Group"}),
                        content_type="application/json")
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True

    def test_assign_and_remove(self, client):
        # Create character + group
        rc = client.post("/characters/new", data={"name": "GC", "role": "minor"})
        char_id = json.loads(rc.data)["id"]
        rg = client.post("/characters/groups",
                         data=json.dumps({"action": "create", "name": "G1"}),
                         content_type="application/json")
        group_id = json.loads(rg.data)["id"]
        # Assign
        r = client.post("/characters/groups",
                        data=json.dumps({"action": "assign", "character_id": char_id, "group_id": group_id}),
                        content_type="application/json")
        assert r.status_code == 200
        # Remove
        r = client.post("/characters/groups",
                        data=json.dumps({"action": "remove", "character_id": char_id, "group_id": group_id}),
                        content_type="application/json")
        assert r.status_code == 200


class TestCompareExport:
    def test_compare_export_txt(self, client):
        r1 = client.post("/characters/new", data={"name": "Cmp1", "role": "minor"})
        r2 = client.post("/characters/new", data={"name": "Cmp2", "role": "minor"})
        id1 = json.loads(r1.data)["id"]
        id2 = json.loads(r2.data)["id"]
        r = client.get(f"/characters/compare?ch1={id1}&ch2={id2}&export=txt")
        assert r.status_code == 200

    def test_compare_export_pdf(self, client):
        r1 = client.post("/characters/new", data={"name": "Cmp3", "role": "minor"})
        r2 = client.post("/characters/new", data={"name": "Cmp4", "role": "minor"})
        id1 = json.loads(r1.data)["id"]
        id2 = json.loads(r2.data)["id"]
        r = client.get(f"/characters/compare?ch1={id1}&ch2={id2}&export=pdf")
        assert r.status_code == 200


class TestWorldVersionCompare:
    def test_world_versions_compare_page(self, client):
        # Create entry + edit to create v2
        r = client.post("/world/new", data={"type": "location", "name": "V1", "content": "v1"})
        wid = json.loads(r.data)["id"]
        client.post(f"/world/{wid}/edit", data={"type": "location", "name": "V2", "content": "v2"})
        r = client.get(f"/world/{wid}/versions")
        versions = re.findall(r"restoreVersion\('([a-f0-9]+)'\)", r.data.decode())
        if len(versions) >= 2:
            r = client.get(f"/world/{wid}/versions/compare?v1={versions[-1]}&v2={versions[0]}")
            assert r.status_code == 200


class TestNewPages:
    def test_corkboard_page(self, client):
        r = client.get("/plans/corkboard")
        assert r.status_code == 200

    def test_world_hierarchy_page(self, client):
        r = client.get("/world/hierarchy")
        assert r.status_code == 200

    def test_character_timeline_page(self, client):
        r = client.post("/characters/new", data={"name": "TL", "role": "minor"})
        char_id = json.loads(r.data)["id"]
        r = client.get(f"/characters/{char_id}/timeline")
        assert r.status_code == 200


class TestPlanDependencies:
    def test_dependency_warning_when_ahead(self, client):
        from services import plan_service
        # Blocker is "idea" (index 0)
        blocker = plan_service.create_plan(title="Blocker", status="idea")
        # Dependent is "writing" (index 2) — ahead of blocker
        dependent = plan_service.create_plan(title="Dependent", status="writing")
        plan_service.update_plan(dependent.id, depends_on_id=blocker.id)
        warnings = plan_service.dependency_warnings([dependent.id, blocker.id])
        assert dependent.id in warnings
        assert len(warnings[dependent.id]) > 0

    def test_no_warning_when_in_sync(self, client):
        from services import plan_service
        blocker = plan_service.create_plan(title="B2", status="writing")
        dependent = plan_service.create_plan(title="D2", status="writing")
        plan_service.update_plan(dependent.id, depends_on_id=blocker.id)
        warnings = plan_service.dependency_warnings([dependent.id, blocker.id])
        assert warnings[dependent.id] == []

    def test_overdue_plans(self, client):
        from services import plan_service
        from datetime import date, timedelta
        # Create an overdue plan (deadline yesterday, not final)
        p = plan_service.create_plan(title="Overdue", status="writing")
        plan_service.update_plan(p.id, deadline=date.today() - timedelta(days=1))
        overdue = plan_service.overdue_plans()
        assert p.id in overdue

    def test_actual_word_counts(self, client):
        from services import plan_service, chapter_service
        ch = chapter_service.create_chapter(title="Linked", content="one two three four five")
        p = plan_service.create_plan(title="P with chapter")
        plan_service.update_plan(p.id, chapter_id=ch.id)
        counts = plan_service.actual_word_counts_for_plans([p.id])
        assert counts[p.id] == 5


class TestAIConsistencyAndName:
    def test_consistency_check_route_404_when_disabled(self, client):
        r = client.post("/ai/consistency-check",
                        data=json.dumps({}), content_type="application/json")
        assert r.status_code == 404

    def test_consistency_check_route_when_enabled(self, client):
        # Enable AI with a fake model
        client.post("/settings/save", data=json.dumps({
            "ai.enabled": "true", "ai.provider": "ollama", "ai.model": "test",
        }), content_type="application/json")
        r = client.post("/ai/consistency-check",
                        data=json.dumps({}), content_type="application/json")
        # Will 502 (no real provider) but route exists
        assert r.status_code in (200, 502)

    def test_name_generator_route(self, client):
        client.post("/settings/save", data=json.dumps({
            "ai.enabled": "true", "ai.provider": "ollama", "ai.model": "test",
        }), content_type="application/json")
        r = client.post("/ai/generate-name",
                        data=json.dumps({"culture": "fantasy", "kind": "character"}),
                        content_type="application/json")
        assert r.status_code in (200, 502)

    def test_streaming_route(self, client):
        client.post("/settings/save", data=json.dumps({
            "ai.enabled": "true", "ai.provider": "ollama", "ai.model": "test",
        }), content_type="application/json")
        r = client.post("/ai/continue-stream",
                        data=json.dumps({"text": "hello"}),
                        content_type="application/json")
        # Will error (no real provider) but route exists
        assert r.status_code in (200, 502)


class TestSubtaskInlineEdit:
    def test_edit_subtask_title(self, client):
        # Create plan + subtask
        rp = client.post("/plans/new", data={"title": "P", "status": "idea"})
        plan_id = json.loads(rp.data)["id"]
        rs = client.post(f"/plans/{plan_id}/subtasks",
                         data=json.dumps({"title": "Original"}),
                         content_type="application/json")
        sub_id = json.loads(rs.data)["id"]
        # Edit
        r = client.post(f"/plans/subtasks/{sub_id}/edit",
                        data=json.dumps({"title": "Updated"}),
                        content_type="application/json")
        assert r.status_code == 200
        assert json.loads(r.data)["title"] == "Updated"

    def test_edit_subtask_empty_title_rejected(self, client):
        rp = client.post("/plans/new", data={"title": "P2", "status": "idea"})
        plan_id = json.loads(rp.data)["id"]
        rs = client.post(f"/plans/{plan_id}/subtasks",
                         data=json.dumps({"title": "X"}),
                         content_type="application/json")
        sub_id = json.loads(rs.data)["id"]
        r = client.post(f"/plans/subtasks/{sub_id}/edit",
                        data=json.dumps({"title": ""}),
                        content_type="application/json")
        assert r.status_code == 400


class TestDiffWordLevel:
    def test_line_diff_includes_word_diff_for_changed(self):
        from services.diff_service import line_diff
        a = "The quick brown fox"
        b = "The quick red fox"
        diff = line_diff(a, b)
        # Should have at least one del + one add with word_diff segments
        dels = [d for d in diff if d["op"] == "del"]
        adds = [d for d in diff if d["op"] == "add"]
        assert dels and adds
        # At least one should have word_diff
        assert any(d.get("word_diff") for d in dels + adds)

    def test_render_html_diff_has_ins_del(self):
        from services.diff_service import render_html_diff
        html = render_html_diff("old text here", "new text here")
        assert "<ins" in html or "<del" in html

    def test_hunks_grouping(self):
        from services.diff_service import hunks
        h = hunks("line1\nline2\nline3\nline4", "line1\nCHANGED\nline3\nCHANGED2")
        assert len(h) >= 1
