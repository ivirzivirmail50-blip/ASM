"""Editorial checklist service — per-chapter revision workflow."""
from __future__ import annotations

import json
import logging

from sqlalchemy import Column, DateTime, Integer, String, Text, Boolean
from datetime import datetime, timezone

from models import Base
from core.db import read_session, write_transaction
from services._common import new_uuid, now_utc

log = logging.getLogger("asm.checklist")


class ChapterChecklist(Base):
    """Editorial checklist items for a chapter's revision workflow."""
    __tablename__ = "chapter_checklists"

    id = Column(String, primary_key=True)
    chapter_id = Column(String, index=True, nullable=False)
    item_text = Column(String(500), nullable=False)
    is_checked = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)
    category = Column(String(50), default="general")  # general, plot, character, style, grammar
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# Default checklist items per category
DEFAULT_CHECKLIST = [
    ("plot", "Does the chapter advance the main plot?"),
    ("plot", "Is there a clear conflict or tension?"),
    ("plot", "Does the chapter end with a hook or cliffhanger?"),
    ("character", "Are character motivations clear?"),
    ("character", "Do characters speak with distinct voices?"),
    ("character", "Are character arcs progressing?"),
    ("style", "Show, don't tell — are emotions shown through action?"),
    ("style", "Is the pacing appropriate (not too fast/slow)?"),
    ("style", "Are descriptions vivid but not overlong?"),
    ("grammar", "Spelling and grammar checked?"),
    ("grammar", "No repeated words or phrases?"),
    ("grammar", "Dialogue punctuation correct?"),
    ("general", "Does the chapter fit the timeline?"),
    ("general", "Are world-building details consistent?"),
    ("general", "Ready for beta reader review?"),
]


def get_checklist(chapter_id: str) -> list[ChapterChecklist]:
    """Get all checklist items for a chapter. Seeds defaults if none exist."""
    with read_session() as s:
        items = list(s.scalars(
            s.query(ChapterChecklist).filter_by(chapter_id=chapter_id)
            .order_by(ChapterChecklist.sort_order.asc())
        ).all()) if hasattr(s.query(ChapterChecklist), 'scalars') else []
        # Fallback for older SQLAlchemy
        if not items:
            items = list(s.query(ChapterChecklist).filter_by(chapter_id=chapter_id)
                         .order_by(ChapterChecklist.sort_order.asc()).all())
        if not items:
            # Seed defaults
            s.close()
            _seed_defaults(chapter_id)
            with read_session() as s2:
                items = list(s2.query(ChapterChecklist).filter_by(chapter_id=chapter_id)
                             .order_by(ChapterChecklist.sort_order.asc()).all())
        return items


def _seed_defaults(chapter_id: str) -> None:
    """Seed default checklist items for a chapter."""
    with write_transaction() as s:
        for idx, (cat, text) in enumerate(DEFAULT_CHECKLIST):
            s.add(ChapterChecklist(
                id=new_uuid(),
                chapter_id=chapter_id,
                item_text=text,
                is_checked=False,
                sort_order=idx,
                category=cat,
            ))


def add_item(chapter_id: str, text: str, category: str = "general") -> ChapterChecklist:
    if not text or len(text) > 500:
        from core.errors import ValidationError
        raise ValidationError("Checklist item text required, ≤ 500 chars.")
    with write_transaction() as s:
        max_order = s.query(ChapterChecklist).filter_by(chapter_id=chapter_id).count()
        item = ChapterChecklist(
            id=new_uuid(), chapter_id=chapter_id,
            item_text=text, is_checked=False,
            sort_order=max_order, category=category,
        )
        s.add(item)
        s.flush()
        return item


def toggle_item(item_id: str) -> bool:
    """Toggle checked state. Returns new state."""
    with read_session() as s:
        item = s.get(ChapterChecklist, item_id)
        current = bool(item.is_checked) if item else False
    with write_transaction() as s:
        item = s.get(ChapterChecklist, item_id)
        if item:
            item.is_checked = not item.is_checked
            s.flush()
            return bool(item.is_checked)
    return current


def delete_item(item_id: str) -> None:
    with write_transaction() as s:
        item = s.get(ChapterChecklist, item_id)
        if item:
            s.delete(item)


def get_progress(chapter_id: str) -> dict:
    """Return {total, checked, pct, by_category}."""
    items = get_checklist(chapter_id)
    total = len(items)
    checked = sum(1 for i in items if i.is_checked)
    by_cat: dict[str, dict] = {}
    for item in items:
        cat = item.category or "general"
        if cat not in by_cat:
            by_cat[cat] = {"total": 0, "checked": 0}
        by_cat[cat]["total"] += 1
        if item.is_checked:
            by_cat[cat]["checked"] += 1
    return {
        "total": total,
        "checked": checked,
        "pct": int(checked / total * 100) if total > 0 else 0,
        "by_category": by_cat,
    }
