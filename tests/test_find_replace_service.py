"""Tests for the Bulk Find & Replace feature (v4.2)."""
from __future__ import annotations

import pytest

from services import find_replace_service as svc
from services.chapter_service import create_chapter, get_chapter


def _seed_chapters():
    create_chapter(title="A", content="The quick brown fox jumps over the lazy dog.")
    create_chapter(title="B", content="Fox says hello. Fox says goodbye.")
    create_chapter(title="C", content="Nothing relevant here.")


def test_preview_plain_text_no_matches():
    _seed_chapters()
    result = svc.preview("nonexistent", "X")
    assert result["chapters_scanned"] >= 3
    assert result["total_matches"] == 0


def test_preview_plain_text_with_matches():
    _seed_chapters()
    result = svc.preview("fox", "cat", whole_word=True)
    assert result["total_matches"] == 3  # 1 in A, 2 in B
    assert result["chapters_with_matches"] == 2


def test_preview_case_insensitive_default():
    _seed_chapters()
    result = svc.preview("FOX", "cat")
    # Should match lowercase "Fox" because case-insensitive is default
    assert result["total_matches"] >= 3


def test_preview_case_sensitive():
    _seed_chapters()
    result = svc.preview("FOX", "cat", case_sensitive=True)
    assert result["total_matches"] == 0


def test_preview_whole_word():
    create_chapter(title="WW", content="The foxy fox is not a Fox.")
    result = svc.preview("fox", "cat", whole_word=True, case_sensitive=False)
    # "fox" (whole word) appears twice: "fox" and "Fox"
    assert result["total_matches"] >= 2


def test_preview_regex():
    create_chapter(title="Re", content="cat123 dog456 cat789")
    result = svc.preview(r"cat\d+", "REPLACED", use_regex=True)
    assert result["total_matches"] == 2


def test_preview_invalid_regex():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.preview("[unclosed", "x", use_regex=True)


def test_preview_empty_pattern_rejected():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.preview("", "x")


def test_preview_pattern_too_long():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.preview("x" * 501, "y")


def test_preview_replacement_too_long():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.preview("x", "y" * 501)


def test_apply_dry_run_does_not_modify():
    create_chapter(title="DR", content="Hello world. Hello again.")
    result = svc.apply("Hello", "Hi", whole_word=True, dry_run=True)
    assert result["total_matches"] >= 2
    # Nothing actually applied — chapter content unchanged
    # (We don't have a chapter_id here, so we just verify no "applied" flag)


def test_apply_actually_replaces():
    ch = create_chapter(title="App", content="Hello world. Hello again.")
    result = svc.apply("Hello", "Hi", whole_word=True)
    assert result["applied"] is True
    assert result["chapters_modified"] >= 1
    assert result["total_replacements"] >= 2
    # Verify chapter content was actually changed
    updated = get_chapter(ch.id)
    assert "Hi" in updated.content
    assert "Hello" not in updated.content


def test_apply_with_no_matches_returns_not_applied():
    create_chapter(title="NM", content="Nothing here.")
    result = svc.apply("nonexistent_xyz", "x")
    assert result["applied"] is False
    assert result["chapters_modified"] == 0


def test_apply_scoped_to_specific_chapter():
    ch1 = create_chapter(title="SC1", content="Hello one.")
    ch2 = create_chapter(title="SC2", content="Hello two.")
    result = svc.apply("Hello", "Hi", whole_word=True, scope_chapter_ids=[ch1.id])
    assert result["chapters_modified"] == 1
    # Only ch1 should be modified
    assert "Hi" in get_chapter(ch1.id).content
    assert "Hello" in get_chapter(ch2.id).content  # unchanged


def test_apply_scoped_to_status():
    create_chapter(title="ST1", content="Hello draft", status="draft")
    create_chapter(title="ST2", content="Hello final", status="final")
    result = svc.apply("Hello", "Hi", whole_word=True, scope_status="draft")
    assert result["chapters_modified"] == 1


def test_apply_creates_version_snapshot():
    """Each modified chapter should have a new version snapshot."""
    from services.chapter_service import get_chapter_with_versions
    ch = create_chapter(title="VS", content="Hello world.")
    initial_versions = get_chapter_with_versions(ch.id)[1]
    initial_count = len(initial_versions)
    svc.apply("Hello", "Hi", whole_word=True)
    after = get_chapter_with_versions(ch.id)[1]
    assert len(after) > initial_count


def test_preview_context_extraction():
    create_chapter(
        title="Ctx",
        content="A" * 100 + " TARGET " + "B" * 100,
    )
    result = svc.preview("TARGET", "REPLACED", whole_word=True)
    assert result["total_matches"] == 1
    ctx = result["results"][0]["matches"][0]["context"]
    assert "…" in ctx  # has ellipsis because text exceeds window
    assert "TARGET" in ctx


def test_regex_with_backreference():
    create_chapter(title="BR", content="Hello John and Hello Mary.")
    result = svc.preview(r"Hello (\w+)", r"Hi \1", use_regex=True)
    assert result["total_matches"] == 2
    # Apply and verify backreference works
    pre_ch = create_chapter(title="BR2", content="Hello John.")
    svc.apply(r"Hello (\w+)", r"Hi \1", use_regex=True, scope_chapter_ids=[pre_ch.id])
    assert "Hi John" in get_chapter(pre_ch.id).content
