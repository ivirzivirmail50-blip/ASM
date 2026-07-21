"""Character service: CRUD, groups, relationships, arcs."""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.db import read_session, write_transaction
from core.errors import NotFoundError, ValidationError
from models.character import (
    Character, CharacterArc, CharacterGroup, CharacterGroupMember,
    CharacterRelationship,
)
from security import limits
from services._common import (
    current_project_id, dump_json, load_json, log_activity, new_uuid, now_utc,
)

log = logging.getLogger("asm.character")

ROLE_OPTIONS = ("protagonist", "antagonist", "supporting", "minor")
RELATIONSHIP_TYPES = (
    "married_to", "rival_of", "parent_of", "friend_of", "enemy_of",
    "serves", "mentors", "loves", "betrayed_by", "custom",
)


def color_for_name(name: str) -> str:
    """Deterministic hex color from name hash."""
    h = hashlib.md5(name.encode("utf-8")).hexdigest()
    return f"#{h[0:2]}{h[2:4]}{h[4:6]}"


def list_characters(
    *, role: str | None = None, search: str | None = None,
    sort: str = "name",
) -> list[Character]:
    with read_session() as s:
        q = select(Character).where(
            Character.project_id == current_project_id(s)
        )
        if role and role != "all":
            q = q.where(Character.role == role)
        if search:
            like = f"%{search}%"
            q = q.where(
                (Character.name.ilike(like)) | (Character.notes.ilike(like))
            )
        sort_col = {
            "name": Character.name,
            "created_at": Character.created_at,
        }.get(sort, Character.name)
        q = q.order_by(sort_col.asc())
        return list(s.scalars(q).all())


def get_character(character_id: str) -> Character:
    with read_session() as s:
        ch = s.get(Character, character_id)
        if not ch:
            raise NotFoundError("Character not found.")
        return ch


