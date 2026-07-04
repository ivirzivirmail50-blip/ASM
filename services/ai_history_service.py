"""AI history service — stores and retrieves AI-generated outputs."""
from __future__ import annotations

import json
import logging

from sqlalchemy import select, desc

from core.db import read_session, write_transaction
from models.ai_history import AIHistory

log = logging.getLogger("asm.ai_history")


def save(action_type: str, response: str, *,
         entity_type: str = "", entity_id: str = "", entity_title: str = "",
         prompt_summary: str = "", metadata: dict | None = None) -> AIHistory:
    """Save an AI action result to history."""
    with write_transaction() as s:
        entry = AIHistory(
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_title=entity_title,
            prompt_summary=(prompt_summary or "")[:300],
            response=response,
            metadata_=json.dumps(metadata or {}),
        )
        s.add(entry)
        s.flush()
        return entry


def list_recent(limit: int = 50, action_type: str | None = None) -> list[AIHistory]:
    """List recent AI history entries."""
    with read_session() as s:
        q = select(AIHistory)
        if action_type:
            q = q.where(AIHistory.action_type == action_type)
        q = q.order_by(desc(AIHistory.created_at)).limit(limit)
        return list(s.scalars(q).all())


def delete(entry_id: int) -> None:
    with write_transaction() as s:
        entry = s.get(AIHistory, entry_id)
        if entry:
            s.delete(entry)


def clear_all() -> None:
    with write_transaction() as s:
        s.query(AIHistory).delete()
