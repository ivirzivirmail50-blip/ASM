"""ChapterDependency model — chapter-to-chapter dependency edges."""
from __future__ import annotations

from sqlalchemy import Column, ForeignKey, String

from models import Base


class ChapterDependency(Base):
    """A dependency: from_chapter depends on to_chapter (to must come first)."""
    __tablename__ = "chapter_dependencies"

    id = Column(String, primary_key=True)
    project_id = Column(String, default="default", index=True)
    from_chapter_id = Column(String, ForeignKey("chapters.id"), nullable=False, index=True)
    to_chapter_id = Column(String, ForeignKey("chapters.id"), nullable=False, index=True)
