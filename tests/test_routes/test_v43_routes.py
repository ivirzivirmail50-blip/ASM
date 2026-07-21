"""Route tests for v4.3 modules: reading, voice, timeline_check, references."""
import json
import pytest


class TestReadingRoutes:
    def test_index_renders(self, client):
        r = client.get("/reading/")
        assert r.status_code == 200
        assert b"Reading Mode" in r.data

    def test_api_chapters(self, client):
        r = client.get("/reading/api/chapters")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "chapters" in d
        assert isinstance(d["chapters"], list)

    def test_index_with_chapters(self, client):
        client.post("/chapters/new", data={
            "title": "Reader Test", "content": "Some readable content.", "status": "draft",
        })
        r = client.get("/reading/")
        assert r.status_code == 200


class TestVoiceRoutes:
    def test_index_renders(self, client):
        r = client.get("/voice/")
        assert r.status_code == 200
        assert b"Voice Profiles" in r.data

    def test_index_no_characters(self, client):
        r = client.get("/voice/")
        assert b"No characters yet" in r.data

    def test_profile_creates_lazy(self, client):
        # Create a character first
        r = client.post("/characters/new", data={
            "name": "Test Char", "role": "protagonist",
        })
        d = json.loads(r.data)
        cid = d.get("id") or d.get("character", {}).get("id")
        if not cid:
            # Try as form
            r = client.post("/characters/new", data={
                "name": "Test Char 2", "role": "protagonist",
            }, content_type="application/x-www-form-urlencoded")
            d = json.loads(r.data)
            cid = d.get("id")
        if cid:
            r = client.get(f"/voice/{cid}")
            assert r.status_code == 200

    def test_api_update(self, client):
        # Need a character — create one directly via service
        from services.character_service import create_character
        c = create_character(name="Voice Test", role="protagonist")
        r = client.post(f"/voice/api/{c.id}", json={
            "speech_verbosity": "terse",
            "formality": "archaic",
            "favorite_words": "indeed\nnevertheless",
            "avoided_words": "okay",
        })
        assert r.status_code == 200
        assert r.get_json()["ok"]

    def test_api_scan(self, client):
        from services.character_service import create_character
        c = create_character(name="Scan Test", role="protagonist")
        r = client.get(f"/voice/api/{c.id}/scan")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]

    def test_api_summary(self, client):
        from services.character_service import create_character
        c = create_character(name="Summary Test", role="protagonist")
        r = client.get(f"/voice/api/{c.id}/summary")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]


class TestTimelineCheckRoutes:
    def test_index_renders(self, client):
        r = client.get("/timeline-check/")
        assert r.status_code == 200
        assert b"Timeline Conflict" in r.data

    def test_api_scan(self, client):
        r = client.get("/timeline-check/api/scan")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "issues" in d
        assert "gaps" in d

    def test_api_scan_with_track(self, client):
        r = client.get("/timeline-check/api/scan?track=alpha")
        assert r.status_code == 200


class TestReferencesRoutes:
    def test_index_renders(self, client):
        r = client.get("/references/")
        assert r.status_code == 200
        assert b"Research & References" in r.data

    def test_create_reference(self, client):
        r = client.post("/references/api/new", json={
            "title": "Test Book",
            "author": "Test Author",
            "source_type": "book",
            "read_status": "unread",
            "priority": "high",
            "rating": 5,
        })
        assert r.status_code == 200
        assert r.get_json()["ok"]

    def test_create_invalid_type(self, client):
        r = client.post("/references/api/new", json={
            "title": "x", "source_type": "bogus",
        })
        assert r.status_code == 400

    def test_create_invalid_rating(self, client):
        r = client.post("/references/api/new", json={
            "title": "x", "rating": 99,
        })
        assert r.status_code == 400

    def test_update_reference(self, client):
        r = client.post("/references/api/new", json={"title": "Old"})
        rid = r.get_json()["id"]
        r = client.post(f"/references/api/{rid}", json={"title": "New", "read_status": "read"})
        assert r.get_json()["ok"]

    def test_delete_reference(self, client):
        r = client.post("/references/api/new", json={"title": "X"})
        rid = r.get_json()["id"]
        r = client.post(f"/references/api/{rid}/delete")
        assert r.get_json()["ok"]

    def test_stats_endpoint(self, client):
        r = client.get("/references/api/stats")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"]
        assert "total" in d

    def test_index_with_filters(self, client):
        client.post("/references/api/new", json={
            "title": "Filter Test", "source_type": "book", "read_status": "read",
        })
        r = client.get("/references/?source_type=book&read_status=read")
        assert r.status_code == 200


class TestV43Sidebar:
    """Verify all v4.3 modules appear in the sidebar."""

    def test_sidebar_has_reading(self, client):
        r = client.get("/")
        assert b"Reading Mode" in r.data

    def test_sidebar_has_voice(self, client):
        r = client.get("/")
        assert b"Voice Profiles" in r.data

    def test_sidebar_has_timeline_audit(self, client):
        r = client.get("/")
        assert b"Timeline Audit" in r.data

    def test_sidebar_has_references(self, client):
        r = client.get("/")
        assert b"Research & Refs" in r.data
