"""Character Arc Tracker service — manage character development arcs.

Each character can have multiple arcs (e.g. "Redemption Arc", "Coming of Age").
Each arc has stages (JSON array): {name, description, status, chapter_ids}.

Statuses: planned / active / completed / skipped

The tracker computes:
- Progress % (completed stages / total stages)
- Current stage (first non-completed)
- Linked chapters per stage
- Overall arc status (based on stage statuses)
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from core.db import read_session, write_transaction
from core.errors import NotFoundError, ValidationError
from models.character import Character, CharacterArc
from services._common import current_project_id, dump_json, load_json, new_uuid, now_utc

log = logging.getLogger("asm.character_arcs")


STAGE_STATUSES = {
    "planned":    {"label": "Planned",    "icon": "○", "color": "#94a3b8"},
    "active":     {"label": "Active",     "icon": "◐", "color": "#facc15"},
    "completed":  {"label": "Completed",  "icon": "●", "color": "#34d399"},
    "skipped":    {"label": "Skipped",    "icon": "✕", "color": "#6b7299"},
}


def list_arcs(character_id: str | None = None) -> list[CharacterArc]:
    with read_session() as s:
        q = select(CharacterArc)
        if character_id:
            q = q.where(CharacterArc.character_id == character_id)
        return list(s.scalars(q.order_by(CharacterArc.created_at.asc())))


def get_arc(arc_id: str) -> CharacterArc:
    with read_session() as s:
        arc = s.get(CharacterArc, arc_id)
        if not arc:
            raise NotFoundError("Character arc not found.")
        return arc


def create_arc(*, character_id: str, arc_name: str, description: str = "",
               stages: list[dict] | None = None) -> CharacterArc:
    if not arc_name or len(arc_name) > 200:
        raise ValidationError("Arc name required, ≤ 200 chars.")
    with write_transaction() as s:
        # Verify character exists
        ch = s.get(Character, character_id)
        if not ch:
            raise NotFoundError("Character not found.")
        arc = CharacterArc(
            id=new_uuid(),
            character_id=character_id,
            arc_name=arc_name.strip(),
            description=description or "",
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
            raise NotFoundError("Character arc not found.")
        for k in ("arc_name", "description"):
            if k in fields and fields[k] is not None:
                setattr(arc, k, fields[k])
        if "stages" in fields:
            stages = fields["stages"]
            if not isinstance(stages, list):
                raise ValidationError("stages must be a list")
            arc.stages = dump_json(stages)
        s.flush()
        return arc


def delete_arc(arc_id: str) -> None:
    with write_transaction() as s:
        arc = s.get(CharacterArc, arc_id)
        if arc:
            s.delete(arc)


def add_stage(arc_id: str, *, name: str, description: str = "",
              status: str = "planned", chapter_ids: list[str] | None = None) -> CharacterArc:
    if status not in STAGE_STATUSES:
        raise ValidationError(f"status must be one of {list(STAGE_STATUSES)}")
    with write_transaction() as s:
        arc = s.get(CharacterArc, arc_id)
        if not arc:
            raise NotFoundError("Character arc not found.")
        stages = load_json(arc.stages, [])
        stages.append({
            "name": name,
            "description": description,
            "status": status,
            "chapter_ids": chapter_ids or [],
        })
        arc.stages = dump_json(stages)
        s.flush()
        return arc


def update_stage(arc_id: str, stage_index: int, **fields: Any) -> CharacterArc:
    with write_transaction() as s:
        arc = s.get(CharacterArc, arc_id)
        if not arc:
            raise NotFoundError("Character arc not found.")
        stages = load_json(arc.stages, [])
        if stage_index < 0 or stage_index >= len(stages):
            raise ValidationError("Invalid stage index.")
        for k in ("name", "description", "status", "chapter_ids"):
            if k in fields and fields[k] is not None:
                stages[stage_index][k] = fields[k]
        arc.stages = dump_json(stages)
        s.flush()
        return arc


def remove_stage(arc_id: str, stage_index: int) -> CharacterArc:
    with write_transaction() as s:
        arc = s.get(CharacterArc, arc_id)
        if not arc:
            raise NotFoundError("Character arc not found.")
        stages = load_json(arc.stages, [])
        if stage_index < 0 or stage_index >= len(stages):
            raise ValidationError("Invalid stage index.")
        stages.pop(stage_index)
        arc.stages = dump_json(stages)
        s.flush()
        return arc


def to_dict(arc: CharacterArc) -> dict[str, Any]:
    stages = load_json(arc.stages, [])
    total = len(stages)
    completed = sum(1 for st in stages if st.get("status") == "completed")
    skipped = sum(1 for st in stages if st.get("status") == "skipped")
    active = sum(1 for st in stages if st.get("status") == "active")
    progress_pct = round(completed / max(1, total) * 100, 1) if total else 0
    # Current stage = first non-completed, non-skipped
    current_stage = None
    for i, st in enumerate(stages):
        if st.get("status") in ("planned", "active"):
            current_stage = {"index": i, **st}
            break
    # Overall status
    if total == 0:
        overall = "empty"
    elif completed + skipped == total:
        overall = "completed" if completed > 0 else "skipped"
    elif active > 0:
        overall = "active"
    else:
        overall = "planned"
    return {
        "id": arc.id,
        "character_id": arc.character_id,
        "arc_name": arc.arc_name,
        "description": arc.description or "",
        "stages": stages,
        "stage_count": total,
        "completed_stages": completed,
        "active_stages": active,
        "skipped_stages": skipped,
        "progress_pct": progress_pct,
        "current_stage": current_stage,
        "overall_status": overall,
        "created_at": arc.created_at.isoformat() if arc.created_at else None,
    }


def stats() -> dict[str, Any]:
    """Aggregate stats across all arcs."""
    arcs = list_arcs()
    all_dicts = [to_dict(a) for a in arcs]
    return {
        "total_arcs": len(arcs),
        "completed_arcs": sum(1 for d in all_dicts if d["overall_status"] == "completed"),
        "active_arcs": sum(1 for d in all_dicts if d["overall_status"] == "active"),
        "planned_arcs": sum(1 for d in all_dicts if d["overall_status"] == "planned"),
        "total_stages": sum(d["stage_count"] for d in all_dicts),
        "completed_stages": sum(d["completed_stages"] for d in all_dicts),
    }
