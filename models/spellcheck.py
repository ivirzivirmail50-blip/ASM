"""CustomWord model — writer's custom dictionary for spell check."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String

from models import Base


class CustomWord(Base):
    """A word the writer has added to their custom dictionary."""
    __tablename__ = "custom_words"

    id = Column(String, primary_key=True)
    project_id = Column(String, default="default", index=True)
    word = Column(String(200), nullable=False, index=True)
    added_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
