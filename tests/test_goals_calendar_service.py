"""Tests for Goals Calendar (v4.5)."""
from __future__ import annotations

from datetime import date

import pytest

from services import goals_calendar_service as svc


def test_get_month_calendar_returns_structure():
    today = date.today()
    result = svc.get_month_calendar(today.year, today.month)
    assert "year" in result
    assert "month" in result
    assert "weeks" in result
    assert "daily_goal" in result
    assert "total_words" in result
    assert isinstance(result["weeks"], list)


def test_month_calendar_has_weeks():
    result = svc.get_month_calendar(2026, 7)
    # July 2026 spans 5 weeks
    assert len(result["weeks"]) >= 4
    for week in result["weeks"]:
        assert len(week) == 7  # 7 days per week


def test_month_calendar_day_fields():
    result = svc.get_month_calendar(2026, 7)
    for week in result["weeks"]:
        for day in week:
            assert "date" in day
            assert "day" in day
            assert "in_month" in day
            assert "is_today" in day
            assert "words" in day
            assert "goal_met" in day
            assert "heat_level" in day
            assert 0 <= day["heat_level"] <= 4


def test_month_calendar_prev_next():
    result = svc.get_month_calendar(2026, 1)
    assert result["prev_month"] == (2025, 12)
    assert result["next_month"] == (2026, 2)

    result = svc.get_month_calendar(2026, 12)
    assert result["prev_month"] == (2026, 11)
    assert result["next_month"] == (2027, 1)


def test_month_calendar_stats():
    result = svc.get_month_calendar(2026, 7)
    assert "writing_days" in result
    assert "goal_met_days" in result
    assert "avg_per_writing_day" in result
    assert isinstance(result["writing_days"], int)
    assert isinstance(result["goal_met_days"], int)


def test_heat_level():
    assert svc._heat_level(0, 500) == 0
    assert svc._heat_level(50, 500) == 1   # < 25%
    assert svc._heat_level(200, 500) == 2  # < 50%
    assert svc._heat_level(400, 500) == 3  # < 100%
    assert svc._heat_level(500, 500) == 4  # >= 100%
    assert svc._heat_level(600, 500) == 4


def test_get_year_overview():
    result = svc.get_year_overview(2026)
    assert "year" in result
    assert "daily_goal" in result
    assert "total_goal" in result
    assert "year_words" in result
    assert "writing_days" in result
    assert "months" in result
    assert len(result["months"]) == 12


def test_year_overview_months_have_data():
    result = svc.get_year_overview(2026)
    for m in result["months"]:
        assert "month" in m
        assert "month_name" in m
        assert "words" in m
        assert "heat_level" in m
        assert 0 <= m["heat_level"] <= 4


def test_get_current_progress():
    result = svc.get_current_progress()
    assert "today" in result
    assert "week" in result
    assert "month" in result
    assert "year" in result
    for period in ["today", "week", "month", "year"]:
        assert "words" in result[period]
        assert "goal" in result[period]
        assert "pct" in result[period]


def test_word_deltas_for_range_empty():
    deltas = svc._word_deltas_for_range(date(2020, 1, 1), date(2020, 1, 2))
    assert isinstance(deltas, dict)


def test_year_goal_pct_bounded():
    result = svc.get_year_overview(2026)
    assert result["year_goal_pct"] >= 0
