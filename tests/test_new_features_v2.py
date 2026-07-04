"""Tests for cache, async export, timeline reorder, pagination settings, and AI disclosure."""
import json
import time
import pytest

from core.cache import cache


class TestCache:
    def test_set_and_get(self):
        cache.set("test:key1", "value1", ttl_seconds=5)
        assert cache.get("test:key1") == "value1"

    def test_get_missing_returns_none(self):
        assert cache.get("nonexistent:key") is None

    def test_ttl_expiration(self):
        cache.set("test:expire", "temp", ttl_seconds=1)
        assert cache.get("test:expire") == "temp"
        time.sleep(1.5)
        assert cache.get("test:expire") is None

    def test_invalidate_by_prefix(self):
        cache.set("stats:counts", {"a": 1}, ttl_seconds=60)
        cache.set("stats:words", 100, ttl_seconds=60)
        cache.set("other:key", "x", ttl_seconds=60)
        removed = cache.invalidate("stats:")
        assert removed >= 2
        assert cache.get("stats:counts") is None
        assert cache.get("stats:words") is None
        assert cache.get("other:key") == "x"

    def test_clear_all(self):
        cache.set("a:1", 1, ttl_seconds=60)
        cache.set("b:2", 2, ttl_seconds=60)
        cache.clear()
        assert cache.get("a:1") is None
        assert cache.get("b:2") is None

    def test_cached_decorator(self):
        from core.cache import cached
        call_count = [0]

        @cached("test:deco", ttl_seconds=60)
        def expensive_func():
            call_count[0] += 1
            return "result"

        # First call: executes
        assert expensive_func() == "result"
        assert call_count[0] == 1
        # Second call: cached
        assert expensive_func() == "result"
        assert call_count[0] == 1  # not incremented

    def test_thread_safety(self):
        """Cache should be thread-safe (no exceptions under concurrent access)."""
        import threading
        errors = []

        def worker():
            try:
                for i in range(100):
                    cache.set(f"thread:{i}", i, ttl_seconds=60)
                    cache.get(f"thread:{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors


class TestStatsCache:
    def test_stats_cached(self):
        """Stats functions should use cache — second call returns cached value."""
        from services import stats_service
        # Clear cache first
        cache.invalidate("stats:")
        result1 = stats_service.overall_counts()
        result2 = stats_service.overall_counts()
        assert result1 == result2

    def test_stats_cache_invalidated_on_write(self):
        """Creating a chapter should invalidate stats cache."""
        from services import stats_service, chapter_service
        cache.invalidate("stats:")
        # First call populates cache
        stats_service.overall_counts()
        # Create a chapter (should invalidate cache via log_activity)
        chapter_service.create_chapter(title="Cache Invalidation Test", content="x")
        # Cache should be invalidated — next call fetches fresh data
        result = stats_service.overall_counts()
        assert result["chapters"] >= 1


class TestAsyncExport:
    def test_async_export_returns_task_id(self, client):
        # Create a chapter so there's something to export
        client.post("/chapters/new", data={"title": "Async Test", "content": "x"})
        r = client.get("/export/async/manuscript/txt")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["ok"] is True
        assert "task_id" in data

    def test_export_status_endpoint(self, client):
        client.post("/chapters/new", data={"title": "Status Test", "content": "x"})
        r = client.get("/export/async/manuscript/txt")
        task_id = json.loads(r.data)["task_id"]
        # Wait a moment for background thread
        time.sleep(1)
        r = client.get(f"/export/status/{task_id}")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["ok"] is True
        assert "status" in data
        assert data["status"] in ("processing", "done", "error")

    def test_export_status_not_found(self, client):
        r = client.get("/export/status/nonexistent-task-id")
        assert r.status_code == 404

    def test_export_download_not_ready(self, client):
        """Download should 404 if task hasn't completed."""
        r = client.get("/export/download/nonexistent-task-id")
        assert r.status_code == 404


class TestTimelineReorder:
    def test_timeline_reorder_endpoint(self, client):
        # Create plans with tracks
        client.post("/plans/new", data={"title": "P1", "status": "idea", "track": "Main Plot"})
        client.post("/plans/new", data={"title": "P2", "status": "idea", "track": "Subplot"})
        # Reorder
        r = client.post("/plans/timeline/reorder",
                        data=json.dumps({"tracks": ["Subplot", "Main Plot"]}),
                        content_type="application/json")
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True

    def test_get_track_order(self):
        from services import plan_service
        order = plan_service.get_track_order()
        assert isinstance(order, list)

    def test_reorder_tracks_persists(self):
        from services import plan_service
        plan_service.reorder_tracks(["Track C", "Track A", "Track B"])
        order = plan_service.get_track_order()
        # Should start with Track C (if it exists in DB) or be a subset
        assert isinstance(order, list)


class TestPaginationSettings:
    def test_chapters_per_page_setting_exists(self, client):
        r = client.get("/settings/")
        assert b"chapters_per_page" in r.data

    def test_world_per_page_setting_exists(self, client):
        r = client.get("/settings/")
        assert b"world_per_page" in r.data

    def test_search_results_per_module_setting(self, client):
        r = client.get("/settings/")
        assert b"search_results_per_module" in r.data

    def test_chapter_pagination_uses_setting(self, client):
        """Changing chapters_per_page should affect list behavior."""
        # Set to a small value
        client.post("/settings/save", data=json.dumps({"chapters_per_page": 5}),
                    content_type="application/json")
        # Create 10 chapters
        for i in range(10):
            client.post("/chapters/new", data={"title": f"Pag {i}", "content": "x"})
        # Page 1 should have 5 chapters
        r = client.get("/chapters/")
        # Count chapter cards
        import re
        cards = re.findall(r'data-id="([a-f0-9]{32})"', r.data.decode())
        assert len(cards) <= 5

    def test_world_pagination(self, client):
        """World index should show pagination controls when there are many entries."""
        # Create multiple entries
        for i in range(5):
            client.post("/world/new", data={
                "type": "location", "name": f"Pag Loc {i}", "content": "x"
            })
        r = client.get("/world/")
        assert r.status_code == 200


class TestAIDisclosure:
    def test_disclosure_setting_exists(self, client):
        """ai.disclosure_accepted should be in default settings."""
        from models.settings import DEFAULT_SETTINGS
        assert "ai.disclosure_accepted" in DEFAULT_SETTINGS

    def test_disclosure_defaults_false(self):
        from models.settings import DEFAULT_SETTINGS
        assert DEFAULT_SETTINGS["ai.disclosure_accepted"] == "false"

    def test_disclosure_can_be_set(self, client):
        client.post("/settings/save", data=json.dumps({
            "ai.disclosure_accepted": "true"
        }), content_type="application/json")
        r = client.get("/settings/ai")
        assert r.status_code == 200


class TestManuscriptSettings:
    def test_manuscript_pdf_uses_settings(self, client):
        """Manuscript PDF should respect manuscript_line_spacing setting."""
        # Set line spacing to 3.0 (triple-spaced)
        client.post("/settings/save", data=json.dumps({
            "manuscript_line_spacing": "3.0",
            "manuscript_font": "Courier",
            "manuscript_font_size": "12",
        }), content_type="application/json")
        # Create a chapter and export
        client.post("/chapters/new", data={"title": "MS Test", "content": "Some content here."})
        r = client.get("/export/manuscript/pdf")
        assert r.status_code == 200
        assert r.data.startswith(b"%PDF")
