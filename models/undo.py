"""Undo/redo operations — persistent in DB (command pattern).

Each operation records enough to reverse itself. The undo stack is capped
at 100 entries (per PROMPT spec). Delete operations have a 10-second
window where a toast offers "Undo?".

Snapshots store enough entity data to recreate the row on undo. For
multi-row operations (e.g., chapter + version rows), the snapshot is a
JSON dict containing all affected rows.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import Column, DateTime, Integer, String, Text

from models import Base

log = logging.getLogger("asm.undo")

MAX_UNDO = 100


class UndoOperation(Base):
    __tablename__ = "undo_operations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    operation = Column(String(80))  # delete_chapter / delete_character / delete_plan / delete_world_entry / reorder
    label = Column(String(200))     # human-readable label, e.g. "Delete chapter 'Chapter 1'"
    entity_type = Column(String(50))
    entity_id = Column(String(64))
    snapshot = Column(Text)         # JSON of the entity + related rows
    undo_action = Column(String(80))  # restore / reverse_reorder / etc.
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def snapshot_chapter(ch) -> dict:
    """Capture a chapter + its versions for undo."""
    from core.db import read_session
    from models.chapter import ChapterVersion
    from services._common import load_json
    out = {
        "chapter": {
            "id": ch.id, "project_id": ch.project_id, "title": ch.title,
            "content": ch.content, "synopsis": ch.synopsis, "status": ch.status,
            "word_count": ch.word_count, "target_word_count": ch.target_word_count,
            "sort_order": ch.sort_order, "character_ids": ch.character_ids,
            "tags": ch.tags, "raw_file_path": ch.raw_file_path,
            "created_at": ch.created_at.isoformat() if ch.created_at else None,
            "updated_at": ch.updated_at.isoformat() if ch.updated_at else None,
        },
        "versions": [],
    }
    with read_session() as s:
        rows = s.query(ChapterVersion).filter_by(chapter_id=ch.id).all()
        for v in rows:
            out["versions"].append({
                "id": v.id, "chapter_id": v.chapter_id,
                "version_number": v.version_number, "content": v.content,
                "word_count": v.word_count, "source": v.source,
                "uploaded_at": v.uploaded_at.isoformat() if v.uploaded_at else None,
                "notes": v.notes,
            })
    return out


def snapshot_character(ch) -> dict:
    """Capture a character + groups + relationships + arcs for undo."""
    from core.db import read_session
    from models.character import (CharacterGroupMember, CharacterRelationship,
                                   CharacterArc)
    out = {
        "character": {
            "id": ch.id, "project_id": ch.project_id, "name": ch.name,
            "age": ch.age, "gender": ch.gender, "aliases": ch.aliases,
            "role": ch.role, "avatar_color": ch.avatar_color,
            "avatar_path": ch.avatar_path, "physical": ch.physical,
            "psychology": ch.psychology, "background": ch.background,
            "philosophy": ch.philosophy, "philosophy_quotes": ch.philosophy_quotes,
            "story_role": ch.story_role, "story_role_chapters": ch.story_role_chapters,
            "voice": ch.voice, "notes": ch.notes,
            "graph_x": ch.graph_x, "graph_y": ch.graph_y,
            "created_at": ch.created_at.isoformat() if ch.created_at else None,
            "updated_at": ch.updated_at.isoformat() if ch.updated_at else None,
        },
        "group_memberships": [],
        "relationships": [],
        "arcs": [],
    }
    with read_session() as s:
        for gm in s.query(CharacterGroupMember).filter_by(character_id=ch.id).all():
            out["group_memberships"].append({"id": gm.id, "group_id": gm.group_id})
        for r in s.query(CharacterRelationship).filter(
            (CharacterRelationship.from_character_id == ch.id)
            | (CharacterRelationship.to_character_id == ch.id)
        ).all():
            out["relationships"].append({
                "id": r.id, "from_character_id": r.from_character_id,
                "to_character_id": r.to_character_id,
                "relationship_type": r.relationship_type,
                "description": r.description, "is_bidirectional": r.is_bidirectional,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })
        for arc in s.query(CharacterArc).filter_by(character_id=ch.id).all():
            out["arcs"].append({
                "id": arc.id, "character_id": arc.character_id,
                "arc_name": arc.arc_name, "description": arc.description,
                "stages": arc.stages,
                "created_at": arc.created_at.isoformat() if arc.created_at else None,
            })
    return out


def snapshot_plan(p) -> dict:
    from core.db import read_session
    from models.plan import PlanSubtask
    out = {
        "plan": {
            "id": p.id, "project_id": p.project_id, "title": p.title,
            "description": p.description, "status": p.status, "column": p.column,
            "sort_order": p.sort_order, "chapter_id": p.chapter_id,
            "parent_id": p.parent_id, "depends_on_id": p.depends_on_id,
            "story_date": p.story_date, "event_type": p.event_type,
            "track": p.track, "characters_involved": p.characters_involved,
            "deadline": p.deadline.isoformat() if p.deadline else None,
            "effort_estimate": p.effort_estimate, "tags": p.tags,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        },
        "subtasks": [],
    }
    with read_session() as s:
        for st in s.query(PlanSubtask).filter_by(plan_id=p.id).all():
            out["subtasks"].append({
                "id": st.id, "plan_id": st.plan_id, "title": st.title,
                "is_completed": st.is_completed, "sort_order": st.sort_order,
                "created_at": st.created_at.isoformat() if st.created_at else None,
            })
    return out


def snapshot_world_entry(e) -> dict:
    from core.db import read_session
    from models.world import WorldEntryVersion, WorldEntryRelation
    out = {
        "entry": {
            "id": e.id, "project_id": e.project_id, "type": e.type,
            "name": e.name, "category": e.category, "description": e.description,
            "content": e.content, "notes": e.notes, "metadata": e.metadata_,
            "parent_id": e.parent_id, "map_pin_x": e.map_pin_x,
            "map_pin_y": e.map_pin_y, "map_pin_label": e.map_pin_label,
            "map_image_path": e.map_image_path, "sort_order": e.sort_order,
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "updated_at": e.updated_at.isoformat() if e.updated_at else None,
        },
        "versions": [],
        "relations": [],
    }
    with read_session() as s:
        for v in s.query(WorldEntryVersion).filter_by(entry_id=e.id).all():
            out["versions"].append({
                "id": v.id, "entry_id": v.entry_id,
                "version_number": v.version_number, "snapshot": v.snapshot,
                "source": v.source,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "notes": v.notes,
            })
        for r in s.query(WorldEntryRelation).filter(
            (WorldEntryRelation.from_entry_id == e.id)
            | (WorldEntryRelation.to_entry_id == e.id)
        ).all():
            out["relations"].append({
                "id": r.id, "from_entry_id": r.from_entry_id,
                "to_entry_id": r.to_entry_id,
                "relation_type": r.relation_type, "description": r.description,
            })
    return out


def record_delete(entity_type: str, entity_id: str, label: str,
                  snapshot: dict) -> None:
    """Record a delete operation for undo (called BEFORE the actual delete)."""
    from core.db import write_transaction
    with write_transaction() as s:
        # Cap the undo stack
        count = s.query(UndoOperation).count()
        if count >= MAX_UNDO:
            # Delete oldest entries
            oldest = s.query(UndoOperation).order_by(
                UndoOperation.id.asc()
            ).limit(count - MAX_UNDO + 1).all()
            for op in oldest:
                s.delete(op)
        s.add(UndoOperation(
            operation=f"delete_{entity_type}",
            label=label,
            entity_type=entity_type,
            entity_id=entity_id,
            snapshot=json.dumps(snapshot, ensure_ascii=False, default=str),
            undo_action="restore",
            created_at=datetime.now(timezone.utc),
        ))


def list_recent(limit: int = 20) -> list[UndoOperation]:
    from core.db import read_session
    with read_session() as s:
        return list(s.query(UndoOperation).order_by(
            UndoOperation.id.desc()
        ).limit(limit).all())


def undo_last() -> dict[str, Any] | None:
    """Undo the most recent operation. Returns {ok, label} or None."""
    from core.db import read_session, write_transaction
    with read_session() as s:
        last = s.query(UndoOperation).order_by(
            UndoOperation.id.desc()
        ).first()
        if not last:
            return None
        snapshot = json.loads(last.snapshot) if last.snapshot else {}
        op_id = last.id
        label = last.label
        entity_type = last.entity_type
        undo_action = last.undo_action

    # Perform the restore based on entity_type
    if undo_action == "restore":
        with write_transaction() as s:
            _restore_entity(s, entity_type, snapshot)
            # Remove the undo entry
            op = s.get(UndoOperation, op_id)
            if op:
                s.delete(op)
        return {"ok": True, "label": label, "action": "restored"}
    return {"ok": False, "label": label, "action": "unknown"}


def _restore_entity(session, entity_type: str, snapshot: dict) -> None:
    """Restore an entity + its related rows from a snapshot."""
    from models.chapter import Chapter, ChapterVersion
    from models.character import (Character, CharacterGroupMember,
                                   CharacterRelationship, CharacterArc)
    from models.plan import Plan, PlanSubtask
    from models.world import WorldEntry, WorldEntryVersion, WorldEntryRelation
    from datetime import datetime

    def _parse_dt(v):
        if not v:
            return None
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    if entity_type == "chapter":
        c = snapshot["chapter"]
        existing = session.get(Chapter, c["id"])
        if not existing:
            ch = Chapter(
                id=c["id"], project_id=c["project_id"], title=c["title"],
                content=c["content"], synopsis=c["synopsis"], status=c["status"],
                word_count=c["word_count"], target_word_count=c["target_word_count"],
                sort_order=c["sort_order"], character_ids=c["character_ids"],
                tags=c["tags"], raw_file_path=c["raw_file_path"],
                created_at=_parse_dt(c["created_at"]) or datetime.now(timezone.utc),
                updated_at=_parse_dt(c["updated_at"]) or datetime.now(timezone.utc),
            )
            session.add(ch)
        # Restore versions
        for v in snapshot["versions"]:
            if not session.get(ChapterVersion, v["id"]):
                session.add(ChapterVersion(
                    id=v["id"], chapter_id=v["chapter_id"],
                    version_number=v["version_number"], content=v["content"],
                    word_count=v["word_count"], source=v["source"],
                    uploaded_at=_parse_dt(v["uploaded_at"]) or datetime.now(timezone.utc),
                    notes=v["notes"],
                ))
    elif entity_type == "character":
        c = snapshot["character"]
        existing = session.get(Character, c["id"])
        if not existing:
            ch = Character(
                id=c["id"], project_id=c["project_id"], name=c["name"],
                age=c["age"], gender=c["gender"], aliases=c["aliases"],
                role=c["role"], avatar_color=c["avatar_color"],
                avatar_path=c["avatar_path"], physical=c["physical"],
                psychology=c["psychology"], background=c["background"],
                philosophy=c["philosophy"], philosophy_quotes=c["philosophy_quotes"],
                story_role=c["story_role"], story_role_chapters=c["story_role_chapters"],
                voice=c["voice"], notes=c["notes"],
                graph_x=c["graph_x"], graph_y=c["graph_y"],
                created_at=_parse_dt(c["created_at"]) or datetime.now(timezone.utc),
                updated_at=_parse_dt(c["updated_at"]) or datetime.now(timezone.utc),
            )
            session.add(ch)
        for gm in snapshot["group_memberships"]:
            if not session.get(CharacterGroupMember, gm["id"]):
                session.add(CharacterGroupMember(
                    id=gm["id"], character_id=c["id"], group_id=gm["group_id"],
                ))
        for r in snapshot["relationships"]:
            if not session.get(CharacterRelationship, r["id"]):
                session.add(CharacterRelationship(
                    id=r["id"], from_character_id=r["from_character_id"],
                    to_character_id=r["to_character_id"],
                    relationship_type=r["relationship_type"],
                    description=r["description"],
                    is_bidirectional=r["is_bidirectional"],
                    created_at=_parse_dt(r["created_at"]) or datetime.now(timezone.utc),
                ))
        for arc in snapshot["arcs"]:
            if not session.get(CharacterArc, arc["id"]):
                session.add(CharacterArc(
                    id=arc["id"], character_id=arc["character_id"],
                    arc_name=arc["arc_name"], description=arc["description"],
                    stages=arc["stages"],
                    created_at=_parse_dt(arc["created_at"]) or datetime.now(timezone.utc),
                ))
    elif entity_type == "plan":
        p = snapshot["plan"]
        existing = session.get(Plan, p["id"])
        if not existing:
            from datetime import date as date_type
            deadline = None
            if p["deadline"]:
                try:
                    deadline = date_type.fromisoformat(p["deadline"])
                except (ValueError, TypeError):
                    pass
            session.add(Plan(
                id=p["id"], project_id=p["project_id"], title=p["title"],
                description=p["description"], status=p["status"], column=p["column"],
                sort_order=p["sort_order"], chapter_id=p["chapter_id"],
                parent_id=p["parent_id"], depends_on_id=p["depends_on_id"],
                story_date=p["story_date"], event_type=p["event_type"],
                track=p["track"], characters_involved=p["characters_involved"],
                deadline=deadline, effort_estimate=p["effort_estimate"],
                tags=p["tags"],
                created_at=_parse_dt(p["created_at"]) or datetime.now(timezone.utc),
                updated_at=_parse_dt(p["updated_at"]) or datetime.now(timezone.utc),
            ))
        for st in snapshot["subtasks"]:
            if not session.get(PlanSubtask, st["id"]):
                session.add(PlanSubtask(
                    id=st["id"], plan_id=st["plan_id"], title=st["title"],
                    is_completed=st["is_completed"], sort_order=st["sort_order"],
                    created_at=_parse_dt(st["created_at"]) or datetime.now(timezone.utc),
                ))
    elif entity_type == "world_entry":
        e = snapshot["entry"]
        existing = session.get(WorldEntry, e["id"])
        if not existing:
            session.add(WorldEntry(
                id=e["id"], project_id=e["project_id"], type=e["type"],
                name=e["name"], category=e["category"], description=e["description"],
                content=e["content"], notes=e["notes"], metadata_=e["metadata"],
                parent_id=e["parent_id"], map_pin_x=e["map_pin_x"],
                map_pin_y=e["map_pin_y"], map_pin_label=e["map_pin_label"],
                map_image_path=e["map_image_path"], sort_order=e["sort_order"],
                created_at=_parse_dt(e["created_at"]) or datetime.now(timezone.utc),
                updated_at=_parse_dt(e["updated_at"]) or datetime.now(timezone.utc),
            ))
        for v in snapshot["versions"]:
            if not session.get(WorldEntryVersion, v["id"]):
                session.add(WorldEntryVersion(
                    id=v["id"], entry_id=v["entry_id"],
                    version_number=v["version_number"], snapshot=v["snapshot"],
                    source=v["source"],
                    created_at=_parse_dt(v["created_at"]) or datetime.now(timezone.utc),
                    notes=v["notes"],
                ))
        for r in snapshot["relations"]:
            if not session.get(WorldEntryRelation, r["id"]):
                session.add(WorldEntryRelation(
                    id=r["id"], from_entry_id=r["from_entry_id"],
                    to_entry_id=r["to_entry_id"],
                    relation_type=r["relation_type"], description=r["description"],
                ))


# Need this import for the datetime usage in _restore_entity
from datetime import timezone  # noqa: E402
