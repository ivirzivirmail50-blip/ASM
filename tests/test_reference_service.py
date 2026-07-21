"""Tests for the Research & References feature (v4.3)."""
from __future__ import annotations

import pytest

from services import reference_service as svc


def test_create_reference_minimal():
    r = svc.create_reference(title="Test Book")
    assert r.id
    assert r.title == "Test Book"
    assert r.source_type == "article"
    assert r.read_status == "unread"
    assert r.priority == "medium"


def test_create_reference_invalid_source_type():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.create_reference(title="x", source_type="bogus")


def test_create_reference_invalid_read_status():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.create_reference(title="x", read_status="bogus")


def test_create_reference_invalid_priority():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.create_reference(title="x", priority="bogus")


def test_create_reference_invalid_rating():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.create_reference(title="x", rating=10)


def test_create_reference_empty_title():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.create_reference(title="")


def test_create_full_reference():
    r = svc.create_reference(
        title="The Hero with a Thousand Faces",
        author="Joseph Campbell",
        url="https://example.com",
        source_type="book",
        publication_date="1949",
        publisher="Princeton University Press",
        isbn_or_doi="ISBN 0691017840",
        description="The classic study of mythic structure",
        quotes=[{"text": "The hero's journey", "page": "23", "notes": ""}],
        tags=["mythology", "structure"],
        read_status="read",
        priority="high",
        rating=5,
        notes="Foundational",
    )
    assert r.author == "Joseph Campbell"
    assert r.source_type == "book"
    assert r.read_status == "read"
    assert r.priority == "high"
    assert r.rating == 5
    from services._common import load_json
    assert load_json(r.quotes, [])[0]["text"] == "The hero's journey"
    assert load_json(r.tags, []) == ["mythology", "structure"]


def test_list_references_filter_by_type():
    svc.create_reference(title="A", source_type="book")
    svc.create_reference(title="B", source_type="article")
    books = svc.list_references(source_type="book")
    assert all(r.source_type == "book" for r in books)


def test_list_references_filter_by_status():
    svc.create_reference(title="A", read_status="read")
    svc.create_reference(title="B", read_status="unread")
    read = svc.list_references(read_status="read")
    assert all(r.read_status == "read" for r in read)


def test_list_references_filter_by_priority():
    svc.create_reference(title="A", priority="high")
    svc.create_reference(title="B", priority="low")
    high = svc.list_references(priority="high")
    assert all(r.priority == "high" for r in high)


def test_list_references_search():
    svc.create_reference(title="Searchable Title", author="Unique Author")
    svc.create_reference(title="Other", author="Different")
    results = svc.list_references(search="Unique")
    assert len(results) == 1
    assert results[0].author == "Unique Author"


def test_list_references_filter_by_tag():
    svc.create_reference(title="A", tags=["alpha"])
    svc.create_reference(title="B", tags=["beta"])
    alpha = svc.list_references(tag="alpha")
    assert len(alpha) == 1
    assert alpha[0].title == "A"


def test_update_reference():
    r = svc.create_reference(title="Old")
    updated = svc.update_reference(r.id, title="New", read_status="read", rating=4)
    assert updated.title == "New"
    assert updated.read_status == "read"
    assert updated.rating == 4


def test_update_reference_invalid_rating():
    r = svc.create_reference(title="X")
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.update_reference(r.id, rating=99)


def test_update_reference_arrays():
    r = svc.create_reference(title="X")
    updated = svc.update_reference(r.id, quotes=[{"text": "Q", "page": "5", "notes": "n"}],
                                   tags=["new_tag"])
    from services._common import load_json
    assert load_json(updated.quotes, [])[0]["text"] == "Q"
    assert load_json(updated.tags, []) == ["new_tag"]


def test_delete_reference():
    r = svc.create_reference(title="X")
    svc.delete_reference(r.id)
    from core.errors import NotFoundError
    with pytest.raises(NotFoundError):
        svc.get_reference(r.id)


def test_to_dict_shape():
    r = svc.create_reference(
        title="T", author="A", source_type="book",
        read_status="read", priority="high", rating=4,
        tags=["t1"], quotes=[{"text": "q", "page": "1", "notes": ""}],
    )
    d = svc.to_dict(r)
    assert d["title"] == "T"
    assert d["source_type_label"] == "Book"
    assert d["source_icon"] == "📚"
    assert d["read_status_label"] == "Read"
    assert d["priority_label"] == "High"
    assert d["rating"] == 4
    assert d["tags"] == ["t1"]
    assert len(d["quotes"]) == 1


def test_all_tags():
    svc.create_reference(title="A", tags=["alpha", "beta"])
    svc.create_reference(title="B", tags=["beta", "gamma"])
    tags = svc.all_tags()
    assert tags == ["alpha", "beta", "gamma"]


def test_stats_empty():
    s = svc.stats()
    assert s["total"] == 0
    assert s["avg_rating"] == 0


def test_stats_with_data():
    svc.create_reference(title="A", read_status="read", priority="high", rating=5)
    svc.create_reference(title="B", read_status="unread", priority="low", rating=3)
    s = svc.stats()
    assert s["total"] >= 2
    assert s["read"] >= 1
    assert s["unread"] >= 1
    assert s["avg_rating"] == 4.0  # (5+3)/2


def test_priority_sort_order():
    svc.create_reference(title="Low", priority="low")
    svc.create_reference(title="High", priority="high")
    svc.create_reference(title="Medium", priority="medium")
    refs = svc.list_references()
    titles = [r.title for r in refs]
    # High should come before Medium and Low
    assert titles.index("High") < titles.index("Low")
    assert titles.index("High") < titles.index("Medium")
