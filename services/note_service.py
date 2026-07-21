"""Notes & Ideas Inbox — quick-capture for stray thoughts that don't fit elsewhere.

A writer's scratchpad: ideas, questions, reminders, references, scene snippets.
Notes can be:
- Categorized (idea / question / reminder / reference / scene_idea / todo)
- Pinned for prominence
- Linked to a chapter, character, world entry, or plan (cross-reference)
- Tagged
- Searched (FTS5 + LIKE fallback)
- Promoted: convert a note into a chapter, snippet, or plan

This module is intentionally lightweight — it's the inbox, not the filing cabinet.
The workflow is: capture → triage → promote or delete.
"""
from __future__ import annotations

import logging
from typing import Any

from core.db import read_session, write_transaction
from core.errors import NotFoundError, ValidationError
from models.note import Note
from services._common import current_project_id, dump_json, load_json, log_activity, new_uuid, now_utc

log = logging.getLogger("asm.notes")


NOTE_CATEGORIES = {
    "idea":       {"label": "Idea",        "icon": "💡", "color": "#facc15"},
    "question":   {"label": "Question",     "icon": "❓", "color": "#60a5fa"},
    "reminder":   {"label": "Reminder",     "icon": "⏰", "color": "#f87171"},
    "reference":  {"label": "Reference",    "icon": "📚", "color": "#a78bfa"},
    "scene_idea": {"label": "Scene Idea",   "icon": "🎬", "color": "#34d399"},
    "todo":       {"label": "Todo",         "icon": "✓",  "color": "#94a3b8"},
}


def list_notes(
    *,
    category: str | None = None,
    tag: str | None = None,
    search: str | None = None,
    pinned_only: bool = False,
    include_done: bool = True,
    limit: int = 200,
) -> list[Note]:
    with read_session() as s:
        q = s.query(Note).filter_by(project_id=current_project_id(s))
        if category and category != "all":
            q = q.filter_by(category=category)
        if pinned_only:
            q = q.filter_by(pinned=1)
        if not include_done:
            q = q.filter_by(done=0)
        if search:
            like = f"%{search}%"
            q = q.filter((Note.title.like(like)) | (Note.body.like(like)))
        notes = list(q.order_by(Note.pinned.desc(),
                                Note.created_at.desc()).limit(limit).all())
        if tag:
            # Filter by tag in Python (tags stored as JSON)
            notes = [n for n in notes if tag in load_json(n.tags, [])]
        return notes


def get_note(note_id: str) -> Note:
    with read_session() as s:
        n = s.get(Note, note_id)
        if not n:
            raise NotFoundError("Note not found.")
        return n


