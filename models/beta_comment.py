"""Beta reader comment model — read-only annotations on chapters."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from models import Base


class BetaComment(Base):
    """A comment left by a beta reader on a chapter."""
    __tablename__ = "beta_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chapter_id = Column(String, index=True)
    reader_name = Column(String(100), default="Beta Reader")
    selected_text = Column(Text)  # The text the comment refers to
    comment = Column(Text, nullable=False)
    position = Column(Integer, default=0)  # Character offset in chapter
    status = Column(String(20), default="open")  # open / resolved
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
