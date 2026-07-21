"""Focused tests for v4.8: character arcs, forecast, habits.

Critical paths only.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Character Arc Tracker
# ---------------------------------------------------------------------------

class TestCharacterArcs:
    def test_create_arc(self, client):
        from services.character_service import create_character
        c = create_character(name="Arc Hero", role="protagonist")
        r = client.post("/character-arcs/api/new", json={
            "character_id": c.id, "arc_name": "Redemption Arc",
            "description": "From villain to hero",
        })
        assert r.status_code == 200
        assert r.get_json()["ok"]

    def test_create_arc_no_character(self, client):
        r = client.post("/character-arcs/api/new", json={
            "character_id": "nonexistent", "arc_name": "Test",
        })
        assert r.status_code == 404

    def test_add_and_update_stage(self, client):
        from services.character_service import create_character
        from services.character_arc_service import create_arc, add_stage, update_stage, get_arc, to_dict
        c = create_character(name="Stage Hero", role="protagonist")
        arc = create_arc(character_id=c.id, arc_name="Growth")
        add_stage(arc.id, name="Call to adventure", status="planned")
        d = to_dict(get_arc(arc.id))
        assert d["stage_count"] == 1
        update_stage(arc.id, 0, status="completed")
        d = to_dict(get_arc(arc.id))
        assert d["completed_stages"] == 1
        assert d["progress_pct"] == 100.0

    def test_progress_calculation(self, client):
        from services.character_service import create_character
        from services.character_arc_service import create_arc, add_stage, get_arc, to_dict
        c = create_character(name="Progress Hero", role="protagonist")
        arc = create_arc(character_id=c.id, arc_name="Test")
        add_stage(arc.id, name="S1", status="completed")
        add_stage(arc.id, name="S2", status="active")
        add_stage(arc.id, name="S3", status="planned")
        d = to_dict(get_arc(arc.id))
        assert d["stage_count"] == 3
        assert d["completed_stages"] == 1
        assert d["progress_pct"] == 33.3
        assert d["current_stage"]["name"] == "S2"  # first non-completed

    def test_overall_status(self, client):
        from services.character_service import create_character
        from services.character_arc_service import create_arc, add_stage, get_arc, to_dict
        c = create_character(name="Status Hero", role="protagonist")
        arc = create_arc(character_id=c.id, arc_name="Test")
        add_stage(arc.id, name="S1", status="active")
        d = to_dict(get_arc(arc.id))
        assert d["overall_status"] == "active"
        arc2 = create_arc(character_id=c.id, arc_name="Completed")
        add_stage(arc2.id, name="S1", status="completed")
        d2 = to_dict(get_arc(arc2.id))
        assert d2["overall_status"] == "completed"

    def test_delete_arc(self, client):
        from services.character_service import create_character
        from services.character_arc_service import create_arc
        c = create_character(name="Delete Hero", role="protagonist")
        arc = create_arc(character_id=c.id, arc_name="Test")
        r = client.post(f"/character-arcs/api/{arc.id}/delete")
        assert r.get_json()["ok"]

    def test_index_renders(self, client):
        r = client.get("/character-arcs/")
        assert r.status_code == 200
        assert b"Character Arc" in r.data

    def test_stats(self, client):
        r = client.get("/character-arcs/api/stats")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "total_arcs" in d


# ---------------------------------------------------------------------------
# Manuscript Forecast
# ---------------------------------------------------------------------------

class TestForecast:
    def test_index_renders(self, client):
        r = client.get("/forecast/")
        assert r.status_code == 200
        assert b"Forecast" in r.data

    def test_api_forecast(self, client):
        r = client.get("/forecast/api/forecast")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "total_words" in d
        assert "paces" in d
        assert "milestones" in d

    def test_forecast_with_words(self, client):
        # Create a chapter with words
        client.post("/chapters/new", data={
            "title": "Forecast Test", "content": " ".join(["word"] * 500), "status": "draft",
        })
        r = client.get("/forecast/api/forecast")
        d = r.get_json()
        assert d["total_words"] >= 500
        assert d["completion_pct"] > 0

    def test_paces_have_all_windows(self, client):
        r = client.get("/forecast/api/forecast")
        d = r.get_json()
        assert "7d" in d["paces"]
        assert "30d" in d["paces"]
        assert "90d" in d["paces"]

    def test_milestones_have_4_entries(self, client):
        r = client.get("/forecast/api/forecast")
        d = r.get_json()
        assert len(d["milestones"]) == 4  # 30/60/90/180 days


# ---------------------------------------------------------------------------
# Writing Habit Insights
# ---------------------------------------------------------------------------

class TestHabits:
    def test_index_renders(self, client):
        r = client.get("/habits/")
        assert r.status_code == 200
        assert b"Habit" in r.data

    def test_api_insights(self, client):
        r = client.get("/habits/api/insights")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "total_entries" in d
        assert "heatmap" in d

    def test_insights_with_activity(self, client):
        # Create a chapter to generate activity
        client.post("/chapters/new", data={
            "title": "Habit Test", "content": "Some content for habit analysis.", "status": "draft",
        })
        r = client.get("/habits/api/insights")
        d = r.get_json()
        assert d["total_entries"] >= 1
        assert d["total_words"] > 0

    def test_heatmap_is_7x24(self, client):
        r = client.get("/habits/api/insights")
        d = r.get_json()
        assert len(d["heatmap"]) == 7  # 7 days
        for row in d["heatmap"]:
            assert len(row) == 24  # 24 hours

    def test_days_param(self, client):
        r = client.get("/habits/api/insights?days=30")
        d = r.get_json()
        assert d["days_analyzed"] == 30


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

class TestV48Sidebar:
    def test_sidebar_has_character_arcs(self, client):
        r = client.get("/")
        assert b"Character Arcs" in r.data

    def test_sidebar_has_forecast(self, client):
        r = client.get("/")
        assert b"Manuscript Forecast" in r.data

    def test_sidebar_has_habits(self, client):
        r = client.get("/")
        assert b"Writing Habits" in r.data
