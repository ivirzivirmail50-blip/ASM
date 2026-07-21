"""Tests for the Notes & Ideas Inbox feature (v4.1)."""
from __future__ import annotations

import pytest

from services import note_service as svc


def test_create_note_minimal():
    n = svc.create_note(title="Hello", body="World", category="idea")
    assert n.id
    assert n.title == "Hello"
    assert n.body == "World"
    assert n.category == "idea"
    assert not n.pinned
    assert not n.done


def test_create_note_invalid_category():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.create_note(title="x", body="y", category="bogus")


def test_create_note_requires_title_or_body():
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.create_note(title="", body="", category="idea")


def test_create_note_with_tags_and_links():
    n = svc.create_note(
        title="Tagged note",
        body="Body",
        category="todo",
        tags=["research", "ch3"],
        links=[{"entity_type": "chapter", "entity_id": "abc", "entity_title": "Ch 1"}],
        pinned=True,
    )
    assert n.pinned
    from services._common import load_json
    assert load_json(n.tags, []) == ["research", "ch3"]
    assert len(load_json(n.links, [])) == 1


def test_list_notes_returns_in_project():
    svc.create_note(title="A", body="", category="idea")
    svc.create_note(title="B", body="", category="todo")
    notes = svc.list_notes()
    assert len(notes) >= 2


def test_list_notes_pinned_first():
    a = svc.create_note(title="A", body="", category="idea")
    b = svc.create_note(title="B", body="", category="idea", pinned=True)
    notes = svc.list_notes()
    # B is pinned, should come first
    assert notes[0].id == b.id


def test_list_notes_filter_by_category():
    svc.create_note(title="A", body="", category="idea")
    svc.create_note(title="B", body="", category="todo")
    ideas = svc.list_notes(category="idea")
    assert all(n.category == "idea" for n in ideas)
    todos = svc.list_notes(category="todo")
    assert all(n.category == "todo" for n in todos)


def test_list_notes_search_in_title_and_body():
    svc.create_note(title="Findable keyword", body="", category="idea")
    svc.create_note(title="Other", body="has keyword in body", category="idea")
    svc.create_note(title="Unrelated", body="", category="idea")
    results = svc.list_notes(search="keyword")
    assert len(results) == 2


def test_list_notes_filter_by_tag():
    svc.create_note(title="A", body="", category="idea", tags=["alpha"])
    svc.create_note(title="B", body="", category="idea", tags=["beta"])
    svc.create_note(title="C", body="", category="idea", tags=["alpha", "beta"])
    alpha = svc.list_notes(tag="alpha")
    assert len(alpha) == 2  # A and C


def test_update_note():
    n = svc.create_note(title="Old", body="Old body", category="idea")
    svc.update_note(n.id, title="New", body="New body", category="todo")
    updated = svc.get_note(n.id)
    assert updated.title == "New"
    assert updated.body == "New body"
    assert updated.category == "todo"


def test_toggle_pin():
    n = svc.create_note(title="x", body="", category="idea")
    assert not n.pinned
    n2 = svc.toggle_pin(n.id)
    assert n2.pinned
    n3 = svc.toggle_pin(n.id)
    assert not n3.pinned


def test_toggle_done():
    n = svc.create_note(title="x", body="", category="todo")
    assert not n.done
    n2 = svc.toggle_done(n.id)
    assert n2.done
    n3 = svc.toggle_done(n.id)
    assert not n3.done


def test_list_notes_hide_done():
    a = svc.create_note(title="A", body="", category="idea")
    b = svc.create_note(title="B", body="", category="idea")
    svc.toggle_done(b.id)
    active = svc.list_notes(include_done=False)
    assert all(n.id != b.id for n in active)
    assert any(n.id == a.id for n in active)


def test_add_link():
    n = svc.create_note(title="x", body="", category="idea")
    svc.add_link(n.id, "chapter", "ch-1", "Chapter 1")
    updated = svc.get_note(n.id)
    from services._common import load_json
    links = load_json(updated.links, [])
    assert len(links) == 1
    assert links[0]["entity_id"] == "ch-1"


def test_add_link_dedupes():
    n = svc.create_note(title="x", body="", category="idea")
    svc.add_link(n.id, "chapter", "ch-1", "Chapter 1")
    svc.add_link(n.id, "chapter", "ch-1", "Chapter 1")  # duplicate
    updated = svc.get_note(n.id)
    from services._common import load_json
    links = load_json(updated.links, [])
    assert len(links) == 1


def test_add_link_invalid_entity_type():
    n = svc.create_note(title="x", body="", category="idea")
    from core.errors import ValidationError
    with pytest.raises(ValidationError):
        svc.add_link(n.id, "bogus", "1", "x")


def test_remove_link():
    n = svc.create_note(title="x", body="", category="idea")
    svc.add_link(n.id, "chapter", "ch-1", "Chapter 1")
    svc.add_link(n.id, "character", "c-1", "Hero")
    svc.remove_link(n.id, "ch-1")
    updated = svc.get_note(n.id)
    from services._common import load_json
    links = load_json(updated.links, [])
    assert len(links) == 1
    assert links[0]["entity_id"] == "c-1"


def test_delete_note():
    n = svc.create_note(title="x", body="", category="idea")
    svc.delete_note(n.id)
    from core.errors import NotFoundError
    with pytest.raises(NotFoundError):
        svc.get_note(n.id)


def test_all_tags():
    svc.create_note(title="A", body="", category="idea", tags=["alpha", "beta"])
    svc.create_note(title="B", body="", category="idea", tags=["beta", "gamma"])
    tags = svc.all_tags()
    assert tags == ["alpha", "beta", "gamma"]


def test_to_dict_shape():
    n = svc.create_note(
        title="T", body="B", category="todo",
        tags=["x"], pinned=True,
    )
    d = svc.to_dict(n)
    assert d["title"] == "T"
    assert d["body"] == "B"
    assert d["category"] == "todo"
    assert d["category_label"] == "Todo"
    assert d["icon"] == "✓"
    assert d["tags"] == ["x"]
    assert d["pinned"] is True
    assert d["done"] is False
    assert d["created_at"]


def test_promote_to_snippet():
    n = svc.create_note(title="Snip me", body="Body text", category="idea")
    sid = svc.promote_to_snippet(n.id)
    assert sid
    # Note should be marked done
    updated = svc.get_note(n.id)
    assert updated.done


def test_promote_to_plan():
    n = svc.create_note(title="Plan me", body="Plan body", category="idea")
    pid = svc.promote_to_plan(n.id)
    assert pid
    updated = svc.get_note(n.id)
    assert updated.done
    # Plan should exist
    from services.plan_service import get_plan
    p = get_plan(pid)
    assert "Plan me" in p.title


def test_promote_to_chapter():
    n = svc.create_note(title="Chapter me", body="Chapter body", category="scene_idea")
    ch_id = svc.promote_to_chapter(n.id)
    assert ch_id
    updated = svc.get_note(n.id)
    assert updated.done
    # Chapter should exist with the note body in its content
    from services.chapter_service import get_chapter
    ch = get_chapter(ch_id)
    assert "Chapter body" in ch.content


def test_get_note_not_found():
    from core.errors import NotFoundError
    with pytest.raises(NotFoundError):
        svc.get_note("nonexistent-id")


def test_update_note_not_found():
    from core.errors import NotFoundError
    with pytest.raises(NotFoundError):
        svc.update_note("nonexistent-id", title="x")
