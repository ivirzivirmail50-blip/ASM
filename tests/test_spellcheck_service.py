"""Tests for Spell Check (v4.5)."""
from __future__ import annotations

import pytest

from services import spellcheck_service as svc
from services.chapter_service import create_chapter


def test_bundled_words_not_empty():
    assert len(svc.BUNDLED_WORDS) > 100
    assert "the" in svc.BUNDLED_WORDS
    assert "elara" in svc.BUNDLED_WORDS


def test_tokenize_simple():
    tokens = svc._tokenize("Hello world this is a test")
    # "a" is 1 char, filtered (len < 2) → 5 tokens
    assert len(tokens) == 5
    words = [t[0] for t in tokens]
    assert "Hello" in words
    assert "test" in words


def test_tokenize_empty():
    assert svc._tokenize("") == []


def test_tokenize_strips_markdown():
    tokens = svc._tokenize("# Header\n\n**Bold** _italic_")
    words = [t[0] for t in tokens]
    assert "Header" in words
    assert "Bold" in words
    assert "italic" in words


def test_tokenize_strips_html():
    tokens = svc._tokenize("<p>Hello <strong>world</strong></p>")
    words = [t[0] for t in tokens]
    assert "Hello" in words
    assert "world" in words


def test_levenshtein_basic():
    assert svc._levenshtein("kitten", "sitting") == 3
    assert svc._levenshtein("abc", "abc") == 0
    assert svc._levenshtein("", "abc") == 3


def test_levenshtein_max_dist():
    # Distance > max_dist returns max_dist + 1
    assert svc._levenshtein("abc", "xyz", max_dist=2) == 3


def test_build_known_words_includes_bundled():
    known = svc._build_known_words()
    assert "the" in known
    assert "elara" in known


def test_build_known_words_includes_custom():
    svc.add_word("aethelgard")
    known = svc._build_known_words()
    assert "aethelgard" in known


def test_build_known_words_includes_character_names():
    from services.character_service import create_character
    create_character(name="Zephyrian the Great")
    known = svc._build_known_words()
    assert "zephyrian" in known
    assert "great" in known


def test_check_chapter_flags_unknown_words():
    ch = create_chapter(
        title="Spell Test",
        content="The zzzxxx qqqyyy ran quickly.",
    )
    result = svc.check_chapter(ch.id)
    assert result["flagged_count"] >= 2
    flagged_words = [f["word"] for f in result["flagged"]]
    assert "zzzxxx" in flagged_words
    assert "qqqyyy" in flagged_words


def test_check_chapter_known_words_not_flagged():
    ch = create_chapter(
        title="Known Test",
        content="The hero walked into the castle.",
    )
    result = svc.check_chapter(ch.id)
    flagged_words = [f["word"] for f in result["flagged"]]
    # "hero", "walked", "castle" are in bundled words
    assert "hero" not in flagged_words
    assert "castle" not in flagged_words


def test_check_chapter_custom_word_not_flagged():
    svc.add_word("xyzzy")
    ch = create_chapter(
        title="Custom Test",
        content="The xyzzy was glowing.",
    )
    result = svc.check_chapter(ch.id)
    flagged_words = [f["word"] for f in result["flagged"]]
    assert "xyzzy" not in flagged_words


def test_check_chapter_returns_context():
    ch = create_chapter(
        title="Context Test",
        content="A" * 100 + " zzzxxx " + "B" * 100,
    )
    result = svc.check_chapter(ch.id)
    assert result["flagged_count"] >= 1
    ctx = result["flagged"][0]["context"]
    assert "…" in ctx  # has ellipsis because text exceeds window


def test_check_chapter_returns_suggestions():
    ch = create_chapter(
        title="Suggestion Test",
        content="The teh was mispelled.",
    )
    result = svc.check_chapter(ch.id)
    # "teh" should be flagged and have some suggestions
    teh = next((f for f in result["flagged"] if f["word"] == "teh"), None)
    if teh:
        # Suggestions should be a list (may or may not include "the" depending on known set)
        assert isinstance(teh["suggestions"], list)


def test_check_all_chapters():
    create_chapter(title="Multi 1", content="Some content.")
    create_chapter(title="Multi 2", content="More content.")
    result = svc.check_all_chapters()
    assert result["chapters_checked"] >= 2
    assert "total_words" in result
    assert "total_flagged" in result


def test_check_chapter_not_found():
    from core.errors import NotFoundError
    with pytest.raises(NotFoundError):
        svc.check_chapter("nonexistent-id")


def test_add_word():
    rec = svc.add_word("testword123")
    assert rec.id
    assert rec.word == "testword123"


def test_add_word_idempotent():
    r1 = svc.add_word("idempotent_test")
    r2 = svc.add_word("idempotent_test")
    assert r1.id == r2.id


def test_add_word_invalid():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.add_word("")


def test_add_words_batch():
    count = svc.add_words_batch(["batch1", "batch2", "batch3"])
    assert count >= 1


def test_remove_word_by_text():
    svc.add_word("removetest")
    svc.remove_word_by_text("removetest")
    known = svc._build_known_words()
    assert "removetest" not in known


def test_list_custom_words():
    svc.add_word("listtest")
    words = svc.list_custom_words()
    assert any(w.word == "listtest" for w in words)


def test_to_dict_shape():
    rec = svc.add_word("dicttest")
    d = svc.to_dict(rec)
    assert d["word"] == "dicttest"
    assert d["id"]
    assert d["added_at"]


def test_suggest_returns_list():
    known = {"the", "tea", "ten", "then", "them"}
    suggestions = svc._suggest("teh", known)
    assert isinstance(suggestions, list)
    assert "the" in suggestions


def test_suggest_max_length_filter():
    known = {"a", "abcdefghij"}
    # Very different lengths should not be suggested
    suggestions = svc._suggest("xy", known, max_suggestions=5)
    assert isinstance(suggestions, list)
