"""SavedInspiration model — bookmarked prompts and generated scenarios."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from models import Base


class SavedInspiration(Base):
    """A bookmarked prompt or generated scenario."""
    __tablename__ = "saved_inspirations"

    id = Column(String, primary_key=True)
    project_id = Column(String, default="default", index=True)
    kind = Column(String(30))              # prompt / scenario / whatif
    category = Column(String(60))          # opening / conflict / character / setting / twist / combo
    title = Column(String(300))
    body = Column(Text)                    # the actual prompt text
    meta = Column(Text)                    # JSON: extra structured data (scenario parts, etc.)
    pinned = Column(Integer, default=0)    # 0/1
    used = Column(Integer, default=0)      # 0/1 — marked as "used"
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
