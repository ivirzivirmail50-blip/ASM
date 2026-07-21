"""Note model — quick-capture items for the Notes & Ideas Inbox."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from models import Base


class Note(Base):
    __tablename__ = "notes"

    id = Column(String, primary_key=True)
    project_id = Column(String, default="default", index=True)
    title = Column(String(500))
    body = Column(Text)
    category = Column(String(40), default="idea", index=True)
    tags = Column(Text)                       # JSON array
    pinned = Column(Integer, default=0)
    done = Column(Integer, default=0)         # for todos
    # Cross-reference links (JSON array of {entity_type, entity_id, entity_title})
    links = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
