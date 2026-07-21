"""Tests for the Glossary & Style Sheet feature (v4.2)."""
from __future__ import annotations

import pytest

from services import glossary_service as svc


def test_create_entry_minimal():
    e = svc.create_entry(term="Elara", category="character")
    assert e.id
    assert e.term == "Elara"
    assert e.category == "character"


def test_create_entry_invalid_category():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.create_entry(term="x", category="bogus")


def test_create_entry_empty_term():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.create_entry(term="", category="other")


def test_create_entry_with_alts_and_forbidden():
    e = svc.create_entry(
        term="Elara",
        category="character",
        alternates=["El", "Lara"],
        forbidden=["Ellara"],
        case_sensitive=True,
    )
    from services._common import load_json
    assert load_json(e.alternates, []) == ["El", "Lara"]
    assert load_json(e.forbidden, []) == ["Ellara"]
    assert e.case_sensitive == 1


def test_list_entries_filter_by_category():
    svc.create_entry(term="A", category="character")
    svc.create_entry(term="B", category="place")
    chars = svc.list_entries(category="character")
    assert all(e.category == "character" for e in chars)


def test_update_entry():
    e = svc.create_entry(term="Old", category="other")
    svc.update_entry(e.id, term="New", category="character", alternates=["n1"])
    updated = svc.get_entry(e.id)
    assert updated.term == "New"
    assert updated.category == "character"


def test_delete_entry():
    e = svc.create_entry(term="x", category="other")
    svc.delete_entry(e.id)
    from core.errors import NotFoundError
    with pytest.raises(NotFoundError):
        svc.get_entry(e.id)


def test_to_dict_shape():
    e = svc.create_entry(
        term="T", category="character", definition="D",
        alternates=["a"], forbidden=["b"], notes="N",
    )
    d = svc.to_dict(e)
    assert d["term"] == "T"
    assert d["category_label"] == "Character"
    assert d["icon"] == "👤"
    assert d["alternates"] == ["a"]
    assert d["forbidden"] == ["b"]
    assert d["definition"] == "D"
    assert d["notes"] == "N"
    assert d["case_sensitive"] is False


def test_scan_empty_glossary_returns_zero():
    result = svc.scan_chapters()
    assert result["chapters_scanned"] == 0
    assert result["issues"] == []
    assert result["presence"] == []


def test_scan_finds_forbidden_variants():
    # Set up: glossary entry forbids "Ellara", chapter contains it
    from services.chapter_service import create_chapter
    svc.create_entry(
        term="Elara", category="character",
        forbidden=["Ellara"],
    )
    create_chapter(
        title="Test Chapter",
        content="Ellara walked into the tavern. Ellara ordered a drink.",
    )
    result = svc.scan_chapters()
    assert result["chapters_scanned"] >= 1
    # Should find at least one forbidden-issue
    forbidden_issues = [i for i in result["issues"] if i["type"] == "forbidden"]
    assert len(forbidden_issues) >= 1
    assert forbidden_issues[0]["found"] == "Ellara"
    assert forbidden_issues[0]["term"] == "Elara"
    assert forbidden_issues[0]["count"] == 2


def test_scan_finds_near_misses():
    from services.chapter_service import create_chapter
    svc.create_entry(term="Elara", category="character")
    # "Elira" is Levenshtein distance 1 from "Elara"
    create_chapter(
        title="Near miss chapter",
        content="Elira walked into the tavern.",
    )
    result = svc.scan_chapters()
    near_miss = [i for i in result["issues"] if i["type"] == "near_miss"]
    assert any(i["found"].lower() == "elira" for i in near_miss)


def test_scan_presence_tracking():
    from services.chapter_service import create_chapter
    svc.create_entry(
        term="Elara", category="character",
        alternates=["El"],
    )
    create_chapter(
        title="Presence test",
        content="Elara and El walked together. Elara smiled.",
    )
    result = svc.scan_chapters()
    assert any(p["term"] == "Elara" and p["count"] >= 3 for p in result["presence"])


def test_scan_respects_alternates():
    """Alternates should not be flagged as near-misses."""
    from services.chapter_service import create_chapter
    svc.create_entry(
        term="Elara", category="character",
        alternates=["El", "Lara"],
    )
    create_chapter(
        title="Alternates test",
        content="El and Lara walked together.",
    )
    result = svc.scan_chapters()
    # No issues for El or Lara (they're alternates)
    near_miss_for_alts = [
        i for i in result["issues"]
        if i["type"] == "near_miss" and i["found"].lower() in ("el", "lara")
    ]
    assert near_miss_for_alts == []


def test_scan_case_sensitive():
    from services.chapter_service import create_chapter
    svc.create_entry(
        term="Council", category="other",
        case_sensitive=True,
    )
    create_chapter(title="CS test", content="The council met today.")
    result = svc.scan_chapters()
    # In case-sensitive mode, lowercase "council" is a near-miss (distance 0 case... no, distance is 1 because 'c' != 'C')
    # Actually Levenshtein with case-sensitive comparison counts case difference as distance 1
    near_miss = [i for i in result["issues"] if i["type"] == "near_miss"]
    # Should find "council" as a near-miss of "Council"
    assert any(i["found"] == "council" for i in near_miss)


def test_levenshtein_basic():
    assert svc._levenshtein("kitten", "sitting") == 3
    assert svc._levenshtein("", "abc") == 3
    assert svc._levenshtein("abc", "abc") == 0
    assert svc._levenshtein("Elara", "Elira") == 1


def test_seed_default_glossary_idempotent():
    svc.seed_default_glossary()
    n1 = len(svc.list_entries())
    svc.seed_default_glossary()
    n2 = len(svc.list_entries())
    assert n1 == n2  # doesn't double-seed
