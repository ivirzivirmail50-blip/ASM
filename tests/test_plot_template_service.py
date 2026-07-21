"""Tests for the Plot Structure Templates feature (v4.1)."""
from __future__ import annotations

import pytest

from services import plot_template_service as svc
from services import plan_service


def test_list_templates_returns_six():
    templates = svc.list_templates()
    assert len(templates) == 6
    keys = {t["key"] for t in templates}
    assert {"heros_journey", "save_the_cat", "three_act", "seven_point",
            "freytag", "kishotenketsu"} <= keys


def test_each_template_has_beats():
    for t in svc.list_templates():
        assert t["beat_count"] >= 4, f"{t['key']} has too few beats"
        tmpl = svc.get_template(t["key"])
        assert tmpl
        assert len(tmpl["beats"]) == t["beat_count"]
        for beat in tmpl["beats"]:
            name, desc, status, event_type = beat
            assert name and desc and status and event_type
            assert status in plan_service.STATUS_COLUMNS


def test_get_template_unknown_returns_none():
    assert svc.get_template("nonexistent") is None


def test_apply_template_creates_plans():
    result = svc.apply_template("three_act")
    assert result["template"] == "three_act"
    assert result["beats_created"] == 7
    assert result["track"] == "plot:three_act"
    assert len(result["plan_ids"]) == 7
    # Verify plans exist on the right track
    plans = plan_service.list_plans(track="plot:three_act")
    assert len(plans) == 7
    # First plan title should be "[01] Act I — Setup"
    titles = [p.title for p in plans]
    assert "[01]" in titles[0]
    assert "Setup" in titles[0]


def test_apply_template_invalid_key_raises():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.apply_template("nonexistent")


def test_apply_heros_journey_creates_12_beats():
    result = svc.apply_template("heros_journey")
    assert result["beats_created"] == 12
    plans = plan_service.list_plans(track="plot:heros_journey")
    assert len(plans) == 12
    # Last beat should be the Return with the Elixir
    last = sorted(plans, key=lambda p: p.title)[11]
    assert "Return" in last.title


def test_apply_save_the_cat_creates_15_beats():
    result = svc.apply_template("save_the_cat")
    assert result["beats_created"] == 15


def test_apply_seven_point_creates_7_beats():
    result = svc.apply_template("seven_point")
    assert result["beats_created"] == 7


def test_apply_freytag_creates_5_beats():
    result = svc.apply_template("freytag")
    assert result["beats_created"] == 5


def test_apply_kishotenketsu_creates_4_beats():
    result = svc.apply_template("kishotenketsu")
    assert result["beats_created"] == 4


def test_applied_plans_have_descriptions():
    svc.apply_template("freytag")
    plans = plan_service.list_plans(track="plot:freytag")
    for p in plans:
        assert p.description
        assert "Beat" in p.description
        assert "Freytag" in p.description


def test_applied_plans_have_tags():
    svc.apply_template("freytag")
    plans = plan_service.list_plans(track="plot:freytag")
    for p in plans:
        from services._common import load_json
        tags = load_json(p.tags, [])
        assert "plot_template" in tags
        assert "freytag" in tags


def test_applied_plans_have_event_type():
    svc.apply_template("freytag")
    plans = plan_service.list_plans(track="plot:freytag")
    for p in plans:
        assert p.event_type  # all beats set an event_type


def test_multiple_templates_can_coexist():
    svc.apply_template("three_act")
    svc.apply_template("freytag")
    three_act = plan_service.list_plans(track="plot:three_act")
    freytag = plan_service.list_plans(track="plot:freytag")
    assert len(three_act) == 7
    assert len(freytag) == 5
