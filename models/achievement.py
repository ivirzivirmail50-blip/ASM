"""UnlockedAchievement model — persisted record of unlocked achievements."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text

from models import Base


class UnlockedAchievement(Base):
    """A persisted record of an achievement the writer has unlocked."""
    __tablename__ = "unlocked_achievements"

    id = Column(String, primary_key=True)
    project_id = Column(String, default="default", index=True)
    achievement_key = Column(String(80), nullable=False, index=True)
    unlocked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    context = Column(Text)  # JSON: extra info (e.g. {"streak": 7})
