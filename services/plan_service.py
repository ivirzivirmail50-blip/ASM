"""Plan service: CRUD, subtasks, status, reorder, dependencies."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.db import read_session, write_transaction
from core.errors import NotFoundError, ValidationError
from models.plan import Plan, PlanSubtask
from security import limits
from services._common import (
    current_project_id, dump_json, load_json, log_activity, new_uuid, now_utc,
)

log = logging.getLogger("asm.plan")

STATUS_COLUMNS = ("idea", "planned", "writing", "draft_done", "revised", "final")


def list_plans(*, status: str | None = None, track: str | None = None) -> list[Plan]:
    with read_session() as s:
        q = select(Plan).where(Plan.project_id == current_project_id(s))
        if status and status != "all":
            q = q.where(Plan.status == status)
        if track:
            q = q.where(Plan.track == track)
        q = q.order_by(Plan.sort_order.asc())
        return list(s.scalars(q).all())


def get_plan(plan_id: str) -> Plan:
    with read_session() as s:
        p = s.get(Plan, plan_id)
        if not p:
            raise NotFoundError("Plan not found.")
        return p


def create_plan(
    *, title: str, description: str | None = None,
    status: str = "idea", column: str | None = None,
    chapter_id: str | None = None, parent_id: str | None = None,
    depends_on_id: str | None = None, story_date: str | None = None,
    event_type: str | None = None, track: str | None = None,
    characters_involved: list[str] | None = None,
    deadline: date | None = None, effort_estimate: int | None = None,
    tags: list[str] | None = None,
) -> Plan:
    if not title or len(title) > limits.TITLE_MAX:
        raise ValidationError("Title required, ≤ 500 chars.")
    if status not in STATUS_COLUMNS:
        raise ValidationError(f"Status must be one of {STATUS_COLUMNS}.")
    pid = new_uuid()
    with write_transaction() as s:
        from sqlalchemy import func
        max_order = s.scalar(
            select(func.max(Plan.sort_order)).where(
                Plan.project_id == current_project_id(s)
            )
        ) or 0
        p = Plan(
            id=pid,
            project_id=current_project_id(s),
            title=title,
            description=description,
            status=status,
            column=column or status,
            sort_order=max_order + 1,
            chapter_id=chapter_id,
            parent_id=parent_id,
            depends_on_id=depends_on_id,
            story_date=story_date,
            event_type=event_type,
            track=track,
            characters_involved=dump_json(characters_involved or []),
            deadline=deadline,
            effort_estimate=effort_estimate,
            tags=dump_json(tags or []),
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        s.add(p)
        log_activity(
            s, entity_type="plan", entity_id=pid, entity_title=title,
            action="created",
        )
        s.flush()
        return p


def update_plan(plan_id: str, **fields: Any) -> Plan:
    with write_transaction() as s:
        p = s.get(Plan, plan_id)
        if not p:
            raise NotFoundError("Plan not found.")
        for k in ("title", "description", "status", "column",
                  "chapter_id", "parent_id", "depends_on_id", "story_date",
                  "event_type", "track", "deadline", "effort_estimate"):
            if k in fields and fields[k] is not None:
                setattr(p, k, fields[k])
        for k in ("characters_involved", "tags"):
            if k in fields:
                setattr(p, k, dump_json(fields[k] or []))
        p.updated_at = now_utc()
        log_activity(
            s, entity_type="plan", entity_id=plan_id,
            entity_title=p.title, action="updated",
        )
        s.flush()
        return p


def delete_plan(plan_id: str) -> str:
    """Delete a plan. Records undo snapshot. Returns label."""
    from models.undo import snapshot_plan, record_delete
    p = get_plan(plan_id)
    snapshot = snapshot_plan(p)
    label = f"Delete plan '{p.title}'"
    record_delete("plan", plan_id, label, snapshot)
    with write_transaction() as s:
        p = s.get(Plan, plan_id)
        if not p:
            raise NotFoundError("Plan not found.")
        title = p.title
        s.query(PlanSubtask).filter_by(plan_id=plan_id).delete()
        # Detach children
        s.query(Plan).filter(Plan.parent_id == plan_id).update(
            {Plan.parent_id: None}
        )
        s.delete(p)
        log_activity(
            s, entity_type="plan", entity_id=plan_id,
            entity_title=title, action="deleted",
        )
    return label


def change_status(plan_id: str, new_status: str) -> Plan:
    if new_status not in STATUS_COLUMNS:
        raise ValidationError("Invalid status.")
    with write_transaction() as s:
        p = s.get(Plan, plan_id)
        if not p:
            raise NotFoundError("Plan not found.")
        p.status = new_status
        p.column = new_status
        p.updated_at = now_utc()
        log_activity(
            s, entity_type="plan", entity_id=plan_id,
            entity_title=p.title, action="status_changed",
            details={"status": new_status},
        )
        s.flush()
        return p


def reorder_in_column(column: str, ordered_ids: list[str]) -> None:
    """Update sort_order for plans in a specific Kanban column."""
    with write_transaction() as s:
        for idx, pid in enumerate(ordered_ids):
            p = s.get(Plan, pid)
            if p:
                p.sort_order = idx + 1
                p.column = column
        log_activity(
            s, entity_type="plan", entity_id="batch",
            entity_title=column, action="reordered",
        )


def reorder_all(orders_by_column: dict[str, list[str]]) -> None:
    """Update sort_order for plans across all columns."""
    with write_transaction() as s:
        for col, ids in orders_by_column.items():
            for idx, pid in enumerate(ids):
                p = s.get(Plan, pid)
                if p:
                    p.sort_order = idx + 1
                    p.column = col
        log_activity(
            s, entity_type="plan", entity_id="batch",
            entity_title="Kanban", action="reordered",
        )


def reorder_nested(items: list[dict]) -> None:
    """Update sort_order and parent_id for outline items.

    Each item dict: {id, parent_id (or null), sort_order}
    """
    with write_transaction() as s:
        for item in items:
            p = s.get(Plan, item.get("id"))
            if not p:
                continue
            parent = item.get("parent_id")
            p.parent_id = parent if parent else None
            p.sort_order = int(item.get("sort_order", 0))
        log_activity(
            s, entity_type="plan", entity_id="batch",
            entity_title="Outline", action="reordered",
        )


# ---- Subtasks ----

def list_subtasks(plan_id: str) -> list[PlanSubtask]:
    with read_session() as s:
        return list(s.scalars(
            select(PlanSubtask).where(PlanSubtask.plan_id == plan_id)
            .order_by(PlanSubtask.sort_order.asc())
        ).all())


def add_subtask(plan_id: str, title: str) -> PlanSubtask:
    if not title or len(title) > limits.TITLE_MAX:
        raise ValidationError("Subtask title required.")
    with write_transaction() as s:
        from sqlalchemy import func
        max_order = s.scalar(
            select(func.max(PlanSubtask.sort_order))
            .where(PlanSubtask.plan_id == plan_id)
        ) or 0
        st = PlanSubtask(
            id=new_uuid(), plan_id=plan_id, title=title,
            is_completed=False, sort_order=max_order + 1,
            created_at=now_utc(),
        )
        s.add(st)
        s.flush()
        return st


def update_subtask(subtask_id: str, *, title: str | None = None,
                   is_completed: bool | None = None,
                   sort_order: int | None = None) -> PlanSubtask:
    with write_transaction() as s:
        st = s.get(PlanSubtask, subtask_id)
        if not st:
            raise NotFoundError("Subtask not found.")
        if title is not None:
            st.title = title
        if is_completed is not None:
            st.is_completed = bool(is_completed)
        if sort_order is not None:
            st.sort_order = int(sort_order)
        s.flush()
        return st


def delete_subtask(subtask_id: str) -> None:
    with write_transaction() as s:
        st = s.get(PlanSubtask, subtask_id)
        if st:
            s.delete(st)


def reorder_subtasks(plan_id: str, ordered_ids: list[str]) -> None:
    with write_transaction() as s:
        for idx, sid in enumerate(ordered_ids):
            st = s.get(PlanSubtask, sid)
            if st:
                st.sort_order = idx + 1


def subtask_counts_for_plans(plan_ids: list[str]) -> dict[str, tuple[int, int]]:
    """Return {plan_id: (completed_count, total_count)} for the given plans."""
    if not plan_ids:
        return {}
    with read_session() as s:
        rows = s.execute(
            select(PlanSubtask.plan_id, PlanSubtask.is_completed)
            .where(PlanSubtask.plan_id.in_(plan_ids))
        ).all()
        out: dict[str, list[int]] = {pid: [0, 0] for pid in plan_ids}
        for pid, is_done in rows:
            if pid not in out:
                out[pid] = [0, 0]
            out[pid][1] += 1
            if is_done:
                out[pid][0] += 1
        return {pid: (counts[0], counts[1]) for pid, counts in out.items()}


def actual_word_counts_for_plans(plan_ids: list[str]) -> dict[str, int]:
    """Return {plan_id: actual_word_count} from linked chapters."""
    if not plan_ids:
        return {}
    from models.chapter import Chapter
    with read_session() as s:
        plans = s.scalars(
            select(Plan).where(Plan.id.in_(plan_ids))
        ).all()
        out = {}
        for p in plans:
            if p.chapter_id:
                ch = s.get(Chapter, p.chapter_id)
                out[p.id] = ch.word_count if ch else 0
            else:
                out[p.id] = 0
        return out


def dependency_warnings(plan_ids: list[str]) -> dict[str, list[str]]:
    """Return {plan_id: [warning_messages]} for dependency conflicts.

    A warning is generated when a plan depends on another plan whose status
    is "behind" (e.g., dependent is "writing" but blocker is still "idea").
    """
    if not plan_ids:
        return {}
    status_order = {s: i for i, s in enumerate(STATUS_COLUMNS)}
    with read_session() as s:
        plans = s.scalars(
            select(Plan).where(Plan.id.in_(plan_ids))
        ).all()
        plan_map = {p.id: p for p in plans}
        out: dict[str, list[str]] = {pid: [] for pid in plan_ids}
        for p in plans:
            if not p.depends_on_id:
                continue
            blocker = plan_map.get(p.depends_on_id)
            if not blocker:
                out[p.id].append(f"Depends on missing plan {p.depends_on_id[:8]}")
                continue
            my_progress = status_order.get(p.status, 0)
            blocker_progress = status_order.get(blocker.status, 0)
            if my_progress > blocker_progress:
                out[p.id].append(
                    f"Depends on '{blocker.title}' which is behind "
                    f"(blocker: {blocker.status}, this: {p.status})"
                )
        return out


def overdue_plans() -> list[str]:
    """Return plan_ids that are overdue (deadline < today and not final)."""
    from datetime import date
    today = date.today()
    with read_session() as s:
        rows = s.scalars(
            select(Plan).where(
                Plan.deadline.is_not(None),
                Plan.deadline < today,
                Plan.status != "final",
            )
        ).all()
        return [p.id for p in rows]


def get_track_order() -> list[str]:
    """Get the saved track ordering from settings.

    Returns a list of track names in display order.
    Tracks not in the saved list are appended alphabetically.
    """
    from core.db import read_session
    from models.settings import Setting
    with read_session() as s:
        import json
        raw = Setting.get(s, "timeline_track_order", [])
        if isinstance(raw, str):
            try:
                saved = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                saved = []
        else:
            saved = raw or []
        # Get all existing tracks
        all_tracks = set()
        rows = s.scalars(
            select(Plan.track).where(Plan.track.is_not(None)).distinct()
        ).all()
        all_tracks = {t for t in rows if t}
        # Saved order first, then any new tracks alphabetically
        ordered = [t for t in saved if t in all_tracks]
        remaining = sorted(all_tracks - set(ordered))
        return ordered + remaining


def reorder_tracks(track_names: list[str]) -> None:
    """Save the display order of timeline tracks.

    Args:
        track_names: List of track names in the desired display order.
    """
    import json
    from core.db import write_transaction
    from models.settings import Setting
    with write_transaction() as s:
        Setting.set(s, "timeline_track_order", track_names)
