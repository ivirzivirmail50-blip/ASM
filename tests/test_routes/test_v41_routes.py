"""Route tests for v4.1 modules: inspiration, plot_templates, notes."""
import json
import pytest


class TestInspirationRoutes:
    def test_index_renders(self, client):
        r = client.get("/inspiration/")
        assert r.status_code == 200
        assert b"Inspiration Hub" in r.data
        assert b"Prompt of the Day" in r.data

    def test_daily_api(self, client):
        r = client.get("/inspiration/api/daily")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert d["daily"]["text"]
        assert d["daily"]["category"]
        assert d["daily"]["date"]

    def test_random_api(self, client):
        r = client.get("/inspiration/api/random")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert d["prompt"]["text"]
        assert d["prompt"]["category"] in (
            "opening", "conflict", "character", "setting", "twist",
            "dialogue", "whatif",
        )

    def test_random_api_with_category(self, client):
        r = client.get("/inspiration/api/random?category=conflict")
        d = r.get_json()
        assert d["prompt"]["category"] == "conflict"

    def test_scenario_api(self, client):
        r = client.get("/inspiration/api/scenario")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        s = d["scenario"]
        assert s["prose"]
        for k in ("protagonist", "setting", "goal", "obstacle", "twist"):
            assert k in s["parts"]

    def test_whatif_api(self, client):
        r = client.get("/inspiration/api/whatif")
        d = r.get_json()
        assert d["prompt"]["category"] == "whatif"

    def test_prompts_for_category(self, client):
        r = client.get("/inspiration/api/prompts/opening")
        d = r.get_json()
        assert d["category"] == "opening"
        assert len(d["prompts"]) >= 5

    def test_save_and_list_flow(self, client):
        r = client.post("/inspiration/api/save", json={
            "kind": "prompt", "category": "opening", "body": "Test prompt body",
        })
        assert r.status_code == 200
        assert r.get_json()["ok"]

    def test_pin_unpin_flow(self, client):
        r = client.post("/inspiration/api/save", json={
            "kind": "scenario", "category": "combo", "body": "scenario body",
        })
        sid = r.get_json()["id"]
        r = client.post(f"/inspiration/api/{sid}/pin")
        assert r.get_json()["pinned"] is True
        r = client.post(f"/inspiration/api/{sid}/pin")
        assert r.get_json()["pinned"] is False

    def test_mark_used(self, client):
        r = client.post("/inspiration/api/save", json={
            "kind": "prompt", "category": "x", "body": "y",
        })
        sid = r.get_json()["id"]
        r = client.post(f"/inspiration/api/{sid}/used")
        assert r.get_json()["used"] is True

    def test_delete(self, client):
        r = client.post("/inspiration/api/save", json={
            "kind": "prompt", "category": "x", "body": "y",
        })
        sid = r.get_json()["id"]
        r = client.post(f"/inspiration/api/{sid}/delete")
        assert r.get_json()["ok"] is True

    def test_save_invalid_kind_returns_400(self, client):
        r = client.post("/inspiration/api/save", json={
            "kind": "bogus", "category": "x", "body": "y",
        })
        assert r.status_code == 400


class TestPlotTemplatesRoutes:
    def test_index_renders(self, client):
        r = client.get("/plot-templates/")
        assert r.status_code == 200
        assert b"Plot Structure Templates" in r.data
        assert b"Hero" in r.data
        assert b"Save the Cat" in r.data

    def test_detail_renders(self, client):
        r = client.get("/plot-templates/heros_journey")
        assert r.status_code == 200
        assert b"Ordinary World" in r.data
        assert b"Return with the Elixir" in r.data

    def test_detail_unknown_template_404(self, client):
        r = client.get("/plot-templates/bogus")
        assert r.status_code == 404

    def test_apply_creates_plans(self, client):
        r = client.post("/plot-templates/api/apply", json={"key": "three_act"})
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert d["beats_created"] == 7
        assert d["track"] == "plot:three_act"

    def test_apply_invalid_key_returns_400(self, client):
        r = client.post("/plot-templates/api/apply", json={"key": "bogus"})
        assert r.status_code == 400

    def test_apply_creates_track_visible_in_outline(self, client):
        client.post("/plot-templates/api/apply", json={"key": "freytag"})
        # Outline should now show plot:freytag as a track
        r = client.get("/plans/outline")
        assert r.status_code == 200


