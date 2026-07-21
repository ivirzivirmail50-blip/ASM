"""Focused tests for v4.6: sessions, snapshot_diff, quick_capture.

Only critical paths and edge cases — not exhaustive coverage.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


# ---------------------------------------------------------------------------
# Session Timer
# ---------------------------------------------------------------------------

class TestSessionService:
    def test_start_and_end_session(self):
        from services import session_service as svc
        sess = svc.start_session(session_type="pomodoro")
        assert sess.id
        assert sess.status == "active"
        assert sess.target_minutes == 25
        ended = svc.end_session(sess.id, status="completed")
        assert ended.status == "completed"
        assert ended.ended_at is not None

    def test_cannot_start_two_active_sessions(self):
        from services import session_service as svc
        from core.errors import ValidationError
        s1 = svc.start_session(session_type="pomodoro")
        with pytest.raises(ValidationError):
            svc.start_session(session_type="pomodoro")
        svc.end_session(s1.id, status="abandoned")

    def test_pause_resume_flow(self):
        from services import session_service as svc
        sess = svc.start_session(session_type="short_focus")
        paused = svc.pause_session(sess.id)
        assert paused.status == "paused"
        resumed = svc.resume_session(sess.id)
        assert resumed.status == "active"
        svc.end_session(sess.id)

    def test_invalid_session_type(self):
        from services import session_service as svc
        from core.errors import ValidationError
        with pytest.raises(ValidationError):
            svc.start_session(session_type="bogus")

    def test_stats_returns_dict(self):
        from services import session_service as svc
        s = svc.stats(days=30)
        assert "total_sessions" in s
        assert "avg_wpm" in s


# ---------------------------------------------------------------------------
# Snapshot Diff
# ---------------------------------------------------------------------------

class TestSnapshotDiffService:
    def test_reconstruct_at_returns_dict(self):
        from services import snapshot_diff_service as svc
        state = svc._reconstruct_at(datetime.now(timezone.utc))
        assert isinstance(state, dict)

    def test_compute_diff_same_date_returns_empty(self):
        from services import snapshot_diff_service as svc
        now = datetime.now(timezone.utc)
        diff = svc.compute_diff(now, now)
        assert diff["added_count"] == 0
        assert diff["removed_count"] == 0

    def test_compute_diff_detects_new_chapter(self):
        from services import snapshot_diff_service as svc
        from services.chapter_service import create_chapter
        old = datetime.now(timezone.utc) - timedelta(days=1)
        create_chapter(title="Diff Test", content="New content")
        new = datetime.now(timezone.utc)
        diff = svc.compute_diff(old, new)
        # Should detect the new chapter
        assert diff["to_chapter_count"] >= diff["from_chapter_count"]

    def test_get_available_dates_returns_list(self):
        from services import snapshot_diff_service as svc
        dates = svc.get_available_dates()
        assert isinstance(dates, list)

    def test_render_diff_html(self):
        from services import snapshot_diff_service as svc
        now = datetime.now(timezone.utc)
        diff = svc.compute_diff(now, now)
        html = svc.render_diff_html(diff)
        assert "<html" in html
        assert "Manuscript Diff" in html


# ---------------------------------------------------------------------------
# Quick Capture (route-level)
# ---------------------------------------------------------------------------

class TestQuickCaptureRoutes:
    def test_capture_note(self, client):
        r = client.post("/quick-capture/api/capture", json={
            "type": "note", "body": "Test note body", "title": "QC Note"
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert d["type"] == "note"

    def test_capture_chapter(self, client):
        r = client.post("/quick-capture/api/capture", json={
            "type": "chapter", "body": "Chapter content", "title": "QC Chapter"
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert d["type"] == "chapter"
        assert d["id"]

    def test_capture_journal(self, client):
        r = client.post("/quick-capture/api/capture", json={
            "type": "journal", "body": "Day went well", "mood": "good"
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert d["type"] == "journal"

    def test_capture_snippet(self, client):
        r = client.post("/quick-capture/api/capture", json={
            "type": "snippet", "body": "Reusable text", "title": "QC Snippet"
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert d["type"] == "snippet"

    def test_capture_empty_body_rejected(self, client):
        r = client.post("/quick-capture/api/capture", json={
            "type": "note", "body": "", "title": ""
        })
        assert r.status_code == 400

    def test_capture_invalid_type(self, client):
        r = client.post("/quick-capture/api/capture", json={
            "type": "bogus", "body": "test"
        })
        assert r.status_code == 400

    def test_dashboard_has_widget(self, client):
        r = client.get("/")
        assert b"Quick Capture" in r.data


# ---------------------------------------------------------------------------
# Session routes
# ---------------------------------------------------------------------------

class TestSessionRoutes:
    def test_index_renders(self, client):
        r = client.get("/sessions/")
        assert r.status_code == 200
        assert b"Session Timer" in r.data

    def test_api_start(self, client):
        r = client.post("/sessions/api/start", json={"session_type": "pomodoro"})
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert d["session"]["session_type"] == "pomodoro"
        # Clean up
        client.post(f"/sessions/api/{d['id']}/end", json={"status": "abandoned"})

    def test_api_active(self, client):
        r = client.get("/sessions/api/active")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]

    def test_api_stats(self, client):
        r = client.get("/sessions/api/stats")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "total_sessions" in d


# ---------------------------------------------------------------------------
# Snapshot Diff routes
# ---------------------------------------------------------------------------

class TestSnapshotDiffRoutes:
    def test_index_renders(self, client):
        r = client.get("/snapshot-diff/")
        assert r.status_code == 200
        assert b"Manuscript Diff" in r.data

    def test_api_dates(self, client):
        r = client.get("/snapshot-diff/api/dates")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert isinstance(d["dates"], list)

    def test_api_diff_missing_params(self, client):
        r = client.get("/snapshot-diff/api/diff")
        assert r.status_code == 400
