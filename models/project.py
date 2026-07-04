"""Project (multi-book root) model."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text

from models import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True)
    name = Column(String(500), nullable=False, default="My Story")
    subtitle = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Project {self.id}: {self.name}>"
