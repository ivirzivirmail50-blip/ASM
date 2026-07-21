"""Snippets & chapter templates service — reusable text blocks."""
from __future__ import annotations

import json
import logging

from sqlalchemy import Column, DateTime, Integer, String, Text
from datetime import datetime, timezone

from models import Base
from core.db import read_session, write_transaction
from services._common import new_uuid, now_utc

log = logging.getLogger("asm.snippets")


class Snippet(Base):
    """Reusable text block or chapter template."""
    __tablename__ = "snippets"

    id = Column(String, primary_key=True)
    project_id = Column(String, default="default", index=True)
    name = Column(String(200), nullable=False)
    category = Column(String(50))  # snippet / template
    content = Column(Text)
    tags = Column(Text)  # JSON array
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def list_snippets(category: str | None = None) -> list[Snippet]:
    with read_session() as s:
        from services._common import current_project_id
        pid = current_project_id(s)
        q = s.query(Snippet).filter_by(project_id=pid)
        if category:
            q = q.filter_by(category=category)
        return list(q.order_by(Snippet.name.asc()).all())


def get_snippet(snippet_id: str) -> Snippet:
    with read_session() as s:
        snip = s.get(Snippet, snippet_id)
        if not snip:
            from core.errors import NotFoundError
            raise NotFoundError("Snippet not found.")
        return snip


def create_snippet(name: str, content: str, *, category: str = "snippet",
                   tags: list[str] | None = None) -> Snippet:
    if not name or len(name) > 200:
        from core.errors import ValidationError
        raise ValidationError("Name required, ≤ 200 chars.")
    sid = new_uuid()
    with write_transaction() as s:
        from services._common import current_project_id
        snip = Snippet(
            id=sid, project_id=current_project_id(s),
            name=name, category=category, content=content,
            tags=json.dumps(tags or []),
        )
        s.add(snip)
        s.flush()
        return snip


def update_snippet(snippet_id: str, **fields) -> Snippet:
    with write_transaction() as s:
        snip = s.get(Snippet, snippet_id)
        if not snip:
            from core.errors import NotFoundError
            raise NotFoundError("Snippet not found.")
        for k in ("name", "content", "category"):
            if k in fields and fields[k] is not None:
                setattr(snip, k, fields[k])
        if "tags" in fields:
            snip.tags = json.dumps(fields["tags"] or [])
        snip.updated_at = now_utc()
        s.flush()
        return snip


def delete_snippet(snippet_id: str) -> None:
    with write_transaction() as s:
        snip = s.get(Snippet, snippet_id)
        if snip:
            s.delete(snip)


# Default chapter templates
DEFAULT_TEMPLATES = [
    {
        "name": "Standard Chapter",
        "category": "template",
        "content": "# Chapter Title\n\n## Scene 1\n\nThe first paragraph sets the scene...\n\n## Scene 2\n\nThe second scene develops the conflict...\n\n## Scene 3\n\nThe resolution...\n",
    },
    {
        "name": "Action Scene",
        "category": "template",
        "content": "# Chapter Title\n\nThe air crackled with tension. Every muscle in Elara's body coiled like a spring.\n\n\"Ready?\" Kael whispered.\n\nShe nodded. There was no time for words.\n\n",
    },
    {
        "name": "Dialogue Heavy",
        "category": "template",
        "content": "# Chapter Title\n\n\"You can't be serious,\" Elara said.\n\n\"I've never been more serious,\" Malachar replied, his voice like gravel.\n\n\"And if I refuse?\"\n\n\"Then we both lose everything.\"\n\n",
    },
    {
        "name": "Flashback",
        "category": "template",
        "content": "# Chapter Title\n\n*Five years ago...*\n\nThe memory surfaced unbidden, sharp as broken glass.\n\n",
    },
    {
        "name": "Chapter Ending (Cliffhanger)",
        "category": "template",
        "content": "# Chapter Title\n\n...and then she saw it. The one thing she had prayed she would never see again.\n\nThe door began to open.\n\n",
    },
]


def seed_default_templates() -> None:
    """Seed default chapter templates if none exist."""
    existing = list_snippets(category="template")
    if existing:
        return
    for t in DEFAULT_TEMPLATES:
        create_snippet(t["name"], t["content"], category="template")
    log.info("Seeded %d default chapter templates", len(DEFAULT_TEMPLATES))
