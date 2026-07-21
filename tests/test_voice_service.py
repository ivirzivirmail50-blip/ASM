"""Tests for the Character Voice Profiles feature (v4.3)."""
from __future__ import annotations

import pytest

from services import voice_service as svc
from services.character_service import create_character


def _make_character(name="Test Hero", role="protagonist"):
    return create_character(name=name, role=role)


def test_get_or_create_creates_profile():
    c = _make_character()
    v = svc.get_or_create(c.id)
    assert v.id
    assert v.character_id == c.id
    assert v.speech_verbosity == "moderate"
    assert v.formality == "neutral"
    assert v.uses_contractions is True


def test_get_or_create_idempotent():
    c = _make_character()
    v1 = svc.get_or_create(c.id)
    v2 = svc.get_or_create(c.id)
    assert v1.id == v2.id


def test_get_profile_returns_none_when_not_exists():
    c = _make_character()
    assert svc.get_profile(c.id) is None


def test_get_or_create_character_not_found():
    from core.errors import NotFoundError
    with pytest.raises(NotFoundError):
        svc.get_or_create("nonexistent-id")


def test_update_profile():
    c = _make_character()
    svc.get_or_create(c.id)
    updated = svc.update_profile(c.id, speech_verbosity="terse", formality="archaic")
    assert updated.speech_verbosity == "terse"
    assert updated.formality == "archaic"


def test_update_profile_arrays():
    c = _make_character()
    svc.get_or_create(c.id)
    updated = svc.update_profile(
        c.id,
        favorite_words=["indeed", "nevertheless"],
        avoided_words=["okay", "cool"],
        catchphrases=["By the old gods"],
    )
    from services._common import load_json
    assert load_json(updated.favorite_words, []) == ["indeed", "nevertheless"]
    assert load_json(updated.avoided_words, []) == ["okay", "cool"]
    assert load_json(updated.catchphrases, []) == ["By the old gods"]


def test_update_profile_contractions():
    c = _make_character()
    svc.get_or_create(c.id)
    updated = svc.update_profile(c.id, uses_contractions=False)
    assert updated.uses_contractions is False


def test_to_dict_shape():
    c = _make_character(name="Elara")
    svc.get_or_create(c.id)
    updated = svc.update_profile(c.id, speech_verbosity="verbose", formality="formal",
                                  typical_sentence_length="long", uses_contractions=False,
                                  favorite_words=["indeed"], catchphrases=["By the gods"])
    d = svc.to_dict(updated)
    assert d["character_id"] == c.id
    assert d["verbosity_label"] == "Verbose"
    assert d["formality_label"] == "Formal"
    assert d["sentence_length_label"] == "Long"
    assert d["uses_contractions"] is False
    assert d["favorite_words"] == ["indeed"]
    assert d["catchphrases"] == ["By the gods"]


def test_scan_dialogue_no_profile():
    c = _make_character()
    result = svc.scan_dialogue(c.id)
    assert "issues" in result
    assert result["dialogue_lines_found"] == 0


def test_scan_dialogue_finds_avoided_words():
    from services.chapter_service import create_chapter, update_chapter
    c = _make_character(name="Elara")
    svc.update_profile(c.id, avoided_words=["okay"])
    ch = create_chapter(
        title="Test",
        content='"Hey, okay, that works for me," Elara said.',
    )
    update_chapter(ch.id, character_ids=[c.id], create_version=False)
    result = svc.scan_dialogue(c.id)
    assert result["dialogue_lines_found"] >= 1
    avoided_issues = [i for i in result["issues"] if i["type"] == "avoided_word"]
    assert any(i["word"] == "okay" for i in avoided_issues)


def test_scan_dialogue_counts_catchphrases():
    from services.chapter_service import create_chapter, update_chapter
    c = _make_character(name="Hero")
    svc.update_profile(c.id, catchphrases=["By the old gods"])
    ch = create_chapter(
        title="CP Test",
        content='"By the old gods, what is that?" she whispered. "By the old gods!"',
    )
    update_chapter(ch.id, character_ids=[c.id], create_version=False)
    result = svc.scan_dialogue(c.id)
    assert result["catchphrase_hits"] >= 2  # appears twice


def test_scan_dialogue_only_scans_linked_chapters():
    from services.chapter_service import create_chapter
    c = _make_character()
    svc.update_profile(c.id, avoided_words=["okay"])
    # Chapter NOT linked to character
    create_chapter(title="Not linked", content='"okay okay okay"')
    result = svc.scan_dialogue(c.id)
    assert result["chapters_scanned"] == 0
    assert result["dialogue_lines_found"] == 0


def test_consistency_summary_includes_key_elements():
    c = _make_character(name="Elara")
    svc.update_profile(
        c.id,
        speech_verbosity="verbose",
        formality="formal",
        favorite_words=["indeed"],
        avoided_words=["okay"],
        catchphrases=["By the gods"],
    )
    summary = svc.consistency_summary(c.id)
    assert "Elara" in summary
    assert "verbose" in summary.lower()
    assert "formal" in summary.lower()
    assert "indeed" in summary
    assert "okay" in summary
    assert "By the gods" in summary


def test_consistency_summary_no_profile():
    c = _make_character()
    # Don't create profile
    summary = svc.consistency_summary(c.id)
    assert "No voice profile" in summary


def test_scan_dialogue_length_match():
    from services.chapter_service import create_chapter, update_chapter
    c = _make_character()
    # Declare long sentences but write short dialogue
    svc.update_profile(c.id, typical_sentence_length="long")
    ch = create_chapter(
        title="Length test",
        content='"No." "Yes." "Go." "Stop." "Wait."',
    )
    update_chapter(ch.id, character_ids=[c.id], create_version=False)
    result = svc.scan_dialogue(c.id)
    # Average sentence length should be very short
    assert result["actual_avg_sentence_length"] < 5
    assert result["length_match"] == "shorter_than_declared"


def test_extract_dialogue_lines():
    lines = svc._extract_dialogue_lines('"Hello there." She waved. "How are you?"')
    assert len(lines) == 2
    assert lines[0] == "Hello there."
    assert lines[1] == "How are you?"


def test_extract_dialogue_lines_smart_quotes():
    lines = svc._extract_dialogue_lines('\u201cHello.\u201d')
    assert len(lines) == 1
    assert lines[0] == "Hello."