def create_note(
    *, title: str, body: str = "", category: str = "idea",
    tags: list[str] | None = None,
    links: list[dict] | None = None,
    pinned: bool = False,
) -> Note:
    if category not in NOTE_CATEGORIES:
        raise ValidationError(f"Category must be one of {list(NOTE_CATEGORIES)}.")
    if not title and not body:
        raise ValidationError("Either title or body is required.")
    if title and len(title) > 500:
        raise ValidationError("Title must be ≤ 500 chars.")
    nid = new_uuid()
    with write_transaction() as s:
        n = Note(
            id=nid,
            project_id=current_project_id(s),
            title=(title or "").strip(),
            body=body or "",
            category=category,
            tags=dump_json(tags or []),
            links=dump_json(links or []),
            pinned=1 if pinned else 0,
            done=0,
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        s.add(n)
        log_activity(
            s, entity_type="note", entity_id=nid,
            entity_title=title or (body or "")[:80],
            action="created",
            details={"category": category},
        )
        s.flush()
        return n


def update_note(note_id: str, **fields: Any) -> Note:
    with write_transaction() as s:
        n = s.get(Note, note_id)
        if not n:
            raise NotFoundError("Note not found.")
        for k in ("title", "body", "category"):
            if k in fields and fields[k] is not None:
                setattr(n, k, fields[k])
        if "tags" in fields:
            n.tags = dump_json(fields["tags"] or [])
        if "links" in fields:
            n.links = dump_json(fields["links"] or [])
        if "pinned" in fields:
            n.pinned = 1 if fields["pinned"] else 0
        if "done" in fields:
            n.done = 1 if fields["done"] else 0
        n.updated_at = now_utc()
        s.flush()
        return n


def delete_note(note_id: str) -> None:
    with write_transaction() as s:
        n = s.get(Note, note_id)
        if n:
            s.delete(n)


def toggle_pin(note_id: str) -> Note:
    with write_transaction() as s:
        n = s.get(Note, note_id)
        if not n:
            raise NotFoundError("Note not found.")
        n.pinned = 0 if n.pinned else 1
        n.updated_at = now_utc()
        s.flush()
        return n


def toggle_done(note_id: str) -> Note:
    with write_transaction() as s:
        n = s.get(Note, note_id)
        if not n:
            raise NotFoundError("Note not found.")
        n.done = 0 if n.done else 1
        n.updated_at = now_utc()
        s.flush()
        return n


def add_link(note_id: str, entity_type: str, entity_id: str, entity_title: str) -> Note:
    """Attach a cross-reference link to a note."""
    if entity_type not in ("chapter", "character", "world_entry", "plan"):
        raise ValidationError("entity_type must be chapter/character/world_entry/plan")
    with write_transaction() as s:
        n = s.get(Note, note_id)
        if not n:
            raise NotFoundError("Note not found.")
        links = load_json(n.links, [])
        # Avoid duplicates
        if not any(l.get("entity_id") == entity_id for l in links):
            links.append({
                "entity_type": entity_type,
                "entity_id": entity_id,
                "entity_title": entity_title[:300],
            })
            n.links = dump_json(links)
            n.updated_at = now_utc()
        s.flush()
        return n


def remove_link(note_id: str, entity_id: str) -> Note:
    with write_transaction() as s:
        n = s.get(Note, note_id)
        if not n:
            raise NotFoundError("Note not found.")
        links = load_json(n.links, [])
        links = [l for l in links if l.get("entity_id") != entity_id]
        n.links = dump_json(links)
        n.updated_at = now_utc()
        s.flush()
        return n


def all_tags() -> list[str]:
    """Return all unique tags across notes (for tag filter dropdown)."""
    with read_session() as s:
        notes = list(s.query(Note).filter_by(project_id=current_project_id(s)).all())
        tags: set[str] = set()
        for n in notes:
            for t in load_json(n.tags, []):
                tags.add(t)
        return sorted(tags)


def to_dict(n: Note) -> dict[str, Any]:
    return {
        "id": n.id,
        "title": n.title,
        "body": n.body,
        "category": n.category,
        "category_label": NOTE_CATEGORIES.get(n.category, {}).get("label", n.category),
        "icon": NOTE_CATEGORIES.get(n.category, {}).get("icon", "📝"),
        "color": NOTE_CATEGORIES.get(n.category, {}).get("color", "#94a3b8"),
        "tags": load_json(n.tags, []),
        "links": load_json(n.links, []),
        "pinned": bool(n.pinned),
        "done": bool(n.done),
        "created_at": n.created_at.isoformat() if n.created_at else None,
        "updated_at": n.updated_at.isoformat() if n.updated_at else None,
    }


def promote_to_chapter(note_id: str) -> str:
    """Convert a note into a new chapter. Returns the new chapter id."""
    n = get_note(note_id)
    from services.chapter_service import create_chapter
    title = n.title or "Untitled Note Chapter"
    content = ""
    if n.body:
        content = f"> Note (originally '{n.category}'): {n.body}\n\n"
    ch = create_chapter(title=title[:500], content=content, synopsis=n.body[:200] if n.body else "")
    # Mark note as done so it's removed from inbox view
    toggle_done(note_id)
    return ch.id


def promote_to_snippet(note_id: str) -> str:
    """Convert a note into a snippet."""
    n = get_note(note_id)
    from services.snippet_service import create_snippet
    snip = create_snippet(
        name=(n.title or "Note Snippet")[:200],
        content=n.body or n.title or "",
        category="snippet",
    )
    toggle_done(note_id)
    return snip.id


def promote_to_plan(note_id: str) -> str:
    """Convert a note into a plan item."""
    n = get_note(note_id)
    from services.plan_service import create_plan
    p = create_plan(
        title=(n.title or "Untitled Note Plan")[:500],
        description=n.body or "",
        status="idea",
    )
    toggle_done(note_id)
    return p.id
