"""MilestoneCelebration model — persisted record of reached word count milestones."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from models import Base


class MilestoneCelebration(Base):
    """Persisted record that a milestone was reached (for one-time celebration)."""
    __tablename__ = "milestone_celebrations"

    id = Column(String, primary_key=True)
    project_id = Column(String, default="default", index=True)
    milestone_key = Column(String(40), nullable=False, index=True)  # e.g. "words_10k"
    threshold = Column(Integer, nullable=False)
    reached_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
