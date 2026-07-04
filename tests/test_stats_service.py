"""Tests for stats_service: streaks, word counts, heatmap."""
import pytest
from datetime import datetime, timedelta, timezone

from services import chapter_service, stats_service


def test_count_words_in_stats():
    """overall_counts should reflect created chapters."""
    chapter_service.create_chapter(title="A", content="one two three")
    chapter_service.create_chapter(title="B", content="four five")
    counts = stats_service.overall_counts()
    assert counts["chapters"] >= 2
    assert counts["total_words"] >= 5


def test_words_today_with_new_chapter():
    """Creating a chapter logs a positive word delta, so today's words > 0."""
    chapter_service.create_chapter(title="Today", content="alpha beta gamma delta")
    assert stats_service.words_today() >= 4


def test_daily_history_returns_30_days():
    history = stats_service.daily_history(days=30)
    assert len(history) == 30
    # Each entry has date + words
    for entry in history:
        assert "date" in entry
        assert "words" in entry
        assert entry["words"] >= 0


def test_annual_heatmap_returns_365_days():
    heatmap = stats_service.annual_heatmap(year=2025)
    # 2025 is not a leap year, so 365 days
    assert len(heatmap) == 365
    for entry in heatmap:
        assert "level" in entry
        assert 0 <= entry["level"] <= 4


def test_annual_heatmap_leap_year():
    heatmap = stats_service.annual_heatmap(year=2024)
    assert len(heatmap) == 366  # leap year


def test_heat_level_thresholds():
    assert stats_service._heat_level(0) == 0
    assert stats_service._heat_level(50) == 1
    assert stats_service._heat_level(200) == 2
    assert stats_service._heat_level(500) == 3
    assert stats_service._heat_level(1000) == 4


def test_character_appearance_heatmap():
    from services import character_service
    ch = character_service.create_character(name="Appears", role="minor")
    chapter_service.create_chapter(
        title="Linked", content="Content", character_ids=[ch.id],
    )
    heat = stats_service.character_appearance_heatmap()
    matching = [h for h in heat if h["id"] == ch.id]
    assert matching
    assert matching[0]["appearances"] >= 1


def test_recent_activity_returns_list():
    chapter_service.create_chapter(title="Activity", content="word")
    activity = stats_service.recent_activity(limit=5)
    assert isinstance(activity, list)
    assert len(activity) <= 5
    if activity:
        assert "entity_type" in activity[0]
        assert "action" in activity[0]
        assert "timestamp" in activity[0]


def test_activity_log_cap():
    """Activity log should be capped at ACTIVITY_LOG_CAP (2000 entries)."""
    from security import limits
    from core.db import read_session
    from models.activity import ActivityLog
    from services._common import log_activity, new_uuid
    from core.db import write_transaction

    # Insert more than the cap
    cap = limits.ACTIVITY_LOG_CAP
    excess = 50
    with write_transaction() as s:
        for i in range(cap + excess):
            log_activity(
                s,
                entity_type="chapter",
                entity_id=new_uuid(),
                entity_title=f"Cap test {i}",
                action="updated",
                word_count_delta=10,
            )

    # Verify the count is at or below the cap
    with read_session() as s:
        count = s.query(ActivityLog).count()
        assert count <= cap, f"Activity log has {count} entries, cap is {cap}"
        assert count == cap, f"Expected exactly {cap} entries after capping, got {count}"


def test_activity_log_cap_oldest_removed():
    """When capped, the OLDEST entries should be removed (not newest)."""
    from core.db import read_session, write_transaction
    from models.activity import ActivityLog
    from services._common import log_activity, new_uuid
    from security import limits

    # Insert exactly cap entries with distinguishable titles
    cap = limits.ACTIVITY_LOG_CAP
    with write_transaction() as s:
        for i in range(cap):
            log_activity(
                s,
                entity_type="chapter",
                entity_id=new_uuid(),
                entity_title=f"Entry-{i:05d}",
                action="updated",
            )

    # Now insert one more — should trigger cap, removing the oldest
    with write_transaction() as s:
        log_activity(
            s,
            entity_type="chapter",
            entity_id=new_uuid(),
            entity_title="NEWEST-ENTRY",
            action="created",
        )

    # The newest entry should exist
    with read_session() as s:
        newest = s.query(ActivityLog).filter(
            ActivityLog.entity_title == "NEWEST-ENTRY"
        ).first()
        assert newest is not None, "Newest entry should exist"

        # The oldest entry (Entry-00000) should have been removed
        oldest = s.query(ActivityLog).filter(
            ActivityLog.entity_title == "Entry-00000"
        ).first()
        assert oldest is None, "Oldest entry should have been removed by cap"

        # Count should still be at cap
        count = s.query(ActivityLog).count()
        assert count == cap