class TestNotesRoutes:
    def test_index_renders(self, client):
        r = client.get("/notes/")
        assert r.status_code == 200
        assert b"Notes & Ideas Inbox" in r.data

    def test_create_note(self, client):
        r = client.post("/notes/api/new", json={
            "title": "Test note",
            "body": "Note body",
            "category": "idea",
        })
        assert r.status_code == 200
        assert r.get_json()["ok"]

    def test_create_invalid_category_returns_400(self, client):
        r = client.post("/notes/api/new", json={
            "title": "x", "body": "y", "category": "bogus",
        })
        assert r.status_code == 400

    def test_create_empty_returns_400(self, client):
        r = client.post("/notes/api/new", json={
            "title": "", "body": "", "category": "idea",
        })
        assert r.status_code == 400

    def test_list_api(self, client):
        client.post("/notes/api/new", json={
            "title": "A", "body": "", "category": "idea",
        })
        client.post("/notes/api/new", json={
            "title": "B", "body": "", "category": "todo",
        })
        r = client.get("/notes/api/list")
        d = r.get_json()
        assert d["ok"]
        assert len(d["notes"]) >= 2

    def test_update_note(self, client):
        r = client.post("/notes/api/new", json={
            "title": "Old", "body": "old", "category": "idea",
        })
        nid = r.get_json()["id"]
        r = client.post(f"/notes/api/{nid}", json={"title": "New", "body": "new"})
        assert r.get_json()["ok"]

    def test_pin_toggle(self, client):
        r = client.post("/notes/api/new", json={
            "title": "x", "body": "", "category": "idea",
        })
        nid = r.get_json()["id"]
        r = client.post(f"/notes/api/{nid}/pin")
        assert r.get_json()["pinned"] is True
        r = client.post(f"/notes/api/{nid}/pin")
        assert r.get_json()["pinned"] is False

    def test_done_toggle(self, client):
        r = client.post("/notes/api/new", json={
            "title": "x", "body": "", "category": "todo",
        })
        nid = r.get_json()["id"]
        r = client.post(f"/notes/api/{nid}/done")
        assert r.get_json()["done"] is True

    def test_add_link(self, client):
        r = client.post("/notes/api/new", json={
            "title": "x", "body": "", "category": "idea",
        })
        nid = r.get_json()["id"]
        r = client.post(f"/notes/api/{nid}/link", json={
            "entity_type": "chapter", "entity_id": "ch1", "entity_title": "Ch 1",
        })
        d = r.get_json()
        assert d["ok"]
        assert len(d["links"]) == 1

    def test_add_invalid_link_returns_400(self, client):
        r = client.post("/notes/api/new", json={
            "title": "x", "body": "", "category": "idea",
        })
        nid = r.get_json()["id"]
        r = client.post(f"/notes/api/{nid}/link", json={
            "entity_type": "bogus", "entity_id": "x", "entity_title": "y",
        })
        assert r.status_code == 400

    def test_remove_link(self, client):
        r = client.post("/notes/api/new", json={
            "title": "x", "body": "", "category": "idea",
        })
        nid = r.get_json()["id"]
        client.post(f"/notes/api/{nid}/link", json={
            "entity_type": "chapter", "entity_id": "ch1", "entity_title": "Ch 1",
        })
        r = client.post(f"/notes/api/{nid}/link/ch1/delete")
        d = r.get_json()
        assert d["ok"]
        assert len(d["links"]) == 0

    def test_promote_chapter(self, client):
        r = client.post("/notes/api/new", json={
            "title": "Chapter me", "body": "Body", "category": "scene_idea",
        })
        nid = r.get_json()["id"]
        r = client.post(f"/notes/api/{nid}/promote/chapter")
        d = r.get_json()
        assert d["ok"]
        assert d["chapter_id"]

    def test_promote_snippet(self, client):
        r = client.post("/notes/api/new", json={
            "title": "Snip", "body": "Body", "category": "idea",
        })
        nid = r.get_json()["id"]
        r = client.post(f"/notes/api/{nid}/promote/snippet")
        assert r.get_json()["ok"]

    def test_promote_plan(self, client):
        r = client.post("/notes/api/new", json={
            "title": "Plan", "body": "Body", "category": "todo",
        })
        nid = r.get_json()["id"]
        r = client.post(f"/notes/api/{nid}/promote/plan")
        assert r.get_json()["ok"]

    def test_delete_note(self, client):
        r = client.post("/notes/api/new", json={
            "title": "x", "body": "", "category": "idea",
        })
        nid = r.get_json()["id"]
        r = client.post(f"/notes/api/{nid}/delete")
        assert r.get_json()["ok"] is True

    def test_index_with_search_query(self, client):
        client.post("/notes/api/new", json={
            "title": "Findable", "body": "x", "category": "idea",
        })
        client.post("/notes/api/new", json={
            "title": "Other", "body": "x", "category": "idea",
        })
        r = client.get("/notes/?q=Findable")
        assert r.status_code == 200
        assert b"Findable" in r.data

    def test_index_with_category_filter(self, client):
        client.post("/notes/api/new", json={
            "title": "Idea1", "body": "", "category": "idea",
        })
        client.post("/notes/api/new", json={
            "title": "Todo1", "body": "", "category": "todo",
        })
        r = client.get("/notes/?category=todo")
        assert r.status_code == 200
        assert b"Todo1" in r.data


class TestNewSidebarEntries:
    """Verify the sidebar exposes the new v4.1 modules."""

    def test_sidebar_has_inspiration(self, client):
        r = client.get("/")
        assert b"Inspiration Hub" in r.data

    def test_sidebar_has_plot_templates(self, client):
        r = client.get("/")
        assert b"Plot Structures" in r.data

    def test_sidebar_has_notes(self, client):
        r = client.get("/")
        assert b"Notes & Ideas" in r.data

    def test_sidebar_has_shortcuts_button(self, client):
        r = client.get("/")
        assert b"Keyboard shortcuts" in r.data

    def test_version_bumped_to_41(self, client):
        r = client.get("/")
        assert b"v4.1" in r.data
