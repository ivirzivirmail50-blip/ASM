"""Route integration tests: every GET + POST flow."""
import json
import re
import io
import pytest


def get_id(html: bytes, pattern: str) -> str | None:
    m = re.search(pattern, html.decode())
    return m.group(1) if m else None


class TestDashboard:
    def test_dashboard_renders(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert b"Story Cockpit" in r.data

    def test_dashboard_shows_zero_state_when_empty(self, client):
        r = client.get("/")
        assert b"Total Chapters" in r.data
        assert b"0" in r.data  # zero chapters


class TestChaptersRoutes:
    def test_list_renders(self, client):
        r = client.get("/chapters/")
        assert r.status_code == 200

    def test_new_form_renders(self, client):
        r = client.get("/chapters/new")
        assert r.status_code == 200
        assert b"Title" in r.data

    def test_create_chapter(self, client):
        r = client.post("/chapters/new", data={
            "title": "Route Test Chapter",
            "content": "Some content for testing.",
            "status": "draft",
        })
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["ok"] is True
        assert data["id"]
        assert data["url"].endswith(data["id"])

    def test_create_chapter_validation_error(self, client):
        r = client.post("/chapters/new", data={"title": "", "content": "x"})
        assert r.status_code == 400

    def test_chapter_detail_404(self, client):
        r = client.get("/chapters/nonexistent-id")
        assert r.status_code == 404

    def test_chapter_lifecycle(self, client):
        # Create → edit → cycle-status → delete
        r = client.post("/chapters/new", data={
            "title": "Lifecycle", "content": "v1 content", "status": "draft",
        })
        ch_id = json.loads(r.data)["id"]

        # Detail
        r = client.get(f"/chapters/{ch_id}")
        assert r.status_code == 200

        # Edit
        r = client.post(f"/chapters/{ch_id}/edit", data={
            "title": "Lifecycle v2", "content": "v2 content", "status": "draft",
        })
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True

        # Autosave (no version)
        r = client.post(f"/chapters/{ch_id}/autosave",
                        data=json.dumps({"content": "autosaved"}),
                        content_type="application/json")
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True

        # Cycle status
        r = client.post(f"/chapters/{ch_id}/cycle-status",
                        data=json.dumps({}), content_type="application/json")
        assert r.status_code == 200
        assert json.loads(r.data)["status"] == "revised"

        # Delete
        r = client.post(f"/chapters/{ch_id}/delete",
                        data=json.dumps({}), content_type="application/json")
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True

    def test_upload_txt_file(self, client):
        r = client.post("/chapters/upload", data={
            "file": (io.BytesIO(b"Hello from uploaded file."), "test.txt"),
            "title": "Uploaded",
            "status": "draft",
        }, content_type="multipart/form-data")
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True

    def test_upload_rejects_bad_extension(self, client):
        r = client.post("/chapters/upload", data={
            "file": (io.BytesIO(b"binary"), "evil.exe"),
            "title": "Bad",
        }, content_type="multipart/form-data")
        assert r.status_code == 400

    def test_reorder(self, client):
        # Create two chapters first
        r1 = client.post("/chapters/new", data={"title": "A", "content": "a"})
        r2 = client.post("/chapters/new", data={"title": "B", "content": "b"})
        id1 = json.loads(r1.data)["id"]
        id2 = json.loads(r2.data)["id"]
        r = client.post("/chapters/reorder",
                        data=json.dumps({"order": [id2, id1]}),
                        content_type="application/json")
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True

    def test_export_formats(self, client):
        # Create a chapter with substantial content first
        r = client.post("/chapters/new", data={
            "title": "Export Test Chapter",
            "content": "This is the content of the export test chapter. " * 10,
        })
        ch_id = json.loads(r.data)["id"]
        for fmt in ["txt", "md", "html", "docx", "pdf", "json"]:
            r = client.get(f"/chapters/{ch_id}/export/{fmt}")
            assert r.status_code == 200
            # Each format must return at least some bytes
            assert len(r.data) > 5


class TestCharactersRoutes:
    def test_list_renders(self, client):
        r = client.get("/characters/")
        assert r.status_code == 200

    def test_graph_renders(self, client):
        r = client.get("/characters/graph")
        assert r.status_code == 200
        assert b"character-graph" in r.data or b"vis-network" in r.data

    def test_graph_data_returns_json(self, client):
        r = client.get("/characters/graph/data")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "nodes" in data
        assert "edges" in data
        assert "groups" in data

    def test_create_character(self, client):
        r = client.post("/characters/new", data={
            "name": "Test Character",
            "role": "protagonist",
            "age": "25",
            "gender": "Female",
        })
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True

    def test_relationship_crud(self, client):
        # Create two characters
        r1 = client.post("/characters/new", data={"name": "A", "role": "minor"})
        r2 = client.post("/characters/new", data={"name": "B", "role": "minor"})
        a_id = json.loads(r1.data)["id"]
        b_id = json.loads(r2.data)["id"]
        # Create relationship
        r = client.post("/characters/relationships/new",
                        data=json.dumps({
                            "from_id": a_id, "to_id": b_id,
                            "type": "friend_of", "bidirectional": True,
                        }), content_type="application/json")
        assert r.status_code == 200
        rel_id = json.loads(r.data)["id"]
        # Delete relationship
        r = client.post(f"/characters/relationships/{rel_id}/delete",
                        data=json.dumps({}), content_type="application/json")
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True

    def test_save_graph_position(self, client):
        r = client.post("/characters/new", data={"name": "Pinned", "role": "minor"})
        ch_id = json.loads(r.data)["id"]
        r = client.post("/characters/graph/save-position",
                        data=json.dumps({"id": ch_id, "x": 100, "y": 200}),
                        content_type="application/json")
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True

    def test_timeline_route(self, client):
        r = client.post("/characters/new", data={"name": "Timelined", "role": "minor"})
        ch_id = json.loads(r.data)["id"]
        r = client.get(f"/characters/{ch_id}/timeline")
        assert r.status_code == 200
        assert b"Timeline" in r.data


class TestPlansRoutes:
    def test_board_renders(self, client):
        r = client.get("/plans/")
        assert r.status_code == 200
        assert b"kanban" in r.data.lower() or b"Kanban" in r.data

    def test_outline_renders(self, client):
        r = client.get("/plans/outline")
        assert r.status_code == 200

    def test_timeline_renders(self, client):
        r = client.get("/plans/timeline")
        assert r.status_code == 200

    def test_create_plan(self, client):
        r = client.post("/plans/new", data={
            "title": "Test Plan",
            "status": "idea",
            "track": "Main Plot",
        })
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True

    def test_subtask_crud(self, client):
        # Create plan
        r = client.post("/plans/new", data={"title": "With Subs", "status": "idea"})
        plan_id = json.loads(r.data)["id"]
        # Add subtask
        r = client.post(f"/plans/{plan_id}/subtasks",
                        data=json.dumps({"title": "Sub 1"}),
                        content_type="application/json")
        assert r.status_code == 200
        sub_id = json.loads(r.data)["id"]
        # Toggle
        r = client.post(f"/plans/subtasks/{sub_id}/toggle",
                        data=json.dumps({}), content_type="application/json")
        assert r.status_code == 200
        assert json.loads(r.data)["completed"] is True
        # Reorder
        r = client.post(f"/plans/{plan_id}/subtasks/reorder",
                        data=json.dumps({"order": [sub_id]}),
                        content_type="application/json")
        assert r.status_code == 200
        # Delete
        r = client.post(f"/plans/subtasks/{sub_id}/delete",
                        data=json.dumps({}), content_type="application/json")
        assert r.status_code == 200

    def test_reorder_nested(self, client):
        r1 = client.post("/plans/new", data={"title": "P1", "status": "idea"})
        r2 = client.post("/plans/new", data={"title": "P2", "status": "idea"})
        p1 = json.loads(r1.data)["id"]
        p2 = json.loads(r2.data)["id"]
        r = client.post("/plans/reorder-nested",
                        data=json.dumps({"items": [
                            {"id": p1, "parent_id": None, "sort_order": 1},
                            {"id": p2, "parent_id": p1, "sort_order": 1},
                        ]}), content_type="application/json")
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True


class TestWorldRoutes:
    def test_index_renders(self, client):
        r = client.get("/world/")
        assert r.status_code == 200

    def test_map_renders(self, client):
        r = client.get("/world/map")
        assert r.status_code == 200

    def test_create_entry(self, client):
        r = client.post("/world/new", data={
            "type": "location",
            "name": "Test City",
            "category": "Capital",
            "description": "A test city",
            "content": "City content.",
        })
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True

    def test_pin_set_and_remove(self, client):
        r = client.post("/world/new", data={
            "type": "location", "name": "Mapped", "content": "x",
        })
        wid = json.loads(r.data)["id"]
        # Set
        r = client.post("/world/map/pin",
                        data=json.dumps({"id": wid, "x": 50.0, "y": 30.0}),
                        content_type="application/json")
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True
        # Remove (null coords)
        r = client.post("/world/map/pin",
                        data=json.dumps({"id": wid, "x": None, "y": None}),
                        content_type="application/json")
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True

    def test_duplicate_entry(self, client):
        r = client.post("/world/new", data={
            "type": "lore", "name": "Original", "content": "x",
        })
        wid = json.loads(r.data)["id"]
        r = client.post(f"/world/{wid}/duplicate",
                        data=json.dumps({}), content_type="application/json")
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True


class TestSearchRoutes:
    def test_search_empty(self, client):
        r = client.get("/search/")
        assert r.status_code == 200

    def test_search_with_query(self, client):
        # Create some content first
        client.post("/chapters/new", data={
            "title": "Searchable Chapter",
            "content": "Contains unique keyword velociraptor.",
        })
        r = client.get("/search/?q=velociraptor")
        assert r.status_code == 200


class TestSettingsRoutes:
    def test_settings_renders(self, client):
        r = client.get("/settings/")
        assert r.status_code == 200

    def test_save_settings(self, client):
        r = client.post("/settings/save",
                        data=json.dumps({"daily_word_goal": 1000, "theme": "light"}),
                        content_type="application/json")
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True

    def test_validate_renders(self, client):
        r = client.get("/settings/validate")
        assert r.status_code == 200

    def test_ai_settings_page(self, client):
        r = client.get("/settings/ai")
        assert r.status_code == 200

    def test_backup_list(self, client):
        r = client.get("/settings/backup")
        assert r.status_code == 200

    def test_create_backup(self, client):
        r = client.post("/settings/backup",
                        data=json.dumps({}), content_type="application/json")
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True


class TestExportRoutes:
    def test_manuscript_formats(self, client):
        for fmt in ["txt", "md", "html", "docx", "pdf", "epub"]:
            r = client.get(f"/export/manuscript/{fmt}")
            assert r.status_code == 200
            assert len(r.data) > 5

    def test_world_bible_formats(self, client):
        for fmt in ["txt", "pdf", "docx", "json"]:
            r = client.get(f"/export/world-bible/{fmt}")
            assert r.status_code == 200

    def test_full_project(self, client):
        for fmt in ["pdf", "docx"]:
            r = client.get(f"/export/full-project/{fmt}")
            assert r.status_code == 200

    def test_json_export(self, client):
        r = client.get("/settings/export-json")
        assert r.status_code == 200
        # Verify it strips API key
        data = json.loads(r.data)
        assert data["settings"]["ai.api_key"] == ""


class TestAIRoutes:
    def test_ai_status_disabled(self, client):
        r = client.get("/ai/status")
        assert r.status_code == 200
        assert json.loads(r.data)["enabled"] is False

    def test_ai_continue_returns_404_when_disabled(self, client):
        r = client.post("/ai/continue",
                        data=json.dumps({"text": "hello"}),
                        content_type="application/json")
        assert r.status_code == 404

    def test_ai_status_enabled_after_setting(self, client):
        client.post("/settings/save", data=json.dumps({
            "ai.enabled": "true",
            "ai.provider": "ollama",
            "ai.model": "llama3",
        }), content_type="application/json")
        r = client.get("/ai/status")
        assert json.loads(r.data)["enabled"] is True


class TestErrorPages:
    def test_404(self, client):
        r = client.get("/nonexistent-route-xyz")
        assert r.status_code == 404

    def test_chapter_detail_404(self, client):
        r = client.get("/chapters/nonexistent-id")
        assert r.status_code == 404

    def test_character_detail_404(self, client):
        r = client.get("/characters/nonexistent-id")
        assert r.status_code == 404
