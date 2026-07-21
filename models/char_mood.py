"""CharacterMood model — character emotional state per chapter."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text

from models import Base


class CharacterMood(Base):
    """A character's mood in a specific chapter."""
    __tablename__ = "character_moods"

    id = Column(String, primary_key=True)
    project_id = Column(String, default="default", index=True)
    character_id = Column(String, ForeignKey("characters.id"), nullable=False, index=True)
    chapter_id = Column(String, ForeignKey("chapters.id"), nullable=False, index=True)
    mood = Column(String(30), nullable=False)
    intensity = Column(String(10), default="medium")  # low/medium/high
    note = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
