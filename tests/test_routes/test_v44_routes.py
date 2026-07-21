"""Route tests for v4.4 modules: scenes, journal, compile, theme."""
import json
import pytest


class TestScenesRoutes:
    def test_index_renders(self, client):
        r = client.get("/scenes/")
        assert r.status_code == 200
        assert b"Scene Card Index" in r.data

    def test_api_extract_all(self, client):
        # Create a chapter first
        client.post("/chapters/new", data={
            "title": "Scene Test", "content": "Scene 1.\n\n\nScene 2.", "status": "draft",
        })
        r = client.post("/scenes/api/extract-all")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert d["total_scenes"] >= 2

    def test_api_list(self, client):
        r = client.get("/scenes/api/list")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert isinstance(d["cards"], list)

    def test_api_stats(self, client):
        r = client.get("/scenes/api/stats")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "total" in d

    def test_api_reorder(self, client):
        # Extract scenes from a fresh chapter
        r = client.post("/chapters/new", data={
            "title": "Reorder Test", "content": "S1.\n\n\nS2.", "status": "draft",
        })
        ch_id = json.loads(r.data)["id"]
        client.post(f"/scenes/api/extract/{ch_id}")
        cards = client.get("/scenes/api/list").get_json()["cards"]
        # Filter to only this chapter's cards
        ch_cards = [c for c in cards if c["chapter_id"] == ch_id]
        if len(ch_cards) >= 2:
            ids = [c["id"] for c in ch_cards]
            # Reverse the order
            reversed_ids = list(reversed(ids))
            r = client.post("/scenes/api/reorder", json={"card_ids": reversed_ids})
            assert r.status_code == 200
            assert r.get_json()["ok"]

    def test_api_extract_single_chapter(self, client):
        r = client.post("/chapters/new", data={
            "title": "Single Extract", "content": "Only scene.", "status": "draft",
        })
        ch_id = json.loads(r.data)["id"]
        r = client.post(f"/scenes/api/extract/{ch_id}")
        assert r.status_code == 200
        assert r.get_json()["ok"]


class TestJournalRoutes:
    def test_index_renders(self, client):
        r = client.get("/journal/")
        assert r.status_code == 200
        assert b"Writing Journal" in r.data

    def test_api_today(self, client):
        r = client.get("/journal/api/today")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert d["entry"] is not None

    def test_api_save(self, client):
        r = client.post("/journal/api/save", json={
            "entry_date": "2026-07-15",
            "mood": "good",
            "energy": 4,
            "wins": "Great day",
        })
        assert r.status_code == 200
        assert r.get_json()["ok"]

    def test_api_save_invalid_mood(self, client):
        r = client.post("/journal/api/save", json={
            "entry_date": "2026-07-15",
            "mood": "bogus",
        })
        assert r.status_code == 400

    def test_api_by_date(self, client):
        r = client.get("/journal/api/by-date/2026-07-15")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]

    def test_api_list(self, client):
        r = client.get("/journal/api/list")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert isinstance(d["entries"], list)

    def test_api_stats(self, client):
        r = client.get("/journal/api/stats")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "streak" in d

    def test_api_update(self, client):
        # Save an entry first
        client.post("/journal/api/save", json={
            "entry_date": "2026-07-14", "mood": "ok",
        })
        entries = client.get("/journal/api/list").get_json()["entries"]
        if entries:
            eid = entries[0]["id"]
            r = client.post(f"/journal/api/{eid}", json={"notes": "Updated"})
            assert r.status_code == 200
            assert r.get_json()["ok"]


class TestCompileRoutes:
    def test_index_renders(self, client):
        r = client.get("/compile/")
        assert r.status_code == 200
        assert b"Compile Wizard" in r.data

    def test_api_config_get(self, client):
        r = client.get("/compile/api/config")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "config" in d

    def test_api_config_save(self, client):
        r = client.post("/compile/api/config", json={
            "preset": "dark",
            "include_dedication": True,
            "dedication_text": "For my cat",
            "format": "html",
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert d["config"]["include_dedication"] is True

    def test_api_config_invalid_format(self, client):
        r = client.post("/compile/api/config", json={"format": "bogus"})
        assert r.status_code == 400

    def test_api_preview(self, client):
        # Create a chapter first
        client.post("/chapters/new", data={
            "title": "Compile Preview Test", "content": "Some content.", "status": "draft",
        })
        r = client.get("/compile/api/preview")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "sections" in d
        assert d["chapter_count"] >= 1

    def test_download_html(self, client):
        client.post("/chapters/new", data={
            "title": "Download HTML Test", "content": "Content.", "status": "draft",
        })
        r = client.get("/compile/download?format=html")
        assert r.status_code == 200
        assert b"<html" in r.data

    def test_download_txt(self, client):
        client.post("/chapters/new", data={
            "title": "Download TXT Test", "content": "Content.", "status": "draft",
        })
        r = client.get("/compile/download?format=txt")
        assert r.status_code == 200

    def test_download_md(self, client):
        client.post("/chapters/new", data={
            "title": "Download MD Test", "content": "Content.", "status": "draft",
        })
        r = client.get("/compile/download?format=md")
        assert r.status_code == 200


class TestThemeRoutes:
    def test_index_renders(self, client):
        r = client.get("/theme/")
        assert r.status_code == 200
        assert b"Theme" in r.data

    def test_api_config_get(self, client):
        r = client.get("/theme/api/config")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "config" in d

    def test_api_config_save(self, client):
        r = client.post("/theme/api/config", json={
            "preset": "sepia",
            "font_family": "Georgia, serif",
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert d["config"]["preset"] == "sepia"

    def test_api_config_invalid_preset(self, client):
        r = client.post("/theme/api/config", json={"preset": "bogus"})
        assert r.status_code == 400

    def test_api_css(self, client):
        r = client.get("/theme/api/css")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "css" in d

    def test_api_css_with_preview(self, client):
        r = client.get("/theme/api/css?preview=1&preset=forest")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]

    def test_api_reset(self, client):
        # Save something first
        client.post("/theme/api/config", json={"preset": "sepia"})
        r = client.post("/theme/api/reset")
        assert r.status_code == 200
        assert r.get_json()["ok"]
        # Verify reset
        config = client.get("/theme/api/config").get_json()["config"]
        assert config["preset"] == "dark"

    def test_theme_injected_into_page(self, client):
        # Save a custom theme
        client.post("/theme/api/config", json={"preset": "sepia"})
        r = client.get("/")
        assert b"custom-theme-css" in r.data


class TestV44Sidebar:
    """Verify all v4.4 modules appear in the sidebar."""

    def test_sidebar_has_scenes(self, client):
        r = client.get("/")
        assert b"Scene Cards" in r.data

    def test_sidebar_has_journal(self, client):
        r = client.get("/")
        assert b"Writing Journal" in r.data

    def test_sidebar_has_compile(self, client):
        r = client.get("/")
        assert b"Compile Wizard" in r.data

    def test_sidebar_has_theme_editor(self, client):
        r = client.get("/")
        assert b"Theme Editor" in r.data
