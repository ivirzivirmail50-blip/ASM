"""AI action history model — stores generated names, reports, tags, dialogue, etc."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from models import Base


class AIHistory(Base):
    """Persistent log of AI-generated outputs (names, tags, dialogue, consistency reports)."""
    __tablename__ = "ai_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action_type = Column(String(50), index=True)  # name_gen, tags, dialogue, consistency, summarize, continue
    entity_type = Column(String(50))  # chapter, character, world_entry, none
    entity_id = Column(String(64))
    entity_title = Column(String(200))
    prompt_summary = Column(String(300))  # Short summary of what was asked
    response = Column(Text)  # The AI's response
    metadata_ = Column("metadata", Text)  # JSON: extra info (culture, emotion, etc.)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
