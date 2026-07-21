"""Focused tests for v4.7: beta threads, prompt calendar, chapter deps.

Critical paths only — not exhaustive.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Beta Comment Threads
# ---------------------------------------------------------------------------

class TestBetaThreads:
    def test_add_comment_and_reply(self, client):
        # Create chapter
        r = client.post("/chapters/new", data={
            "title": "Thread Test", "content": "Some text.", "status": "draft",
        })
        ch_id = r.get_json()["id"]
        # Add top-level comment
        r = client.post(f"/beta/{ch_id}/comment", json={
            "comment": "This is confusing", "reader_name": "Reader1",
        })
        assert r.status_code == 200
        cid = r.get_json()["id"]
        # Add reply
        r = client.post(f"/beta/comment/{cid}/reply", json={
            "comment": "Will fix", "reader_name": "Author",
        })
        assert r.status_code == 200
        assert r.get_json()["ok"]

    def test_threaded_view(self, client):
        r = client.post("/chapters/new", data={
            "title": "Threaded View", "content": "Text.", "status": "draft",
        })
        ch_id = r.get_json()["id"]
        client.post(f"/beta/{ch_id}/comment", json={"comment": "Top"})
        r = client.get(f"/beta/{ch_id}/threaded")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert len(d["comments"]) >= 1

    def test_resolve_and_reopen(self, client):
        r = client.post("/chapters/new", data={
            "title": "Resolve Test", "content": "Text.", "status": "draft",
        })
        ch_id = r.get_json()["id"]
        r = client.post(f"/beta/{ch_id}/comment", json={"comment": "Issue"})
        cid = r.get_json()["id"]
        # Resolve
        r = client.post(f"/beta/comment/{cid}/resolve")
        assert r.get_json()["status"] == "resolved"
        # Reopen
        r = client.post(f"/beta/comment/{cid}/reopen")
        assert r.get_json()["status"] == "open"

    def test_delete_comment_cascades_replies(self, client):
        r = client.post("/chapters/new", data={
            "title": "Delete Cascade", "content": "Text.", "status": "draft",
        })
        ch_id = r.get_json()["id"]
        r = client.post(f"/beta/{ch_id}/comment", json={"comment": "Parent"})
        cid = r.get_json()["id"]
        client.post(f"/beta/comment/{cid}/reply", json={"comment": "Reply"})
        # Delete parent — should succeed and cascade to reply
        r = client.post(f"/beta/comment/{cid}/delete")
        assert r.get_json()["ok"]
        # Verify parent is gone
        from services.beta_service import get_comment
        from core.errors import NotFoundError
        with pytest.raises(NotFoundError):
            get_comment(cid)

    def test_empty_reply_rejected(self, client):
        r = client.post("/chapters/new", data={
            "title": "Empty Reply", "content": "Text.", "status": "draft",
        })
        ch_id = r.get_json()["id"]
        r = client.post(f"/beta/{ch_id}/comment", json={"comment": "Top"})
        cid = r.get_json()["id"]
        r = client.post(f"/beta/comment/{cid}/reply", json={"comment": ""})
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Prompt Calendar
# ---------------------------------------------------------------------------

class TestPromptCalendar:
    def test_index_renders(self, client):
        r = client.get("/prompt-calendar/")
        assert r.status_code == 200
        assert b"Prompt Calendar" in r.data

    def test_api_month(self, client):
        r = client.get("/prompt-calendar/api/month/2026/7")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert len(d["weeks"]) >= 4

    def test_api_day(self, client):
        r = client.get("/prompt-calendar/api/day/2026-07-15")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "text" in d["prompt"]

    def test_api_day_invalid_format(self, client):
        r = client.get("/prompt-calendar/api/day/not-a-date")
        assert r.status_code == 400

    def test_month_has_prompt_per_day(self, client):
        r = client.get("/prompt-calendar/api/month/2026/7")
        d = r.get_json()
        for week in d["weeks"]:
            for day in week:
                assert "text" in day
                assert "category" in day


# ---------------------------------------------------------------------------
# Chapter Dependencies
# ---------------------------------------------------------------------------

class TestChapterDeps:
    def test_index_renders(self, client):
        r = client.get("/chapter-deps/")
        assert r.status_code == 200
        assert b"Chapter Dependencies" in r.data

    def test_api_graph_empty(self, client):
        r = client.get("/chapter-deps/api/graph")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "cycles" in d
        assert "violations" in d

    def test_add_and_remove_dependency(self, client):
        # Create two chapters
        r1 = client.post("/chapters/new", data={"title": "Ch A", "content": "a", "status": "draft"})
        r2 = client.post("/chapters/new", data={"title": "Ch B", "content": "b", "status": "draft"})
        ch_a = r1.get_json()["id"]
        ch_b = r2.get_json()["id"]
        # Add dependency: A depends on B
        r = client.post("/chapter-deps/api/add", json={
            "from_chapter_id": ch_a, "to_chapter_id": ch_b,
        })
        assert r.status_code == 200
        assert r.get_json()["ok"]
        # Verify in graph
        r = client.get("/chapter-deps/api/graph")
        assert r.get_json()["total_dependencies"] >= 1
        # Remove
        r = client.post("/chapter-deps/api/remove", json={
            "from_chapter_id": ch_a, "to_chapter_id": ch_b,
        })
        assert r.get_json()["ok"]

    def test_self_dependency_rejected(self, client):
        r = client.post("/chapters/new", data={"title": "Self", "content": "x", "status": "draft"})
        ch_id = r.get_json()["id"]
        r = client.post("/chapter-deps/api/add", json={
            "from_chapter_id": ch_id, "to_chapter_id": ch_id,
        })
        assert r.status_code == 400

    def test_reverse_dependency_rejected(self, client):
        r1 = client.post("/chapters/new", data={"title": "X", "content": "x", "status": "draft"})
        r2 = client.post("/chapters/new", data={"title": "Y", "content": "y", "status": "draft"})
        ch_x = r1.get_json()["id"]
        ch_y = r2.get_json()["id"]
        # Add X depends on Y
        client.post("/chapter-deps/api/add", json={
            "from_chapter_id": ch_x, "to_chapter_id": ch_y,
        })
        # Try reverse: Y depends on X — should fail
        r = client.post("/chapter-deps/api/add", json={
            "from_chapter_id": ch_y, "to_chapter_id": ch_x,
        })
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Sidebar visibility
# ---------------------------------------------------------------------------

class TestV47Sidebar:
    def test_sidebar_has_prompt_calendar(self, client):
        r = client.get("/")
        assert b"Prompt Calendar" in r.data

    def test_sidebar_has_chapter_deps(self, client):
        r = client.get("/")
        assert b"Chapter Deps" in r.data
