"""Chapter + chapter_versions models."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from models import Base


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id"), default="default", index=True)
    title = Column(String(500), nullable=False)
    content = Column(Text)
    synopsis = Column(Text)
    status = Column(String(20), default="draft", index=True)  # draft/revised/final
    word_count = Column(Integer, default=0)
    target_word_count = Column(Integer)
    sort_order = Column(Integer, default=0, index=True)
    character_ids = Column(Text)  # JSON array
    tags = Column(Text)  # JSON array
    raw_file_path = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class ChapterVersion(Base):
    __tablename__ = "chapter_versions"

    id = Column(String, primary_key=True)
    chapter_id = Column(String, ForeignKey("chapters.id"), index=True)
    version_number = Column(Integer)
    content = Column(Text)
    word_count = Column(Integer, default=0)
    source = Column(String(40))  # manual/reupload/status_change/split/merge
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    notes = Column(Text)
