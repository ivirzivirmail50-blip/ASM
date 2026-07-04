"""Tests for undo system: persistent DB-backed undo for deletes."""
import pytest

from services import chapter_service, character_service, plan_service, world_service
from models.undo import UndoOperation, undo_last, list_recent, record_delete, snapshot_chapter


def test_undo_operation_table_exists(app):
    """Verify the undo_operations table is created."""
    from core.db import read_session
    with read_session() as s:
        # Should not raise
        count = s.query(UndoOperation).count()
        assert count == 0


def test_delete_chapter_records_undo():
    ch = chapter_service.create_chapter(title="Undo Me", content="content")
    label = chapter_service.delete_chapter(ch.id)
    assert "Delete chapter" in label
    ops = list_recent(limit=10)
    assert len(ops) >= 1
    assert ops[0].entity_type == "chapter"
    assert ops[0].entity_id == ch.id


def test_undo_restores_chapter():
    ch = chapter_service.create_chapter(title="Restore Me", content="content here")
    ch_id = ch.id
    chapter_service.delete_chapter(ch_id)
    # Chapter should be gone
    from core.errors import NotFoundError
    with pytest.raises(NotFoundError):
        chapter_service.get_chapter(ch_id)
    # Undo
    result = undo_last()
    assert result is not None
    assert result["ok"] is True
    # Chapter should be back
    restored = chapter_service.get_chapter(ch_id)
    assert restored.title == "Restore Me"


def test_undo_restores_character_with_relationships():
    a = character_service.create_character(name="A", role="minor")
    b = character_service.create_character(name="B", role="minor")
    rel = character_service.create_relationship(
        from_id=a.id, to_id=b.id, rel_type="friend_of", bidirectional=True)
    a_id = a.id
    rel_id = rel.id
    character_service.delete_character(a_id)
    # Undo
    result = undo_last()
    assert result["ok"] is True
    # Character should be back
    restored = character_service.get_character(a_id)
    assert restored.name == "A"
    # Relationship should be back too
    rels = character_service.relationships_for(a_id)
    assert any(r.id == rel_id for r in rels)


def test_undo_restores_plan_with_subtasks():
    p = plan_service.create_plan(title="Undo Plan")
    st = plan_service.add_subtask(p.id, "Subtask 1")
    p_id = p.id
    st_id = st.id
    plan_service.delete_plan(p_id)
    # Undo
    result = undo_last()
    assert result["ok"] is True
    # Plan + subtask should be back
    restored = plan_service.get_plan(p_id)
    assert restored.title == "Undo Plan"
    subs = plan_service.list_subtasks(p_id)
    assert any(s.id == st_id for s in subs)


def test_undo_restores_world_entry():
    e = world_service.create_entry(type_="location", name="Undo Place", content="content")
    e_id = e.id
    world_service.delete_entry(e_id)
    result = undo_last()
    assert result["ok"] is True
    restored = world_service.get_entry(e_id)
    assert restored.name == "Undo Place"


def test_undo_returns_none_when_empty():
    result = undo_last()
    assert result is None


def test_undo_stack_cap():
    """Undo stack is capped at MAX_UNDO (100)."""
    from models.undo import MAX_UNDO
    # Create + delete MAX_UNDO + 5 chapters
    for i in range(MAX_UNDO + 5):
        ch = chapter_service.create_chapter(title=f"Cap {i}", content="x")
        chapter_service.delete_chapter(ch.id)
    ops = list_recent(limit=200)
    assert len(ops) <= MAX_UNDO


def test_snapshot_chapter_captures_versions():
    ch = chapter_service.create_chapter(title="Snap", content="v1")
    chapter_service.update_chapter(ch.id, content="v2", create_version=True,
                                    version_source="manual")
    snapshot = snapshot_chapter(ch)
    assert "chapter" in snapshot
    assert "versions" in snapshot
    assert len(snapshot["versions"]) >= 2
