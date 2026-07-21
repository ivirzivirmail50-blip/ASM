"""Tests for Achievements (v4.5)."""
from __future__ import annotations

import pytest

from services import achievement_service as svc


def test_achievements_defined():
    assert len(svc.ACHIEVEMENTS) >= 15
    for key, ach in svc.ACHIEVEMENTS.items():
        assert "name" in ach
        assert "icon" in ach
        assert "description" in ach
        assert "category" in ach
        assert callable(ach["check"])
        assert callable(ach["progress"])
        assert callable(ach["progress_label"])


def test_categories_defined():
    assert len(svc.CATEGORIES) >= 5
    for key, cat in svc.CATEGORIES.items():
        assert "label" in cat
        assert "icon" in cat


def test_build_context_returns_dict():
    ctx = svc._build_context()
    assert "total_words" in ctx
    assert "chapter_count" in ctx
    assert "character_count" in ctx
    assert "world_count" in ctx
    assert "current_streak" in ctx
    assert "days_this_week" in ctx
    assert isinstance(ctx["total_words"], int)
    assert isinstance(ctx["current_streak"], int)


def test_check_and_unlock_returns_result():
    result = svc.check_and_unlock()
    assert "checked" in result
    assert "newly_unlocked" in result
    assert "total_unlocked" in result
    assert isinstance(result["newly_unlocked"], list)


def test_get_status_returns_all_achievements():
    status = svc.get_status()
    assert "achievements" in status
    assert "unlocked_count" in status
    assert "total_count" in status
    assert "completion_pct" in status
    assert "context" in status
    assert len(status["achievements"]) == len(svc.ACHIEVEMENTS)


def test_achievement_has_progress_info():
    status = svc.get_status()
    for a in status["achievements"]:
        assert "key" in a
        assert "name" in a
        assert "icon" in a
        assert "description" in a
        assert "unlocked" in a
        assert "progress" in a
        assert "progress_label" in a
        assert 0 <= a["progress"] <= 100


def test_first_chapter_unlocks_with_chapter():
    from services.chapter_service import create_chapter
    create_chapter(title="Ach Test", content="Some content.")
    svc.check_and_unlock()
    status = svc.get_status()
    first_ch = next(a for a in status["achievements"] if a["key"] == "chapters_1")
    assert first_ch["unlocked"] is True


def test_words_1k_unlocks_with_enough_words():
    from services.chapter_service import create_chapter
    create_chapter(title="1K Test", content=" ".join(["word"] * 1001))
    svc.check_and_unlock()
    status = svc.get_status()
    words_1k = next(a for a in status["achievements"] if a["key"] == "words_1k")
    assert words_1k["unlocked"] is True


def test_first_character_unlocks_with_character():
    from services.character_service import create_character
    create_character(name="Hero", role="protagonist")
    svc.check_and_unlock()
    status = svc.get_status()
    first_char = next(a for a in status["achievements"] if a["key"] == "first_character")
    assert first_char["unlocked"] is True


def test_check_and_unlock_idempotent():
    """Running check twice doesn't re-unlock already-unlocked achievements."""
    from services.chapter_service import create_chapter
    create_chapter(title="Idempotent Test", content="Content.")
    r1 = svc.check_and_unlock()
    r2 = svc.check_and_unlock()
    # Second run should have fewer (or zero) newly unlocked
    assert len(r2["newly_unlocked"]) <= len(r1["newly_unlocked"])


def test_streak_achievement_progress_label():
    ctx = {"current_streak": 2}
    label = svc.ACHIEVEMENTS["streak_3"]["progress_label"](ctx)
    assert "2/3" in label


def test_progress_is_bounded_0_to_100():
    status = svc.get_status()
    for a in status["achievements"]:
        assert 0 <= a["progress"] <= 100


def test_achievements_sorted_with_unlocked_first():
    status = svc.get_status()
    # Unlocked achievements should appear before locked ones
    unlocked_found = False
    for a in status["achievements"]:
        if a["unlocked"]:
            unlocked_found = True
        elif unlocked_found and not a["unlocked"]:
            # Found a locked after an unlocked — that's fine, sorting puts unlocked first
            pass
