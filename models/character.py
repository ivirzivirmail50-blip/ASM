"""Characters, groups, relationships, arcs."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Boolean

from models import Base


class Character(Base):
    __tablename__ = "characters"

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id"), default="default", index=True)
    name = Column(String(200), nullable=False, index=True)
    age = Column(String(40))
    gender = Column(String(40))
    aliases = Column(Text)  # JSON array
    role = Column(String(40), index=True)  # protagonist/antagonist/supporting/minor
    avatar_color = Column(String(20))
    avatar_path = Column(Text)
    physical = Column(Text)
    psychology = Column(Text)
    background = Column(Text)
    philosophy = Column(Text)
    philosophy_quotes = Column(Text)  # JSON array
    story_role = Column(Text)
    story_role_chapters = Column(Text)  # JSON array
    voice = Column(Text)
    notes = Column(Text)
    # Graph layout position (saved on drag).
    graph_x = Column(Integer)
    graph_y = Column(Integer)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class CharacterGroup(Base):
    __tablename__ = "character_groups"

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id"), default="default", index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    color = Column(String(20))


class CharacterGroupMember(Base):
    __tablename__ = "character_group_members"

    id = Column(String, primary_key=True)
    character_id = Column(String, ForeignKey("characters.id"), index=True)
    group_id = Column(String, ForeignKey("character_groups.id"), index=True)


class CharacterRelationship(Base):
    __tablename__ = "character_relationships"

    id = Column(String, primary_key=True)
    # No FK constraint — allows group IDs (g-<id>) as well as character IDs
    from_character_id = Column(String, index=True)
    to_character_id = Column(String, index=True)
    relationship_type = Column(String(60), index=True)
    description = Column(Text)
    is_bidirectional = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CharacterArc(Base):
    __tablename__ = "character_arcs"

    id = Column(String, primary_key=True)
    character_id = Column(String, ForeignKey("characters.id"), index=True)
    arc_name = Column(String(200), nullable=False)
    description = Column(Text)
    stages = Column(Text)  # JSON array of {name, description, status, chapter_ids}
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
