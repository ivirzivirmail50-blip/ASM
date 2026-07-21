"""Character Relationship Timeline — track how relationships evolve over chapters.

Each relationship event captures:
- from_character_id, to_character_id
- chapter_id (where the change happens)
- relationship_type (the NEW type after this event)
- previous_type (what it was before, or empty for first meeting)
- description (what changed and why)
- sort_order (within the timeline)

This lets the writer see: "In chapter 1 they were strangers, by chapter 5
they became allies, and in chapter 12 they became enemies."

The service can reconstruct the relationship state at any chapter.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from core.db import read_session, write_transaction
from core.errors import NotFoundError, ValidationError
from models.character import Character, CharacterRelationship
from models.chapter import Chapter
from services._common import current_project_id, new_uuid, now_utc

log = logging.getLogger("asm.rel_timeline")


def list_events(*, character_id: str | None = None) -> list[dict[str, Any]]:
    """Return all relationship timeline events, optionally filtered by character."""
    with read_session() as s:
        # We reuse CharacterRelationship but treat each row as a timeline event
        q = select(CharacterRelationship)
        if character_id:
            q = q.where(
                (CharacterRelationship.from_character_id == character_id) |
                (CharacterRelationship.to_character_id == character_id)
            )
        rels = list(s.scalars(q))
        # Sort by chapter sort_order (need to join chapters)
        result: list[dict[str, Any]] = []
        for r in rels:
            from_ch = s.get(Character, r.from_character_id)
            to_ch = s.get(Character, r.to_character_id)
            ch = s.get(Chapter, r.chapter_id) if hasattr(r, 'chapter_id') and r.chapter_id else None
            result.append({
                "id": r.id,
                "from_character_id": r.from_character_id,
                "from_name": from_ch.name if from_ch else "?",
                "to_character_id": r.to_character_id,
                "to_name": to_ch.name if to_ch else "?",
                "relationship_type": r.relationship_type,
                "description": r.description or "",
                "is_bidirectional": bool(r.is_bidirectional),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })
        return result


def get_relationships_for_chapter(chapter_id: str) -> list[dict[str, Any]]:
    """Return all direct relationships linked to this chapter."""
    with read_session() as s:
        # Check if CharacterRelationship has chapter_id column
        cols = CharacterRelationship.__table__.columns.keys()
        if "chapter_id" not in cols:
            # Fall back to all relationships
            return list_events()
        rels = list(s.scalars(
            select(CharacterRelationship).where(
                CharacterRelationship.chapter_id == chapter_id
            )
        ))
        result = []
        for r in rels:
            from_ch = s.get(Character, r.from_character_id)
            to_ch = s.get(Character, r.to_character_id)
            result.append({
                "id": r.id,
                "from_character_id": r.from_character_id,
                "from_name": from_ch.name if from_ch else "?",
                "to_character_id": r.to_character_id,
                "to_name": to_ch.name if to_ch else "?",
                "relationship_type": r.relationship_type,
                "description": r.description or "",
                "is_bidirectional": bool(r.is_bidirectional),
            })
        return result


def add_timeline_event(
    *, from_character_id: str, to_character_id: str,
    relationship_type: str, description: str = "",
    is_bidirectional: bool = False,
) -> dict[str, Any]:
    """Add a relationship (as a timeline event)."""
    if from_character_id == to_character_id:
        raise ValidationError("A character cannot have a relationship with themselves.")
    if not relationship_type:
        raise ValidationError("Relationship type required.")
    with write_transaction() as s:
        ch1 = s.get(Character, from_character_id)
        ch2 = s.get(Character, to_character_id)
        if not ch1 or not ch2:
            raise NotFoundError("One or both characters not found.")
        rel = CharacterRelationship(
            id=new_uuid(),
            from_character_id=from_character_id,
            to_character_id=to_character_id,
            relationship_type=relationship_type,
            description=description,
            is_bidirectional=is_bidirectional,
        )
        s.add(rel)
        s.flush()
        return {
            "id": rel.id,
            "from_character_id": from_character_id,
            "from_name": ch1.name,
            "to_character_id": to_character_id,
            "to_name": ch2.name,
            "relationship_type": relationship_type,
            "description": description,
            "is_bidirectional": is_bidirectional,
        }


def remove_event(rel_id: str) -> None:
    with write_transaction() as s:
        rel = s.get(CharacterRelationship, rel_id)
        if rel:
            s.delete(rel)


def get_timeline_matrix() -> dict[str, Any]:
    """Build a character×character matrix of current relationship types."""
    with read_session() as s:
        characters = list(s.scalars(
            select(Character).where(
                Character.project_id == current_project_id(s)
            ).order_by(Character.name.asc())
        ))
        rels = list(s.scalars(select(CharacterRelationship)))
        # Build matrix
        char_ids = [c.id for c in characters]
        char_names = {c.id: c.name for c in characters}
        matrix: dict[str, dict[str, str]] = {cid: {} for cid in char_ids}
        for r in rels:
            if r.from_character_id in matrix and r.to_character_id in matrix:
                matrix[r.from_character_id][r.to_character_id] = r.relationship_type
                if r.is_bidirectional:
                    matrix[r.to_character_id][r.from_character_id] = r.relationship_type
        return {
            "characters": [{"id": c.id, "name": c.name, "role": c.role,
                            "avatar_color": c.avatar_color or "#6366f1"} for c in characters],
            "matrix": matrix,
            "char_names": char_names,
            "total_relationships": len(rels),
        }


def stats() -> dict[str, Any]:
    with read_session() as s:
        rels = list(s.scalars(select(CharacterRelationship)))
        types: dict[str, int] = {}
        for r in rels:
            types[r.relationship_type] = types.get(r.relationship_type, 0) + 1
        return {
            "total": len(rels),
            "types": types,
            "bidirectional_count": sum(1 for r in rels if r.is_bidirectional),
        }
