"""Tests for chapter_service: CRUD, versioning, reorder, split/merge."""
import pytest

from services import chapter_service
from core.errors import NotFoundError, ValidationError


def test_create_chapter_basic():
    ch = chapter_service.create_chapter(title="Test", content="Hello world.")
    assert ch.id
    assert ch.title == "Test"
    assert ch.word_count == 2
    assert ch.status == "draft"
    assert ch.sort_order == 1


def test_create_chapter_validates_title():
    with pytest.raises(ValidationError):
        chapter_service.create_chapter(title="")
    with pytest.raises(ValidationError):
        chapter_service.create_chapter(title="x" * 600)


def test_update_chapter_creates_version():
    ch = chapter_service.create_chapter(title="Original", content="Original content here.")
    initial_version_count = len(chapter_service.get_chapter_with_versions(ch.id)[1])
    chapter_service.update_chapter(ch.id, content="Updated content here now.")
    updated_versions = chapter_service.get_chapter_with_versions(ch.id)[1]
    assert len(updated_versions) == initial_version_count + 1
    assert updated_versions[0].source == "manual"


def test_autosave_does_not_create_version():
    ch = chapter_service.create_chapter(title="Auto", content="Some content.")
    initial = len(chapter_service.get_chapter_with_versions(ch.id)[1])
    chapter_service.update_chapter(ch.id, content="Autosaved content.", create_version=False)
    after = len(chapter_service.get_chapter_with_versions(ch.id)[1])
    assert after == initial  # no new version


def test_status_change_creates_version():
    ch = chapter_service.create_chapter(title="Status", content="Content.")
    initial = len(chapter_service.get_chapter_with_versions(ch.id)[1])
    chapter_service.update_chapter(ch.id, status="revised")
    after = len(chapter_service.get_chapter_with_versions(ch.id)[1])
    assert after == initial + 1
    assert chapter_service.get_chapter(ch.id).status == "revised"


def test_update_chapter_empty_title_no_change():
    """cycleStatus used to send empty title — must not blank the title."""
    ch = chapter_service.create_chapter(title="My Title", content="Content.")
    chapter_service.update_chapter(ch.id, title="")
    refreshed = chapter_service.get_chapter(ch.id)
    assert refreshed.title == "My Title"


def test_reorder_chapters():
    a = chapter_service.create_chapter(title="A", content="a")
    b = chapter_service.create_chapter(title="B", content="b")
    c = chapter_service.create_chapter(title="C", content="c")
    chapter_service.reorder_chapters([c.id, a.id, b.id])
    assert chapter_service.get_chapter(c.id).sort_order == 1
    assert chapter_service.get_chapter(a.id).sort_order == 2
    assert chapter_service.get_chapter(b.id).sort_order == 3


def test_delete_chapter():
    ch = chapter_service.create_chapter(title="Delete me", content="x")
    chapter_service.delete_chapter(ch.id)
    with pytest.raises(NotFoundError):
        chapter_service.get_chapter(ch.id)


def test_get_neighbors():
    a = chapter_service.create_chapter(title="A", content="a")
    b = chapter_service.create_chapter(title="B", content="b")
    c = chapter_service.create_chapter(title="C", content="c")
    prev, nxt = chapter_service.get_neighbors(b.id)
    assert prev.id == a.id
    assert nxt.id == c.id


def test_split_chapter():
    ch = chapter_service.create_chapter(
        title="Split me",
        content="Para 1.\n\nPara 2.\n\nPara 3.\n\nPara 4.",
    )
    original, new = chapter_service.split_chapter(ch.id, 2)
    assert "Para 1" in original.content
    assert "Para 2" in original.content
    assert "Para 3" in new.content
    assert "Para 4" in new.content


def test_merge_chapters():
    a = chapter_service.create_chapter(title="A", content="Content A.")
    b = chapter_service.create_chapter(title="B", content="Content B.")
    merged = chapter_service.merge_chapters(a.id, b.id)
    assert "Content A." in merged.content
    assert "Content B." in merged.content
    with pytest.raises(NotFoundError):
        chapter_service.get_chapter(b.id)


def test_count_words_english():
    assert chapter_service.count_words("hello world foo bar") == 4
    assert chapter_service.count_words("") == 0
    assert chapter_service.count_words(None) == 0
    assert chapter_service.count_words("   ") == 0
