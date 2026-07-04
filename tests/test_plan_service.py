"""Tests for plan_service: CRUD, status, reorder, subtasks."""
import pytest

from services import plan_service
from core.errors import NotFoundError, ValidationError


def test_create_plan_basic():
    p = plan_service.create_plan(title="Test Plan")
    assert p.id
    assert p.title == "Test Plan"
    assert p.status == "idea"
    assert p.column == "idea"


def test_create_plan_validates_title():
    with pytest.raises(ValidationError):
        plan_service.create_plan(title="")
    with pytest.raises(ValidationError):
        plan_service.create_plan(title="x" * 600)


def test_create_plan_invalid_status():
    with pytest.raises(ValidationError):
        plan_service.create_plan(title="X", status="invalid")


def test_change_status():
    p = plan_service.create_plan(title="Status Test")
    plan_service.change_status(p.id, "writing")
    refreshed = plan_service.get_plan(p.id)
    assert refreshed.status == "writing"
    assert refreshed.column == "writing"


def test_change_status_invalid():
    p = plan_service.create_plan(title="X")
    with pytest.raises(ValidationError):
        plan_service.change_status(p.id, "not_a_status")


def test_reorder_all_kanban():
    a = plan_service.create_plan(title="A", status="idea")
    b = plan_service.create_plan(title="B", status="idea")
    plan_service.reorder_all({"idea": [b.id, a.id], "planned": []})
    assert plan_service.get_plan(b.id).sort_order == 1
    assert plan_service.get_plan(a.id).sort_order == 2


def test_reorder_nested():
    a = plan_service.create_plan(title="Parent", status="idea")
    b = plan_service.create_plan(title="Child", status="idea")
    plan_service.reorder_nested([
        {"id": a.id, "parent_id": None, "sort_order": 1},
        {"id": b.id, "parent_id": a.id, "sort_order": 1},
    ])
    assert plan_service.get_plan(b.id).parent_id == a.id
    assert plan_service.get_plan(a.id).parent_id is None


def test_subtasks_crud():
    p = plan_service.create_plan(title="With Subtasks")
    st = plan_service.add_subtask(p.id, "Subtask 1")
    st2 = plan_service.add_subtask(p.id, "Subtask 2")
    subs = plan_service.list_subtasks(p.id)
    assert len(subs) == 2
    plan_service.update_subtask(st.id, is_completed=True)
    subs = plan_service.list_subtasks(p.id)
    assert any(s.is_completed for s in subs)
    plan_service.delete_subtask(st.id)
    plan_service.delete_subtask(st2.id)
    assert len(plan_service.list_subtasks(p.id)) == 0


def test_subtask_counts_for_plans():
    p1 = plan_service.create_plan(title="P1")
    p2 = plan_service.create_plan(title="P2")
    s1 = plan_service.add_subtask(p1.id, "S1")
    s2 = plan_service.add_subtask(p1.id, "S2")
    s3 = plan_service.add_subtask(p2.id, "S3")
    plan_service.update_subtask(s1.id, is_completed=True)
    counts = plan_service.subtask_counts_for_plans([p1.id, p2.id])
    assert counts[p1.id] == (1, 2)
    assert counts[p2.id] == (0, 1)


def test_subtask_counts_empty():
    assert plan_service.subtask_counts_for_plans([]) == {}


def test_delete_plan_detaches_children():
    parent = plan_service.create_plan(title="Parent")
    child = plan_service.create_plan(title="Child")
    plan_service.reorder_nested([
        {"id": child.id, "parent_id": parent.id, "sort_order": 1},
    ])
    plan_service.delete_plan(parent.id)
    # Child should still exist with parent_id cleared
    refreshed = plan_service.get_plan(child.id)
    assert refreshed.parent_id is None
