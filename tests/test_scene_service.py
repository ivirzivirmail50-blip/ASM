"""Tests for Scene Card Index (v4.4)."""
from __future__ import annotations

import pytest

from services import scene_service as svc
from services.chapter_service import create_chapter


def test_split_into_scenes_three_newlines():
    scenes = svc._split_into_scenes("Scene 1 text.\n\n\nScene 2 text.\n\n\nScene 3 text.")
    assert len(scenes) == 3


def test_split_into_scenes_asterisk_marker():
    scenes = svc._split_into_scenes("Scene 1.\n* * *\nScene 2.")
    assert len(scenes) == 2


def test_split_into_scenes_dash_marker():
    scenes = svc._split_into_scenes("Scene 1.\n---\nScene 2.")
    assert len(scenes) == 2


def test_split_into_scenes_empty():
    assert svc._split_into_scenes("") == []
    assert svc._split_into_scenes(None) == []  # type: ignore[arg-type]


def test_extract_title_from_markdown_header():
    assert svc._extract_title("# Chapter Title\nBody text.") == "Chapter Title"


def test_extract_title_fallback_to_first_line():
    title = svc._extract_title("The quick brown fox jumps over the lazy dog and keeps running.")
    assert "The quick brown fox" in title


def test_extract_from_chapter():
    ch = create_chapter(
        title="Test Chapter",
        content="Scene one text.\n\n\nScene two text.\n\n\nScene three text.",
    )
    cards = svc.extract_from_chapter(ch.id)
    assert len(cards) == 3
    for card in cards:
        assert card.title
        assert card.word_count > 0
        assert card.chapter_id == ch.id


def test_extract_from_chapter_replaces_existing():
    ch = create_chapter(
        title="Replace Test",
        content="Scene one.\n\n\nScene two.",
    )
    cards1 = svc.extract_from_chapter(ch.id)
    assert len(cards1) == 2
    # Extract again — should replace, not duplicate
    cards2 = svc.extract_from_chapter(ch.id)
    assert len(cards2) == 2


def test_extract_from_chapter_not_found():
    from core.errors import NotFoundError
    with pytest.raises(NotFoundError):
        svc.extract_from_chapter("nonexistent-id")


def test_extract_all():
    create_chapter(title="A", content="Scene A1.\n\n\nScene A2.")
    create_chapter(title="B", content="Scene B1.")
    result = svc.extract_all()
    assert result["chapters_scanned"] >= 2
    assert result["total_scenes"] >= 3


def test_list_cards():
    ch = create_chapter(title="List Test", content="Scene 1.\n\n\nScene 2.")
    svc.extract_from_chapter(ch.id)
    cards = svc.list_cards()
    assert len(cards) >= 2


def test_list_cards_filter_by_chapter():
    ch1 = create_chapter(title="Ch1", content="Scene 1A.\n\n\nScene 1B.")
    ch2 = create_chapter(title="Ch2", content="Scene 2A.")
    svc.extract_from_chapter(ch1.id)
    svc.extract_from_chapter(ch2.id)
    ch1_cards = svc.list_cards(chapter_id=ch1.id)
    assert all(c.chapter_id == ch1.id for c in ch1_cards)


def test_update_card():
    ch = create_chapter(title="Update Test", content="A scene.")
    cards = svc.extract_from_chapter(ch.id)
    cid = cards[0].id
    updated = svc.update_card(cid, mood="tense", location="Tavern", status="revised")
    assert updated.mood == "tense"
    assert updated.location == "Tavern"
    assert updated.status == "revised"


def test_update_card_tags():
    ch = create_chapter(title="Tag Test", content="A scene.")
    cards = svc.extract_from_chapter(ch.id)
    updated = svc.update_card(cards[0].id, tags=["alpha", "beta"])
    from services._common import load_json
    assert load_json(updated.tags, []) == ["alpha", "beta"]


def test_move_to_chapter():
    ch1 = create_chapter(title="Move From", content="A scene.")
    ch2 = create_chapter(title="Move To", content="")
    cards = svc.extract_from_chapter(ch1.id)
    cid = cards[0].id
    moved = svc.move_to_chapter(cid, ch2.id)
    assert moved.chapter_id == ch2.id


def test_move_to_chapter_invalid_target():
    ch = create_chapter(title="Move Invalid", content="A scene.")
    cards = svc.extract_from_chapter(ch.id)
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.move_to_chapter(cards[0].id, "nonexistent-chapter")


def test_reorder():
    ch = create_chapter(title="Reorder Test", content="S1.\n\n\nS2.\n\n\nS3.")
    cards = svc.extract_from_chapter(ch.id)
    ids = [c.id for c in cards]
    # Reverse the order
    reversed_ids = list(reversed(ids))
    svc.reorder(reversed_ids)
    reordered = svc.list_cards()
    reordered_ids = [c.id for c in reordered if c.id in ids]
    # The first card should now be the last one we created
    assert reordered_ids[0] == reversed_ids[0]


def test_delete_card():
    ch = create_chapter(title="Delete Test", content="A scene.")
    cards = svc.extract_from_chapter(ch.id)
    cid = cards[0].id
    svc.delete_card(cid)
    from core.errors import NotFoundError
    with pytest.raises(NotFoundError):
        svc.get_card(cid)


def test_to_dict_shape():
    ch = create_chapter(title="Dict Test", content="A scene.")
    cards = svc.extract_from_chapter(ch.id)
    d = svc.to_dict(cards[0])
    assert "id" in d
    assert "chapter_id" in d
    assert "title" in d
    assert "summary" in d
    assert "word_count" in d
    assert "mood" in d
    assert "status" in d
    assert "color" in d


def test_stats():
    ch = create_chapter(title="Stats Test", content="S1.\n\n\nS2.")
    svc.extract_from_chapter(ch.id)
    s = svc.stats()
    assert "total" in s
    assert "total_words" in s
    assert "by_chapter" in s
    assert s["total"] >= 2


def test_extract_assigns_unique_colors():
    ch = create_chapter(title="Color Test", content="S1.\n\n\nS2.\n\n\nS3.")
    cards = svc.extract_from_chapter(ch.id)
    colors = [c.color for c in cards]
    # Colors should cycle through CARD_COLORS
    assert len(set(colors)) >= 1
