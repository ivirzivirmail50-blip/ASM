"""Focused tests for v4.9: milestones, rel_timeline, scrivener export.

Critical paths only.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------

class TestMilestones:
    def test_index_renders(self, client):
        r = client.get("/milestones/")
        assert r.status_code == 200
        assert b"Milestone" in r.data

    def test_api_status(self, client):
        r = client.get("/milestones/api/status")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "milestones" in d
        assert "total_words" in d
        assert len(d["milestones"]) == 12  # 12 defined milestones

    def test_api_check(self, client):
        r = client.post("/milestones/api/check")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "newly_celebrated" in d

    def test_milestone_reached_with_words(self, client):
        # Create a chapter with 1000+ words to trigger first milestone
        client.post("/chapters/new", data={
            "title": "Milestone Test",
            "content": " ".join(["word"] * 1001),
            "status": "draft",
        })
        r = client.post("/milestones/api/check")
        d = r.get_json()
        # First milestone (1K) should be reached
        first = next(m for m in d["milestones"] if m["key"] == "words_1k")
        assert first["reached"] is True

    def test_next_milestone_tracking(self, client):
        r = client.get("/milestones/api/status")
        d = r.get_json()
        assert d["next_milestone"] is not None or d["total_words"] >= 1_000_000

    def test_celebration_persists(self, client):
        # Create words, check, then check again — second time no newly celebrated
        client.post("/chapters/new", data={
            "title": "Persist Test",
            "content": " ".join(["word"] * 1001),
            "status": "draft",
        })
        r1 = client.post("/milestones/api/check")
        r2 = client.post("/milestones/api/check")
        # Second check should have fewer (or zero) newly celebrated
        assert len(r2.get_json()["newly_celebrated"]) <= len(r1.get_json()["newly_celebrated"])


# ---------------------------------------------------------------------------
# Relationship Timeline
# ---------------------------------------------------------------------------

class TestRelTimeline:
    def test_index_renders(self, client):
        r = client.get("/rel-timeline/")
        assert r.status_code == 200
        assert b"Relationship Timeline" in r.data

    def test_api_events(self, client):
        r = client.get("/rel-timeline/api/events")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert isinstance(d["events"], list)

    def test_add_relationship(self, client):
        from services.character_service import create_character
        c1 = create_character(name="Hero", role="protagonist")
        c2 = create_character(name="Villain", role="antagonist")
        r = client.post("/rel-timeline/api/add", json={
            "from_character_id": c1.id,
            "to_character_id": c2.id,
            "relationship_type": "enemy",
            "description": "They hate each other",
            "is_bidirectional": True,
        })
        assert r.status_code == 200
        assert r.get_json()["ok"]

    def test_self_relationship_rejected(self, client):
        from services.character_service import create_character
        c = create_character(name="Self", role="protagonist")
        r = client.post("/rel-timeline/api/add", json={
            "from_character_id": c.id,
            "to_character_id": c.id,
            "relationship_type": "ally",
        })
        assert r.status_code == 400

    def test_matrix(self, client):
        r = client.get("/rel-timeline/api/matrix")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "characters" in d
        assert "matrix" in d

    def test_stats(self, client):
        r = client.get("/rel-timeline/api/stats")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "total" in d


# ---------------------------------------------------------------------------
# Scrivener Export
# ---------------------------------------------------------------------------

class TestScrivener:
    def test_index_renders(self, client):
        r = client.get("/scrivener/")
        assert r.status_code == 200
        assert b"Scrivener" in r.data

    def test_download(self, client):
        r = client.get("/scrivener/download")
        assert r.status_code == 200
        assert len(r.data) > 100  # non-empty ZIP

    def test_download_with_chapters(self, client):
        client.post("/chapters/new", data={
            "title": "Scriv Test", "content": "Content for Scrivener.", "status": "draft",
        })
        r = client.get("/scrivener/download")
        assert r.status_code == 200
        # Should be larger with chapter content
        assert len(r.data) > 500

    def test_download_with_status_filter(self, client):
        client.post("/chapters/new", data={
            "title": "Final Ch", "content": "Final content.", "status": "final",
        })
        r = client.get("/scrivener/download?status=final")
        assert r.status_code == 200

    def test_zip_contains_scrtext(self, client):
        import zipfile
        import io
        client.post("/chapters/new", data={
            "title": "Zip Test", "content": "Zip content.", "status": "draft",
        })
        r = client.get("/scrivener/download")
        zf = zipfile.ZipFile(io.BytesIO(r.data))
        names = zf.namelist()
        # Should contain at least one .scrtext file
        assert any(".scrtext" in n for n in names)
        # Should contain binder.xml
        assert any("binder.xml" in n for n in names)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

class TestV49Sidebar:
    def test_sidebar_has_milestones(self, client):
        r = client.get("/")
        assert b"Milestones" in r.data

    def test_sidebar_has_rel_timeline(self, client):
        r = client.get("/")
        assert b"Relationship Timeline" in r.data

    def test_sidebar_has_scrivener(self, client):
        r = client.get("/")
        assert b"Scrivener" in r.data