def create_character(
    *, name: str, role: str = "supporting", age: str | None = None,
    gender: str | None = None, aliases: list[str] | None = None,
    avatar_color: str | None = None, physical: str | None = None,
    psychology: str | None = None, background: str | None = None,
    philosophy: str | None = None, philosophy_quotes: list[str] | None = None,
    story_role: str | None = None, story_role_chapters: list[str] | None = None,
    voice: str | None = None, notes: str | None = None,
) -> Character:
    if not name or len(name) > limits.NAME_MAX:
        raise ValidationError(f"Name required, ≤ {limits.NAME_MAX} chars.")
    if role not in ROLE_OPTIONS:
        raise ValidationError(f"Role must be one of {ROLE_OPTIONS}.")
    cid = new_uuid()
    color = avatar_color or color_for_name(name)
    with write_transaction() as s:
        ch = Character(
            id=cid,
            project_id=current_project_id(s),
            name=name,
            role=role,
            age=age,
            gender=gender,
            aliases=dump_json(aliases or []),
            avatar_color=color,
            physical=physical,
            psychology=psychology,
            background=background,
            philosophy=philosophy,
            philosophy_quotes=dump_json(philosophy_quotes or []),
            story_role=story_role,
            story_role_chapters=dump_json(story_role_chapters or []),
            voice=voice,
            notes=notes,
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        s.add(ch)
        log_activity(
            s, entity_type="character", entity_id=cid, entity_title=name,
            action="created",
        )
        s.flush()
        return ch


def update_character(character_id: str, **fields: Any) -> Character:
    with write_transaction() as s:
        ch = s.get(Character, character_id)
        if not ch:
            raise NotFoundError("Character not found.")
        for k in ("name", "role", "age", "gender", "physical", "psychology",
                  "background", "philosophy", "story_role", "voice", "notes",
                  "avatar_color", "avatar_path", "graph_x", "graph_y"):
            if k in fields and fields[k] is not None:
                if k == "name" and (not fields[k] or len(fields[k]) > limits.NAME_MAX):
                    raise ValidationError("Name required, ≤ 200 chars.")
                setattr(ch, k, fields[k])
        for k in ("aliases", "philosophy_quotes", "story_role_chapters"):
            if k in fields:
                setattr(ch, k, dump_json(fields[k] or []))
        ch.updated_at = now_utc()
        log_activity(
            s, entity_type="character", entity_id=character_id,
            entity_title=ch.name, action="updated",
        )
        s.flush()
        return ch


def delete_character(character_id: str) -> str:
    """Delete a character. Records undo snapshot. Returns label."""
    from models.undo import snapshot_character, record_delete
    ch = get_character(character_id)
    snapshot = snapshot_character(ch)
    label = f"Delete character '{ch.name}'"
    record_delete("character", character_id, label, snapshot)
    with write_transaction() as s:
        ch = s.get(Character, character_id)
        if not ch:
            raise NotFoundError("Character not found.")
        name = ch.name
        s.query(CharacterGroupMember).filter_by(character_id=character_id).delete()
        s.query(CharacterRelationship).filter(
            (CharacterRelationship.from_character_id == character_id)
            | (CharacterRelationship.to_character_id == character_id)
        ).delete()
        s.query(CharacterArc).filter_by(character_id=character_id).delete()
        s.delete(ch)
        log_activity(
            s, entity_type="character", entity_id=character_id,
            entity_title=name, action="deleted",
        )
    return label


# ---- Groups ----

def list_groups() -> list[CharacterGroup]:
    with read_session() as s:
        return list(s.scalars(
            select(CharacterGroup).where(
                CharacterGroup.project_id == current_project_id(s)
            ).order_by(CharacterGroup.name.asc())
        ).all())


def create_group(name: str, *, description: str | None = None,
                 color: str = "#6366f1") -> CharacterGroup:
    if not name or len(name) > limits.NAME_MAX:
        raise ValidationError("Group name required.")
    gid = new_uuid()
    with write_transaction() as s:
        g = CharacterGroup(
            id=gid, project_id=current_project_id(s),
            name=name, description=description, color=color,
        )
        s.add(g)
        s.flush()
        return g


def assign_to_group(character_id: str, group_id: str) -> None:
    with write_transaction() as s:
        if not s.get(Character, character_id):
            raise NotFoundError("Character not found.")
        if not s.get(CharacterGroup, group_id):
            raise NotFoundError("Group not found.")
        existing = s.scalar(
            select(CharacterGroupMember).where(
                CharacterGroupMember.character_id == character_id,
                CharacterGroupMember.group_id == group_id,
            )
        )
        if not existing:
            s.add(CharacterGroupMember(
                id=new_uuid(),
                character_id=character_id, group_id=group_id,
            ))


def remove_from_group(character_id: str, group_id: str) -> None:
    with write_transaction() as s:
        s.query(CharacterGroupMember).filter_by(
            character_id=character_id, group_id=group_id,
        ).delete()


def groups_for_character(character_id: str) -> list[CharacterGroup]:
    with read_session() as s:
        rows = s.scalars(
            select(CharacterGroup)
            .join(CharacterGroupMember,
                  CharacterGroupMember.group_id == CharacterGroup.id)
            .where(CharacterGroupMember.character_id == character_id)
        ).all()
        return list(rows)


def characters_in_group(group_id: str) -> list[Character]:
    with read_session() as s:
        rows = s.scalars(
            select(Character)
            .join(CharacterGroupMember,
                  CharacterGroupMember.character_id == Character.id)
            .where(CharacterGroupMember.group_id == group_id)
            .order_by(Character.name.asc())
        ).all()
        return list(rows)


# ---- Relationships ----

def list_relationships() -> list[CharacterRelationship]:
    with read_session() as s:
        return list(s.scalars(
            select(CharacterRelationship).order_by(
                CharacterRelationship.created_at.desc()
            )
        ).all())


def relationships_for(character_id: str) -> list[CharacterRelationship]:
    with read_session() as s:
        return list(s.scalars(
            select(CharacterRelationship).where(
                (CharacterRelationship.from_character_id == character_id)
                | (CharacterRelationship.to_character_id == character_id)
            ).order_by(CharacterRelationship.created_at.desc())
        ).all())


def create_relationship(
    *, from_id: str, to_id: str, rel_type: str,
    description: str | None = None, bidirectional: bool = False,
) -> CharacterRelationship:
    if rel_type not in RELATIONSHIP_TYPES:
        raise ValidationError(f"Type must be one of {RELATIONSHIP_TYPES}.")
    if from_id == to_id:
        raise ValidationError("Cannot relate a character to themselves.")
    rid = new_uuid()
    with write_transaction() as s:
        # Validate from_id: either a character or a group (g-<group_id>)
        from_is_group = from_id.startswith("g-")
        to_is_group = to_id.startswith("g-")
        if from_is_group:
            from_group = s.get(CharacterGroup, from_id[2:])
            if not from_group:
                raise NotFoundError("Group not found.")
        else:
            if not s.get(Character, from_id):
                raise NotFoundError("Character not found.")
        if to_is_group:
            to_group = s.get(CharacterGroup, to_id[2:])
            if not to_group:
                raise NotFoundError("Group not found.")
        else:
            if not s.get(Character, to_id):
                raise NotFoundError("Character not found.")
        rel = CharacterRelationship(
            id=rid, from_character_id=from_id, to_character_id=to_id,
            relationship_type=rel_type, description=description,
            is_bidirectional=bidirectional if rel_type != "married_to" else True,
            created_at=now_utc(),
        )
        s.add(rel)
        s.flush()
        return rel


def delete_relationship(relationship_id: str) -> None:
    with write_transaction() as s:
        rel = s.get(CharacterRelationship, relationship_id)
        if not rel:
            raise NotFoundError("Relationship not found.")
        s.delete(rel)


def update_graph_position(character_id: str, x: int, y: int) -> None:
    """Persist node position after drag on the relationship graph."""
    with write_transaction() as s:
        ch = s.get(Character, character_id)
        if not ch:
            raise NotFoundError("Character not found.")
        ch.graph_x = int(x)
        ch.graph_y = int(y)


# ---- Arcs ----

def list_arcs(character_id: str) -> list[CharacterArc]:
    with read_session() as s:
        return list(s.scalars(
            select(CharacterArc).where(CharacterArc.character_id == character_id)
            .order_by(CharacterArc.created_at.desc())
        ).all())


def create_arc(character_id: str, arc_name: str,
               description: str | None = None,
               stages: list[dict] | None = None) -> CharacterArc:
    if not arc_name:
        raise ValidationError("Arc name required.")
    aid = new_uuid()
    with write_transaction() as s:
        if not s.get(Character, character_id):
            raise NotFoundError("Character not found.")
        arc = CharacterArc(
            id=aid, character_id=character_id, arc_name=arc_name,
            description=description,
            stages=dump_json(stages or []),
            created_at=now_utc(),
        )
        s.add(arc)
        s.flush()
        return arc


def update_arc(arc_id: str, **fields: Any) -> CharacterArc:
    with write_transaction() as s:
        arc = s.get(CharacterArc, arc_id)
        if not arc:
            raise NotFoundError("Arc not found.")
        if "arc_name" in fields:
            arc.arc_name = fields["arc_name"]
        if "description" in fields:
            arc.description = fields["description"]
        if "stages" in fields:
            arc.stages = dump_json(fields["stages"] or [])
        s.flush()
        return arc


def delete_arc(arc_id: str) -> None:
    with write_transaction() as s:
        arc = s.get(CharacterArc, arc_id)
        if not arc:
            raise NotFoundError("Arc not found.")
        s.delete(arc)
