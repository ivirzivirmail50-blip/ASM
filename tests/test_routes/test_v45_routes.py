"""Route tests for v4.5 modules: achievements, goals_calendar, story_bible, spellcheck."""
import json
import pytest


class TestAchievementsRoutes:
    def test_index_renders(self, client):
        r = client.get("/achievements/")
        assert r.status_code == 200
        assert b"Achievements" in r.data

    def test_api_check(self, client):
        r = client.post("/achievements/api/check")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "checked" in d
        assert "newly_unlocked" in d

    def test_api_status(self, client):
        r = client.get("/achievements/api/status")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "achievements" in d
        assert "unlocked_count" in d


class TestGoalsCalendarRoutes:
    def test_index_renders(self, client):
        r = client.get("/goals/")
        assert r.status_code == 200
        assert b"Goals Calendar" in r.data

    def test_index_with_year_month(self, client):
        r = client.get("/goals/?year=2026&month=7")
        assert r.status_code == 200

    def test_api_month(self, client):
        r = client.get("/goals/api/month/2026/7")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "weeks" in d

    def test_api_year(self, client):
        r = client.get("/goals/api/year/2026")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "months" in d
        assert len(d["months"]) == 12

    def test_api_progress(self, client):
        r = client.get("/goals/api/progress")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "today" in d
        assert "week" in d


class TestStoryBibleRoutes:
    def test_index_renders(self, client):
        r = client.get("/story-bible/")
        assert r.status_code == 200
        assert b"Story Bible" in r.data

    def test_api_data(self, client):
        r = client.get("/story-bible/api/data")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "data" in d
        assert "title" in d["data"]

    def test_download_html(self, client):
        r = client.get("/story-bible/download?format=html")
        assert r.status_code == 200
        assert b"<html" in r.data

    def test_download_txt(self, client):
        r = client.get("/story-bible/download?format=txt")
        assert r.status_code == 200

    def test_download_md(self, client):
        r = client.get("/story-bible/download?format=md")
        assert r.status_code == 200

    def test_download_json(self, client):
        r = client.get("/story-bible/download?format=json")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "title" in data

    def test_download_invalid_format(self, client):
        r = client.get("/story-bible/download?format=bogus")
        assert r.status_code == 400


class TestSpellCheckRoutes:
    def test_index_renders(self, client):
        r = client.get("/spellcheck/")
        assert r.status_code == 200
        assert b"Spell Check" in r.data

    def test_api_check_all(self, client):
        r = client.get("/spellcheck/api/check")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "chapters_checked" in d

    def test_api_add_word(self, client):
        r = client.post("/spellcheck/api/words/add", json={"word": "testword"})
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert d["word"] == "testword"

    def test_api_add_word_invalid(self, client):
        r = client.post("/spellcheck/api/words/add", json={"word": ""})
        assert r.status_code == 400

    def test_api_list_words(self, client):
        client.post("/spellcheck/api/words/add", json={"word": "listword"})
        r = client.get("/spellcheck/api/words")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert isinstance(d["words"], list)

    def test_api_add_batch(self, client):
        r = client.post("/spellcheck/api/words/add-batch", json={
            "words": ["batch_a", "batch_b", "batch_c"]
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert d["added"] >= 1

    def test_api_delete_word_by_text(self, client):
        client.post("/spellcheck/api/words/add", json={"word": "deletetest"})
        r = client.post("/spellcheck/api/words/by-text/deletetest/delete")
        assert r.status_code == 200
        assert r.get_json()["ok"]

    def test_check_single_chapter(self, client):
        # Create a chapter first
        r = client.post("/chapters/new", data={
            "title": "Spell Check Test", "content": "Some content here.", "status": "draft",
        })
        ch_id = json.loads(r.data)["id"]
        r = client.get(f"/spellcheck/api/check/{ch_id}")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "flagged" in d


class TestV45Sidebar:
    """Verify all v4.5 modules appear in the sidebar."""

    def test_sidebar_has_achievements(self, client):
        r = client.get("/")
        assert b"Achievements" in r.data

    def test_sidebar_has_goals_calendar(self, client):
        r = client.get("/")
        assert b"Goals Calendar" in r.data

    def test_sidebar_has_story_bible(self, client):
        r = client.get("/")
        assert b"Story Bible" in r.data

    def test_sidebar_has_spellcheck(self, client):
        r = client.get("/")
        assert b"Spell Check" in r.data
