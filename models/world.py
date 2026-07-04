"""World entries, versions, relations."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text

from models import Base


class WorldEntry(Base):
    __tablename__ = "world_entries"

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id"), default="default", index=True)
    type = Column(String(60), nullable=False, index=True)  # location/lore/faction/glossary/...
    name = Column(String(300), nullable=False, index=True)
    category = Column(String(100))
    description = Column(Text)
    content = Column(Text)
    notes = Column(Text)
    metadata_ = Column("metadata", Text)  # JSON
    parent_id = Column(String, ForeignKey("world_entries.id"))
    map_pin_x = Column(Float)
    map_pin_y = Column(Float)
    map_pin_label = Column(String(200))
    map_image_path = Column(Text)  # for location background
    sort_order = Column(Integer, default=0, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class WorldEntryVersion(Base):
    __tablename__ = "world_entry_versions"

    id = Column(String, primary_key=True)
    entry_id = Column(String, ForeignKey("world_entries.id"), index=True)
    version_number = Column(Integer)
    snapshot = Column(Text)  # JSON of full entry state
    source = Column(String(40))  # manual/autosave_interval/status_change
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    notes = Column(Text)


class WorldEntryRelation(Base):
    __tablename__ = "world_entry_relations"

    id = Column(String, primary_key=True)
    from_entry_id = Column(String, ForeignKey("world_entries.id"), index=True)
    to_entry_id = Column(String, ForeignKey("world_entries.id"), index=True)
    relation_type = Column(String(80))
    description = Column(Text)
