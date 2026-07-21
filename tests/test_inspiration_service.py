"""Tests for the Inspiration Hub (v4.1)."""
from __future__ import annotations

import pytest

from services import inspiration_service as svc


def test_daily_prompt_is_deterministic():
    from datetime import datetime, timezone
    d = datetime(2026, 7, 15, tzinfo=timezone.utc)
    p1 = svc.daily_prompt(d)
    p2 = svc.daily_prompt(d)
    assert p1 == p2
    assert "text" in p1
    assert "category" in p1
    assert p1["date"] == "2026-07-15"


def test_daily_prompt_different_dates_yield_different_prompts():
    from datetime import datetime, timezone
    seen = set()
    # Try a range of dates — at least 3 distinct prompts should appear
    for day in range(1, 30):
        d = datetime(2026, 7, day, tzinfo=timezone.utc)
        p = svc.daily_prompt(d)
        seen.add(p["text"])
    assert len(seen) >= 3


def test_random_prompt_returns_well_formed_dict():
    p = svc.random_prompt()
    assert p["category"] in svc.PROMPT_CATEGORIES
    assert p["text"]
    assert p["category_label"]
    assert p["icon"]


def test_random_prompt_specific_category():
    p = svc.random_prompt(category="conflict")
    assert p["category"] == "conflict"


def test_random_prompt_unknown_category_falls_back():
    # Should fall back to any category rather than crash
    p = svc.random_prompt(category="nonexistent")
    assert p["category"] in svc.PROMPT_CATEGORIES


def test_random_scenario_has_all_parts():
    s = svc.random_scenario()
    assert "parts" in s
    assert "prose" in s
    for key in ("protagonist", "setting", "goal", "obstacle", "twist"):
        assert key in s["parts"]
        assert s["parts"][key]
    assert s["prose"]


def test_random_scenario_prose_starts_with_capital():
    s = svc.random_scenario()
    assert s["prose"][0].isupper()


def test_categories_returns_list():
    cats = svc.categories()
    assert isinstance(cats, list)
    assert len(cats) >= 5
    for c in cats:
        assert c["key"] and c["label"] and c["icon"] and c["count"] > 0


def test_prompts_for_known_category():
    prompts = svc.prompts_for("opening")
    assert len(prompts) >= 5
    assert all(isinstance(p, str) and p for p in prompts)


def test_prompts_for_unknown_category_returns_empty():
    assert svc.prompts_for("nonexistent") == []


def test_save_and_list_inspiration():
    rec = svc.save_inspiration(
        kind="prompt", category="opening",
        title="Test prompt", body="A test prompt body.",
    )
    assert rec.id
    saved = svc.list_saved()
    assert any(s.id == rec.id for s in saved)
    d = svc.to_dict(saved[0])
    assert d["kind"] == "prompt"
    assert d["body"] == "A test prompt body."


def test_save_invalid_kind_rejected():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.save_inspiration(kind="bogus", category="x", body="y")


def test_save_empty_body_rejected():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.save_inspiration(kind="prompt", category="x", body="")


def test_toggle_pin():
    rec = svc.save_inspiration(kind="prompt", category="x", body="hi")
    assert not rec.pinned
    rec2 = svc.toggle_pin(rec.id)
    assert rec2.pinned
    rec3 = svc.toggle_pin(rec.id)
    assert not rec3.pinned


def test_mark_used():
    rec = svc.save_inspiration(kind="scenario", category="combo", body="hi")
    assert not rec.used
    rec2 = svc.mark_used(rec.id)
    assert rec2.used


def test_list_saved_pinned_first():
    a = svc.save_inspiration(kind="prompt", category="x", body="A")
    b = svc.save_inspiration(kind="prompt", category="x", body="B")
    svc.toggle_pin(b.id)
    saved = svc.list_saved()
    # Pinned (b) should come first
    assert saved[0].id == b.id


def test_list_saved_filtered_by_kind():
    svc.save_inspiration(kind="prompt", category="x", body="A")
    svc.save_inspiration(kind="scenario", category="combo", body="B")
    prompts = svc.list_saved(kind="prompt")
    assert all(p.kind == "prompt" for p in prompts)
    scenarios = svc.list_saved(kind="scenario")
    assert all(p.kind == "scenario" for p in scenarios)


def test_delete_inspiration():
    rec = svc.save_inspiration(kind="prompt", category="x", body="hi")
    svc.delete_inspiration(rec.id)
    saved = svc.list_saved()
    assert not any(s.id == rec.id for s in saved)


def test_to_dict_full_shape():
    rec = svc.save_inspiration(
        kind="scenario", category="combo",
        title="T", body="B", meta={"parts": {"x": "y"}},
    )
    d = svc.to_dict(rec)
    assert d["kind"] == "scenario"
    assert d["category"] == "combo"
    assert d["title"] == "T"
    assert d["body"] == "B"
    assert d["meta"] == {"parts": {"x": "y"}}
    assert d["pinned"] is False
    assert d["used"] is False
    assert d["created_at"]
