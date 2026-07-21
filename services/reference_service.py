"""Research & References service — track sources, quotes, citations."""
from __future__ import annotations

import logging
from typing import Any

from core.db import read_session, write_transaction
from core.errors import NotFoundError, ValidationError
from models.reference import (
    Reference, REFERENCE_TYPES, READ_STATUSES, PRIORITIES,
)
from services._common import current_project_id, dump_json, load_json, log_activity, new_uuid, now_utc

log = logging.getLogger("asm.references")


def list_references(
    *, source_type: str | None = None, read_status: str | None = None,
    priority: str | None = None, tag: str | None = None,
    search: str | None = None,
) -> list[Reference]:
    with read_session() as s:
        q = s.query(Reference).filter_by(project_id=current_project_id(s))
        if source_type and source_type != "all":
            q = q.filter_by(source_type=source_type)
        if read_status and read_status != "all":
            q = q.filter_by(read_status=read_status)
        if priority and priority != "all":
            q = q.filter_by(priority=priority)
        if search:
            like = f"%{search}%"
            q = q.filter(
                (Reference.title.like(like))
                | (Reference.author.like(like))
                | (Reference.description.like(like))
            )
        refs = list(q.all())
        if tag:
            refs = [r for r in refs if tag in load_json(r.tags, [])]
        # Sort by priority (high > medium > low) then by created_at desc
        priority_order = {"high": 0, "medium": 1, "low": 2}
        refs.sort(key=lambda r: (
            priority_order.get(r.priority, 99),
            -(r.created_at.timestamp() if r.created_at else 0),
        ))
        return refs


def get_reference(ref_id: str) -> Reference:
    with read_session() as s:
        r = s.get(Reference, ref_id)
        if not r:
            raise NotFoundError("Reference not found.")
        return r


def create_reference(
    *, title: str, author: str = "", url: str = "",
    source_type: str = "article", publication_date: str = "",
    publisher: str = "", isbn_or_doi: str = "",
    description: str = "",
    quotes: list[dict] | None = None,
    tags: list[str] | None = None,
    chapter_ids: list[str] | None = None,
    read_status: str = "unread", priority: str = "medium",
    rating: int | None = None, notes: str = "",
) -> Reference:
    if not title or len(title) > 500:
        raise ValidationError("Title required, ≤ 500 chars.")
    if source_type not in REFERENCE_TYPES:
        raise ValidationError(f"source_type must be one of {list(REFERENCE_TYPES)}.")
    if read_status not in READ_STATUSES:
        raise ValidationError(f"read_status must be one of {list(READ_STATUSES)}.")
    if priority not in PRIORITIES:
        raise ValidationError(f"priority must be one of {list(PRIORITIES)}.")
    if rating is not None and not (1 <= rating <= 5):
        raise ValidationError("rating must be 1-5 or null.")
    rid = new_uuid()
    with write_transaction() as s:
        r = Reference(
            id=rid,
            project_id=current_project_id(s),
            title=title.strip(),
            author=author or "",
            url=url or "",
            source_type=source_type,
            publication_date=publication_date or "",
            publisher=publisher or "",
            isbn_or_doi=isbn_or_doi or "",
            description=description or "",
            quotes=dump_json(quotes or []),
            tags=dump_json(tags or []),
            chapter_ids=dump_json(chapter_ids or []),
            read_status=read_status,
            priority=priority,
            rating=rating,
            notes=notes or "",
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        s.add(r)
        log_activity(
            s, entity_type="reference", entity_id=rid,
            entity_title=title, action="created",
        )
        s.flush()
        return r


def update_reference(ref_id: str, **fields: Any) -> Reference:
    with write_transaction() as s:
        r = s.get(Reference, ref_id)
        if not r:
            raise NotFoundError("Reference not found.")
        for k in ("title", "author", "url", "source_type", "publication_date",
                  "publisher", "isbn_or_doi", "description", "read_status",
                  "priority", "notes"):
            if k in fields and fields[k] is not None:
                setattr(r, k, fields[k])
        if "rating" in fields:
            rating = fields["rating"]
            if rating and not (1 <= int(rating) <= 5):
                raise ValidationError("rating must be 1-5 or null.")
            r.rating = int(rating) if rating else None
        if "quotes" in fields:
            r.quotes = dump_json(fields["quotes"] or [])
        if "tags" in fields:
            r.tags = dump_json(fields["tags"] or [])
        if "chapter_ids" in fields:
            r.chapter_ids = dump_json(fields["chapter_ids"] or [])
        r.updated_at = now_utc()
        s.flush()
        return r


def delete_reference(ref_id: str) -> None:
    with write_transaction() as s:
        r = s.get(Reference, ref_id)
        if r:
            s.delete(r)


def to_dict(r: Reference) -> dict[str, Any]:
    return {
        "id": r.id,
        "title": r.title,
        "author": r.author or "",
        "url": r.url or "",
        "source_type": r.source_type,
        "source_type_label": REFERENCE_TYPES.get(r.source_type, {}).get("label", r.source_type),
        "source_icon": REFERENCE_TYPES.get(r.source_type, {}).get("icon", "📝"),
        "publication_date": r.publication_date or "",
        "publisher": r.publisher or "",
        "isbn_or_doi": r.isbn_or_doi or "",
        "description": r.description or "",
        "quotes": load_json(r.quotes, []),
        "tags": load_json(r.tags, []),
        "chapter_ids": load_json(r.chapter_ids, []),
        "read_status": r.read_status,
        "read_status_label": READ_STATUSES.get(r.read_status, {}).get("label", r.read_status),
        "read_status_icon": READ_STATUSES.get(r.read_status, {}).get("icon", "📝"),
        "read_status_color": READ_STATUSES.get(r.read_status, {}).get("color", "#94a3b8"),
        "priority": r.priority,
        "priority_label": PRIORITIES.get(r.priority, {}).get("label", r.priority),
        "priority_icon": PRIORITIES.get(r.priority, {}).get("icon", "="),
        "priority_color": PRIORITIES.get(r.priority, {}).get("color", "#94a3b8"),
        "rating": r.rating,
        "notes": r.notes or "",
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def all_tags() -> list[str]:
    with read_session() as s:
        refs = list(s.query(Reference).filter_by(project_id=current_project_id(s)).all())
        tags: set[str] = set()
        for r in refs:
            for t in load_json(r.tags, []):
                tags.add(t)
        return sorted(tags)


def stats() -> dict[str, Any]:
    refs = list_references()
    by_type: dict[str, int] = {t: 0 for t in REFERENCE_TYPES}
    by_status: dict[str, int] = {s: 0 for s in READ_STATUSES}
    by_priority: dict[str, int] = {p: 0 for p in PRIORITIES}
    rated = []
    for r in refs:
        by_type[r.source_type] = by_type.get(r.source_type, 0) + 1
        by_status[r.read_status] = by_status.get(r.read_status, 0) + 1
        by_priority[r.priority] = by_priority.get(r.priority, 0) + 1
        if r.rating:
            rated.append(r.rating)
    avg_rating = round(sum(rated) / len(rated), 1) if rated else 0
    return {
        "total": len(refs),
        "by_type": by_type,
        "by_status": by_status,
        "by_priority": by_priority,
        "avg_rating": avg_rating,
        "read": by_status.get("read", 0),
        "reading": by_status.get("reading", 0),
        "unread": by_status.get("unread", 0),
    }
