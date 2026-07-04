"""Tests for character_service: CRUD, groups, relationships, arcs."""
import pytest

from services import character_service
from core.errors import NotFoundError, ValidationError


def test_create_character_basic():
    ch = character_service.create_character(name="Elara", role="protagonist")
    assert ch.id
    assert ch.name == "Elara"
    assert ch.role == "protagonist"
    assert ch.avatar_color  # auto-generated


def test_create_character_validates_name():
    with pytest.raises(ValidationError):
        character_service.create_character(name="")
    with pytest.raises(ValidationError):
        character_service.create_character(name="x" * 250)


def test_create_character_invalid_role():
    with pytest.raises(ValidationError):
        character_service.create_character(name="Test", role="invalid_role")


def test_color_for_name_deterministic():
    c1 = character_service.color_for_name("Elara")
    c2 = character_service.color_for_name("Elara")
    c3 = character_service.color_for_name("Different")
    assert c1 == c2
    assert c1 != c3
    assert c1.startswith("#")


def test_groups_assign_and_remove():
    ch = character_service.create_character(name="Grouped", role="supporting")
    g = character_service.create_group("Test Group", color="#abcdef")
    character_service.assign_to_group(ch.id, g.id)
    groups = character_service.groups_for_character(ch.id)
    assert any(gr.id == g.id for gr in groups)
    members = character_service.characters_in_group(g.id)
    assert any(m.id == ch.id for m in members)
    character_service.remove_from_group(ch.id, g.id)
    groups = character_service.groups_for_character(ch.id)
    assert not any(gr.id == g.id for gr in groups)


def test_relationships_create_and_delete():
    a = character_service.create_character(name="A", role="protagonist")
    b = character_service.create_character(name="B", role="antagonist")
    rel = character_service.create_relationship(
        from_id=a.id, to_id=b.id, rel_type="rival_of", bidirectional=True,
    )
    assert rel.is_bidirectional  # rival_of should support bidirectional
    rels = character_service.relationships_for(a.id)
    assert any(r.id == rel.id for r in rels)
    character_service.delete_relationship(rel.id)
    rels = character_service.relationships_for(a.id)
    assert not any(r.id == rel.id for r in rels)


def test_relationship_self_loop_rejected():
    a = character_service.create_character(name="Solo", role="minor")
    with pytest.raises(ValidationError):
        character_service.create_relationship(
            from_id=a.id, to_id=a.id, rel_type="friend_of",
        )


def test_married_to_is_bidirectional():
    a = character_service.create_character(name="A", role="protagonist")
    b = character_service.create_character(name="B", role="protagonist")
    rel = character_service.create_relationship(
        from_id=a.id, to_id=b.id, rel_type="married_to",
    )
    assert rel.is_bidirectional is True


def test_graph_position_persists():
    ch = character_service.create_character(name="Draggable", role="minor")
    character_service.update_graph_position(ch.id, 250, -100)
    refreshed = character_service.get_character(ch.id)
    assert refreshed.graph_x == 250
    assert refreshed.graph_y == -100


def test_arcs_crud():
    ch = character_service.create_character(name="Arc Hero", role="protagonist")
    arc = character_service.create_arc(
        ch.id, "Redemption Arc",
        description="A journey from villain to hero.",
        stages=[
            {"name": "Setup", "status": "completed"},
            {"name": "Climax", "status": "planned"},
        ],
    )
    arcs = character_service.list_arcs(ch.id)
    assert any(a.id == arc.id for a in arcs)
    character_service.update_arc(arc.id, arc_name="Updated Arc")
    character_service.delete_arc(arc.id)
    arcs = character_service.list_arcs(ch.id)
    assert not any(a.id == arc.id for a in arcs)


def test_delete_character_cascades():
    ch = character_service.create_character(name="Doomed", role="minor")
    g = character_service.create_group("Doomed Group")
    character_service.assign_to_group(ch.id, g.id)
    other = character_service.create_character(name="Other", role="minor")
    rel = character_service.create_relationship(
        from_id=ch.id, to_id=other.id, rel_type="friend_of",
    )
    arc = character_service.create_arc(ch.id, "Arc")
    character_service.delete_character(ch.id)
    # All related rows should be gone
    assert not character_service.groups_for_character(ch.id)
    assert not character_service.relationships_for(ch.id)
    assert not character_service.list_arcs(ch.id)
    with pytest.raises(NotFoundError):
        character_service.get_character(ch.id)
