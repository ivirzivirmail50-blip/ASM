"""Tests for Daily Writing Journal (v4.4)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from services import journal_service as svc


def test_get_or_create_today_creates_entry():
    e = svc.get_or_create_today()
    assert e.id
    assert e.entry_date == date.today()
    assert e.word_count_goal > 0  # pulled from settings


def test_get_or_create_today_idempotent():
    e1 = svc.get_or_create_today()
    e2 = svc.get_or_create_today()
    assert e1.id == e2.id


def test_get_by_date_returns_none_when_not_exists():
    future = date.today() + timedelta(days=365)
    assert svc.get_by_date(future) is None


def test_create_or_update_for_date_creates_new():
    d = date.today() - timedelta(days=10)
    e = svc.create_or_update_for_date(d, mood="good", energy=4, wins="Great day")
    assert e.id
    assert e.mood == "good"
    assert e.energy == 4
    assert e.wins == "Great day"


def test_create_or_update_for_date_updates_existing():
    d = date.today() - timedelta(days=5)
    e1 = svc.create_or_update_for_date(d, mood="good")
    e2 = svc.create_or_update_for_date(d, mood="great", energy=5)
    assert e1.id == e2.id
    assert e2.mood == "great"
    assert e2.energy == 5


def test_invalid_mood_rejected():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.create_or_update_for_date(date.today(), mood="bogus")


def test_invalid_energy_rejected():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.create_or_update_for_date(date.today(), energy=99)


def test_update_entry():
    e = svc.create_or_update_for_date(date.today(), mood="ok")
    updated = svc.update_entry(e.id, mood="great", notes="Updated")
    assert updated.mood == "great"
    assert updated.notes == "Updated"


def test_delete_entry():
    d = date.today() - timedelta(days=20)
    e = svc.create_or_update_for_date(d, mood="ok")
    svc.delete_entry(e.id)
    from core.errors import NotFoundError
    with pytest.raises(NotFoundError):
        svc.get_entry(e.id)


def test_list_entries_newest_first():
    svc.create_or_update_for_date(date.today() - timedelta(days=1), mood="ok")
    svc.create_or_update_for_date(date.today() - timedelta(days=2), mood="ok")
    entries = svc.list_entries(limit=10)
    if len(entries) >= 2:
        assert entries[0].entry_date >= entries[1].entry_date


def test_to_dict_shape():
    e = svc.create_or_update_for_date(
        date.today(), mood="good", energy=4,
        word_count_goal=500, word_count_actual=600,
        wins="W", struggles="S", intentions="I", gratitude="G",
    )
    d = svc.to_dict(e)
    assert d["mood"] == "good"
    assert d["mood_label"] == "Good"
    assert d["mood_icon"] == "😊"
    assert d["energy"] == 4
    assert d["word_count_goal"] == 500
    assert d["word_count_actual"] == 600
    assert d["goal_met"] is True
    assert d["goal_pct"] == 120.0
    assert d["wins"] == "W"


def test_goal_met_when_actual_exceeds_goal():
    e = svc.create_or_update_for_date(
        date.today(), word_count_goal=500, word_count_actual=500,
    )
    d = svc.to_dict(e)
    assert d["goal_met"] is True


def test_goal_not_met_when_actual_below_goal():
    e = svc.create_or_update_for_date(
        date.today(), word_count_goal=500, word_count_actual=400,
    )
    d = svc.to_dict(e)
    assert d["goal_met"] is False


def test_stats_empty():
    # With no entries in the last 30 days (other than what previous tests created)
    s = svc.stats(days=30)
    assert "entries_count" in s
    assert "avg_mood_score" in s
    assert "streak" in s


def test_stats_with_entries():
    svc.create_or_update_for_date(date.today(), mood="good", energy=4)
    svc.create_or_update_for_date(date.today() - timedelta(days=1), mood="ok", energy=3)
    s = svc.stats(days=30)
    assert s["entries_count"] >= 2
    assert s["avg_mood_score"] > 0
    assert s["avg_energy"] > 0


def test_streak_counts_consecutive_days():
    # Create entries for today and yesterday
    svc.create_or_update_for_date(date.today(), mood="ok")
    svc.create_or_update_for_date(date.today() - timedelta(days=1), mood="ok")
    s = svc.stats(days=30)
    assert s["streak"] >= 2


def test_get_entry_not_found():
    from core.errors import NotFoundError
    with pytest.raises(NotFoundError):
        svc.get_entry("nonexistent-id")


def test_mood_distribution_in_stats():
    svc.create_or_update_for_date(date.today(), mood="good")
    svc.create_or_update_for_date(date.today() - timedelta(days=1), mood="bad" if "bad" in svc.JOURNAL_MOODS else "ok")
    s = svc.stats(days=30)
    assert isinstance(s["mood_distribution"], dict)
