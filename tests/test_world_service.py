"""Tests for world_service: CRUD, versions, map pins, relations."""
import pytest

from services import world_service
from core.errors import NotFoundError, ValidationError


def test_create_entry_basic():
    e = world_service.create_entry(type_="location", name="Test City")
    assert e.id
    assert e.type == "location"
    assert e.name == "Test City"
    assert e.sort_order == 1


def test_create_entry_validates_name():
    with pytest.raises(ValidationError):
        world_service.create_entry(type_="location", name="")
    with pytest.raises(ValidationError):
        world_service.create_entry(type_="location", name="x" * 400)


def test_update_entry_creates_version():
    e = world_service.create_entry(type_="lore", name="Original", content="Original content.")
    initial = len(world_service.list_versions(e.id))
    world_service.update_entry(e.id, content="Updated content.")
    after = len(world_service.list_versions(e.id))
    assert after == initial + 1


def test_update_pin_set_and_remove():
    e = world_service.create_entry(type_="location", name="Mapped")
    # Set pin
    world_service.update_pin(e.id, 45.5, 30.2, label="Capital")
    refreshed = world_service.get_entry(e.id)
    assert refreshed.map_pin_x == 45.5
    assert refreshed.map_pin_y == 30.2
    assert refreshed.map_pin_label == "Capital"
    # Remove pin (null coords)
    world_service.update_pin(e.id, None, None)
    refreshed = world_service.get_entry(e.id)
    assert refreshed.map_pin_x is None
    assert refreshed.map_pin_y is None


def test_update_pin_invalid_coords():
    e = world_service.create_entry(type_="location", name="Bad Pin")
    with pytest.raises(ValidationError):
        world_service.update_pin(e.id, "not-a-number", 30)


def test_duplicate_entry():
    e = world_service.create_entry(type_="location", name="To Clone", content="Content.")
    dup = world_service.duplicate_entry(e.id)
    assert dup.id != e.id
    assert "copy" in dup.name
    assert dup.content == e.content


def test_relations():
    a = world_service.create_entry(type_="location", name="A")
    b = world_service.create_entry(type_="location", name="B")
    rel = world_service.create_relation(from_id=a.id, to_id=b.id, rel_type="located_in")
    out, inc = world_service.relations_for(a.id)
    assert any(r.id == rel.id for r in out)
    out_b, inc_b = world_service.relations_for(b.id)
    assert any(r.id == rel.id for r in inc_b)
    world_service.delete_relation(rel.id)
    out, _ = world_service.relations_for(a.id)
    assert not any(r.id == rel.id for r in out)


def test_relation_self_loop_rejected():
    a = world_service.create_entry(type_="location", name="Self")
    with pytest.raises(ValidationError):
        world_service.create_relation(from_id=a.id, to_id=a.id, rel_type="part_of")


def test_restore_version():
    e = world_service.create_entry(type_="location", name="V1", content="Original.")
    world_service.update_entry(e.id, name="V2", content="Updated.")
    versions = world_service.list_versions(e.id)
    # Restore the first (V1)
    first_v = versions[-1]
    restored = world_service.restore_version(e.id, first_v.id)
    assert restored.name == "V1"
    assert "Original" in restored.content


def test_delete_entry_cascades():
    e = world_service.create_entry(type_="location", name="Doomed")
    other = world_service.create_entry(type_="location", name="Other")
    rel = world_service.create_relation(from_id=e.id, to_id=other.id, rel_type="allied_with")
    world_service.delete_entry(e.id)
    with pytest.raises(NotFoundError):
        world_service.get_entry(e.id)
    # Relation should be gone
    out, _ = world_service.relations_for(other.id)
    assert not any(r.id == rel.id for r in out)
