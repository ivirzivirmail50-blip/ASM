"""Route tests for v4.2 modules: glossary, find_replace, submissions, analytics."""
import json
import pytest


class TestGlossaryRoutes:
    def test_index_renders(self, client):
        r = client.get("/glossary/")
        assert r.status_code == 200
        assert b"Glossary" in r.data

    def test_create_entry(self, client):
        r = client.post("/glossary/api/new", json={
            "term": "Elara",
            "category": "character",
            "definition": "The protagonist",
            "alternates": ["El"],
            "forbidden": ["Ellara"],
        })
        assert r.status_code == 200
        assert r.get_json()["ok"]

    def test_create_invalid_category(self, client):
        r = client.post("/glossary/api/new", json={
            "term": "x", "category": "bogus",
        })
        assert r.status_code == 400

    def test_update_entry(self, client):
        r = client.post("/glossary/api/new", json={"term": "x", "category": "other"})
        eid = r.get_json()["id"]
        r = client.post(f"/glossary/api/{eid}", json={"term": "y"})
        assert r.get_json()["ok"]

    def test_delete_entry(self, client):
        r = client.post("/glossary/api/new", json={"term": "x", "category": "other"})
        eid = r.get_json()["id"]
        r = client.post(f"/glossary/api/{eid}/delete")
        assert r.get_json()["ok"]

    def test_scan_endpoint(self, client):
        r = client.get("/glossary/api/scan")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "issues" in d
        assert "presence" in d

    def test_scan_page_renders(self, client):
        r = client.get("/glossary/scan")
        assert r.status_code == 200
        assert b"Scan Results" in r.data

    def test_seed_defaults(self, client):
        r = client.post("/glossary/api/seed")
        assert r.get_json()["ok"]

    def test_filter_by_category(self, client):
        client.post("/glossary/api/new", json={"term": "A", "category": "character"})
        client.post("/glossary/api/new", json={"term": "B", "category": "place"})
        r = client.get("/glossary/?category=character")
        assert r.status_code == 200
        assert b"A" in r.data


class TestFindReplaceRoutes:
    def test_index_renders(self, client):
        r = client.get("/find-replace/")
        assert r.status_code == 200
        assert b"Find & Replace" in r.data

    def test_preview_endpoint(self, client):
        r = client.post("/find-replace/api/preview", json={
            "pattern": "test", "replacement": "exam", "whole_word": True,
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "chapters_scanned" in d

    def test_preview_invalid_regex(self, client):
        r = client.post("/find-replace/api/preview", json={
            "pattern": "[unclosed", "replacement": "x", "use_regex": True,
        })
        assert r.status_code == 400

    def test_apply_endpoint(self, client):
        # First create a chapter with content
        client.post("/chapters/new", data={
            "title": "FRT", "content": "Hello world. Hello again.", "status": "draft",
        })
        r = client.post("/find-replace/api/apply", json={
            "pattern": "Hello", "replacement": "Hi", "whole_word": True,
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert d["applied"] is True

    def test_apply_no_matches(self, client):
        r = client.post("/find-replace/api/apply", json={
            "pattern": "nonexistent_xyz", "replacement": "x",
        })
        d = r.get_json()
        assert d["ok"]
        assert d["applied"] is False


class TestSubmissionsRoutes:
    def test_index_renders(self, client):
        r = client.get("/submissions/")
        assert r.status_code == 200
        assert b"Submission Tracker" in r.data

    def test_create_submission(self, client):
        r = client.post("/submissions/api/new", json={
            "title": "My Story",
            "market_name": "Clarkesworld",
            "market_type": "magazine",
            "status": "submitted",
            "submitted_date": "2026-07-01",
        })
        assert r.status_code == 200
        assert r.get_json()["ok"]

    def test_create_invalid_status(self, client):
        r = client.post("/submissions/api/new", json={
            "title": "x", "market_name": "y", "status": "bogus",
        })
        assert r.status_code == 400

    def test_update_submission(self, client):
        r = client.post("/submissions/api/new", json={
            "title": "x", "market_name": "y",
        })
        sid = r.get_json()["id"]
        r = client.post(f"/submissions/api/{sid}", json={"status": "accepted"})
        assert r.get_json()["ok"]

    def test_delete_submission(self, client):
        r = client.post("/submissions/api/new", json={
            "title": "x", "market_name": "y",
        })
        sid = r.get_json()["id"]
        r = client.post(f"/submissions/api/{sid}/delete")
        assert r.get_json()["ok"]

    def test_stats_endpoint(self, client):
        r = client.get("/submissions/api/stats")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "total" in d
        assert "acceptance_rate" in d

    def test_markets_endpoint(self, client):
        client.post("/submissions/api/new", json={
            "title": "x", "market_name": "TestMag",
        })
        r = client.get("/submissions/api/markets")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert any(m["name"] == "TestMag" for m in d["markets"])

    def test_chapters_endpoint(self, client):
        r = client.get("/submissions/api/chapters")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "chapters" in d

    def test_index_with_status_filter(self, client):
        client.post("/submissions/api/new", json={
            "title": "A", "market_name": "M1", "status": "submitted",
        })
        client.post("/submissions/api/new", json={
            "title": "B", "market_name": "M2", "status": "rejected",
        })
        r = client.get("/submissions/?status=submitted")
        assert r.status_code == 200


class TestAnalyticsRoutes:
    def test_index_renders(self, client):
        r = client.get("/analytics/")
        assert r.status_code == 200
        assert b"Writing Analytics" in r.data

    def test_index_with_no_chapters(self, client):
        r = client.get("/analytics/")
        assert r.status_code == 200
        assert b"No chapters to analyze" in r.data

    def test_index_with_chapters(self, client):
        client.post("/chapters/new", data={
            "title": "AnCh", "content": "Hello world. This is a test chapter.", "status": "draft",
        })
        r = client.get("/analytics/")
        assert r.status_code == 200
        assert b"Total Words" in r.data

    def test_api_chapters(self, client):
        client.post("/chapters/new", data={
            "title": "AC", "content": "Test content.", "status": "draft",
        })
        r = client.get("/analytics/api/chapters")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert isinstance(d["chapters"], list)

    def test_api_summary(self, client):
        r = client.get("/analytics/api/summary")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "chapter_count" in d
        assert "total_words" in d

    def test_api_top_words(self, client):
        client.post("/chapters/new", data={
            "title": "TW", "content": "apple banana apple cherry apple banana", "status": "draft",
        })
        r = client.get("/analytics/api/top-words")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert isinstance(d["words"], list)


class TestV42Sidebar:
    """Verify all v4.2 modules appear in the sidebar."""

    def test_sidebar_has_glossary(self, client):
        r = client.get("/")
        assert b"Glossary & Style" in r.data

    def test_sidebar_has_find_replace(self, client):
        r = client.get("/")
        assert b"Find & Replace" in r.data

    def test_sidebar_has_submissions(self, client):
        r = client.get("/")
        assert b"Submission Tracker" in r.data

    def test_sidebar_has_analytics(self, client):
        r = client.get("/")
        assert b"Writing Analytics" in r.data
