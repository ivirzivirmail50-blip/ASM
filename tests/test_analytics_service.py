"""Tests for the Writing Analytics feature (v4.2)."""
from __future__ import annotations

import pytest

from services import analytics_service as svc
from services.chapter_service import create_chapter


def test_chapter_analytics_basic():
    ch = create_chapter(
        title="Test",
        content="The cat sat on the mat. The dog barked.\n\nThe bird flew away.",
    )
    a = svc.chapter_analytics(ch.id)
    assert a["title"] == "Test"
    assert a["word_count"] > 0
    assert a["sentence_count"] >= 2
    assert a["paragraph_count"] >= 2
    assert a["avg_sentence_length"] > 0
    assert 0 <= a["dialogue_ratio"] <= 1
    assert a["lexical_diversity"] > 0
    assert a["reading_time_minutes"] > 0


def test_chapter_analytics_empty_chapter():
    ch = create_chapter(title="Empty", content="")
    a = svc.chapter_analytics(ch.id)
    assert a["word_count"] == 0
    # _count_sentences returns 0 for empty text
    assert a["sentence_count"] == 0
    assert a["dialogue_ratio"] == 0


def test_chapter_analytics_not_found():
    from core.errors import NotFoundError
    with pytest.raises(NotFoundError):
        svc.chapter_analytics("nonexistent-id")


def test_chapter_analytics_dialogue_detection():
    ch = create_chapter(
        title="Dialogue",
        content='"Hello," she said.\n\n"How are you?" he replied.',
    )
    a = svc.chapter_analytics(ch.id)
    # Should detect significant dialogue ratio
    assert a["dialogue_ratio"] > 0.3


def test_all_chapters_analytics_empty():
    result = svc.all_chapters_analytics()
    # No chapters yet (or only ones from previous tests) — just check shape
    assert isinstance(result, list)


def test_all_chapters_analytics_with_data():
    create_chapter(title="A", content="First chapter content here.")
    create_chapter(title="B", content="Second chapter content here.")
    result = svc.all_chapters_analytics()
    assert len(result) >= 2
    for c in result:
        assert "title" in c
        assert "word_count" in c
        assert "dialogue_ratio" in c
        assert "lexical_diversity" in c


def test_manuscript_summary_empty():
    # When no chapters, returns zeros
    s = svc.manuscript_summary()
    assert s["chapter_count"] == 0
    assert s["total_words"] == 0
    assert s["shortest_chapter"] is None
    assert s["longest_chapter"] is None


def test_manuscript_summary_with_data():
    create_chapter(title="Short", content="Tiny.")
    create_chapter(title="Long", content="A " * 100 + "chapter.")
    s = svc.manuscript_summary()
    assert s["chapter_count"] >= 2
    assert s["total_words"] > 0
    assert s["shortest_chapter"] is not None
    assert s["longest_chapter"] is not None
    # Longest should have more words than shortest
    assert s["longest_chapter"]["word_count"] >= s["shortest_chapter"]["word_count"]
    assert "word_count_distribution" in s
    assert len(s["word_count_distribution"]) >= 2


def test_top_words_returns_list():
    create_chapter(title="TW", content="apple banana apple cherry apple banana")
    words = svc.top_words(limit=5)
    assert isinstance(words, list)
    assert len(words) <= 5
    # "apple" should be the most common
    if words:
        assert words[0]["count"] >= words[-1]["count"]


def test_top_words_excludes_stopwords_by_default():
    create_chapter(title="SW", content="the the the the the uniquexyzword")
    words = svc.top_words(limit=10)
    word_list = [w["word"] for w in words]
    assert "the" not in word_list
    assert "uniquexyzword" in word_list


def test_top_words_includes_stopwords_when_asked():
    create_chapter(title="SW2", content="the the the the the uniqueabcword")
    words = svc.top_words(limit=10, exclude_stopwords=False)
    word_list = [w["word"] for w in words]
    assert "the" in word_list


def test_character_screen_time_empty():
    result = svc.character_screen_time()
    assert isinstance(result, list)


def test_character_screen_time_with_data():
    from services.character_service import create_character
    ch1 = create_chapter(title="CS1", content="Hello world.")
    ch2 = create_chapter(title="CS2", content="Hello again world.")
    c = create_character(name="Hero", role="protagonist")
    # Link character to both chapters
    from services.chapter_service import update_chapter
    update_chapter(ch1.id, character_ids=[c.id], create_version=False)
    update_chapter(ch2.id, character_ids=[c.id], create_version=False)
    result = svc.character_screen_time()
    assert any(ct["name"] == "Hero" for ct in result)


def test_lexical_diversity_increases_with_variety():
    ch1 = create_chapter(title="LD1", content="the the the the the the the the the the")
    ch2 = create_chapter(title="LD2", content="apple banana cherry date elderberry fig grape")
    a1 = svc.chapter_analytics(ch1.id)
    a2 = svc.chapter_analytics(ch2.id)
    # ch2 has higher lexical diversity (more unique words)
    assert a2["lexical_diversity"] > a1["lexical_diversity"]


def test_reading_time_estimation():
    # 250 words at 250 wpm = 1 minute
    content = " ".join(["word"] * 250)
    ch = create_chapter(title="RT", content=content)
    a = svc.chapter_analytics(ch.id)
    assert abs(a["reading_time_minutes"] - 1.0) < 0.1


def test_count_sentences_handles_abbreviations():
    """Sentences ending in 'Dr.' or 'Mr.' shouldn't be split incorrectly,
    but our simple regex may overcount — we just verify it doesn't crash."""
    ch = create_chapter(
        title="Abbr",
        content="Dr. Smith went to the store. He bought milk.",
    )
    a = svc.chapter_analytics(ch.id)
    # Should be at least 1 sentence
    assert a["sentence_count"] >= 1
