"""SQLAlchemy models for Absolute Story Manager v4.0."""

import uuid
from datetime import datetime
from sqlalchemy import Text, Integer, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app import db


def generate_uuid() -> str:
    """Generate a UUID string."""
    return str(uuid.uuid4())


class Project(db.Model):
    """Root project table for future multi-book support."""
    __tablename__ = 'projects'
    
    id: Mapped[str] = mapped_column(Text, primary_key=True, default='default')
    name: Mapped[str] = mapped_column(Text, nullable=False, default="My Story")
    subtitle: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    
    # Relationships
    chapters = relationship('Chapter', back_populates='project', cascade='all, delete-orphan')
    characters = relationship('Character', back_populates='project', cascade='all, delete-orphan')
    plans = relationship('Plan', back_populates='project', cascade='all, delete-orphan')
    world_entries = relationship('WorldEntry', back_populates='project', cascade='all, delete-orphan')
    activity_logs = relationship('ActivityLog', back_populates='project', cascade='all, delete-orphan')
    character_groups = relationship('CharacterGroup', back_populates='project', cascade='all, delete-orphan')


class Chapter(db.Model):
    """Chapter model with versioning support."""
    __tablename__ = 'chapters'
    
    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), default='default')
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text, default="")
    synopsis: Mapped[str | None] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, default='draft')  # draft, revised, final
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    target_word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    character_ids: Mapped[str | None] = mapped_column(Text, default="[]")  # JSON array
    tags: Mapped[str | None] = mapped_column(Text, default="[]")  # JSON array
    raw_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship('Project', back_populates='chapters')
    versions = relationship('ChapterVersion', back_populates='chapter', cascade='all, delete-orphan', order_by='ChapterVersion.version_number')
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'project_id': self.project_id,
            'title': self.title,
            'content': self.content,
            'synopsis': self.synopsis,
            'status': self.status,
            'word_count': self.word_count,
            'target_word_count': self.target_word_count,
            'sort_order': self.sort_order,
            'character_ids': self.character_ids,
            'tags': self.tags,
            'raw_file_path': self.raw_file_path,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'version_count': len(self.versions)
        }


class ChapterVersion(db.Model):
    """Version history for chapters."""
    __tablename__ = 'chapter_versions'
    
    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    chapter_id: Mapped[str] = mapped_column(ForeignKey('chapters.id'))
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(Text, default='manual')  # manual, reupload, status_change, split, merge
    uploaded_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Relationships
    chapter = relationship('Chapter', back_populates='versions')
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'chapter_id': self.chapter_id,
            'version_number': self.version_number,
            'content': self.content,
            'word_count': self.word_count,
            'source': self.source,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
            'notes': self.notes
        }


class Character(db.Model):
    """Character model with rich profile fields."""
    __tablename__ = 'characters'
    
    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), default='default')
    name: Mapped[str] = mapped_column(Text, nullable=False)
    age: Mapped[str | None] = mapped_column(Text, nullable=True)
    gender: Mapped[str | None] = mapped_column(Text, nullable=True)
    aliases: Mapped[str | None] = mapped_column(Text, default="[]")  # JSON array
    role: Mapped[str] = mapped_column(Text, default='supporting')  # protagonist, antagonist, supporting, minor
    avatar_color: Mapped[str | None] = mapped_column(Text, default="#6366f1")
    avatar_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    physical: Mapped[str | None] = mapped_column(Text, default="")
    psychology: Mapped[str | None] = mapped_column(Text, default="")
    background: Mapped[str | None] = mapped_column(Text, default="")
    philosophy: Mapped[str | None] = mapped_column(Text, default="")
    philosophy_quotes: Mapped[str | None] = mapped_column(Text, default="[]")  # JSON array
    story_role: Mapped[str | None] = mapped_column(Text, default="")
    story_role_chapters: Mapped[str | None] = mapped_column(Text, default="[]")  # JSON array
    voice: Mapped[str | None] = mapped_column(Text, default="")
    notes: Mapped[str | None] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship('Project', back_populates='characters')
    groups = relationship('CharacterGroupMember', back_populates='character', cascade='all, delete-orphan')
    relationships_from = relationship('CharacterRelationship', foreign_keys='CharacterRelationship.from_character_id', back_populates='from_character', cascade='all, delete-orphan')
    relationships_to = relationship('CharacterRelationship', foreign_keys='CharacterRelationship.to_character_id', back_populates='to_character', cascade='all, delete-orphan')
    arcs = relationship('CharacterArc', back_populates='character', cascade='all, delete-orphan')
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'project_id': self.project_id,
            'name': self.name,
            'age': self.age,
            'gender': self.gender,
            'aliases': self.aliases,
            'role': self.role,
            'avatar_color': self.avatar_color,
            'avatar_path': self.avatar_path,
            'physical': self.physical,
            'psychology': self.psychology,
            'background': self.background,
            'philosophy': self.philosophy,
            'philosophy_quotes': self.philosophy_quotes,
            'story_role': self.story_role,
            'story_role_chapters': self.story_role_chapters,
            'voice': self.voice,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class CharacterGroup(db.Model):
    """Character groups for categorization."""
    __tablename__ = 'character_groups'
    
    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), default='default')
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, default="")
    color: Mapped[str | None] = mapped_column(Text, default="#6366f1")
    
    # Relationships
    project = relationship('Project', back_populates='character_groups')
    members = relationship('CharacterGroupMember', back_populates='group', cascade='all, delete-orphan')
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'project_id': self.project_id,
            'name': self.name,
            'description': self.description,
            'color': self.color
        }


class CharacterGroupMember(db.Model):
    """Junction table for character-group membership."""
    __tablename__ = 'character_group_members'
    
    character_id: Mapped[str] = mapped_column(ForeignKey('characters.id'), primary_key=True)
    group_id: Mapped[str] = mapped_column(ForeignKey('character_groups.id'), primary_key=True)
    
    # Relationships
    character = relationship('Character', back_populates='groups')
    group = relationship('CharacterGroup', back_populates='members')


class CharacterRelationship(db.Model):
    """Relationships between characters."""
    __tablename__ = 'character_relationships'
    
    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    from_character_id: Mapped[str] = mapped_column(ForeignKey('characters.id'))
    to_character_id: Mapped[str] = mapped_column(ForeignKey('characters.id'))
    relationship_type: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, default="")
    is_bidirectional: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    
    # Relationships
    from_character = relationship('Character', foreign_keys=[from_character_id], back_populates='relationships_from')
    to_character = relationship('Character', foreign_keys=[to_character_id], back_populates='relationships_to')
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'from_character_id': self.from_character_id,
            'to_character_id': self.to_character_id,
            'relationship_type': self.relationship_type,
            'description': self.description,
            'is_bidirectional': self.is_bidirectional,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class CharacterArc(db.Model):
    """Character arc tracking with stages."""
    __tablename__ = 'character_arcs'
    
    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    character_id: Mapped[str] = mapped_column(ForeignKey('characters.id'))
    arc_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, default="")
    stages: Mapped[str | None] = mapped_column(Text, default="[]")  # JSON array
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    
    # Relationships
    character = relationship('Character', back_populates='arcs')
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'character_id': self.character_id,
            'arc_name': self.arc_name,
            'description': self.description,
            'stages': self.stages,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Plan(db.Model):
    """Story planning items for Kanban, timeline, and outline."""
    __tablename__ = 'plans'
    
    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), default='default')
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, default='idea')  # idea, planned, writing, draft_done, revised, final
    column: Mapped[str] = mapped_column(Text, default='idea')  # For Kanban positioning
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    chapter_id: Mapped[str | None] = mapped_column(ForeignKey('chapters.id'), nullable=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey('plans.id'), nullable=True)
    depends_on_id: Mapped[str | None] = mapped_column(ForeignKey('plans.id'), nullable=True)
    story_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_type: Mapped[str | None] = mapped_column(Text, default='plot_point')
    track: Mapped[str | None] = mapped_column(Text, nullable=True)
    characters_involved: Mapped[str | None] = mapped_column(Text, default="[]")  # JSON array
    deadline: Mapped[str | None] = mapped_column(Text, nullable=True)
    effort_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, default="[]")  # JSON array
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship('Project', back_populates='plans')
    subtasks = relationship('PlanSubtask', back_populates='plan', cascade='all, delete-orphan')
    children = relationship('Plan', remote_side=[parent_id], backref='parent')
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'project_id': self.project_id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'column': self.column,
            'sort_order': self.sort_order,
            'chapter_id': self.chapter_id,
            'parent_id': self.parent_id,
            'depends_on_id': self.depends_on_id,
            'story_date': self.story_date,
            'event_type': self.event_type,
            'track': self.track,
            'characters_involved': self.characters_involved,
            'deadline': self.deadline,
            'effort_estimate': self.effort_estimate,
            'tags': self.tags,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class PlanSubtask(db.Model):
    """Subtasks for plan items."""
    __tablename__ = 'plan_subtasks'
    
    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    plan_id: Mapped[str] = mapped_column(ForeignKey('plans.id'))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    
    # Relationships
    plan = relationship('Plan', back_populates='subtasks')
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'plan_id': self.plan_id,
            'title': self.title,
            'is_completed': self.is_completed,
            'sort_order': self.sort_order,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class WorldEntry(db.Model):
    """World building entries (locations, lore, factions, etc.)."""
    __tablename__ = 'world_entries'
    
    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), default='default')
    type: Mapped[str] = mapped_column(Text, nullable=False)  # location, lore, faction, glossary, magic_system, species, culture, technology
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, default="")
    content: Mapped[str | None] = mapped_column(Text, default="")
    notes: Mapped[str | None] = mapped_column(Text, default="")
    metadata: Mapped[str | None] = mapped_column(Text, default="{}")  # JSON object
    parent_id: Mapped[str | None] = mapped_column(ForeignKey('world_entries.id'), nullable=True)
    map_pin_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    map_pin_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    map_pin_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship('Project', back_populates='world_entries')
    versions = relationship('WorldEntryVersion', back_populates='entry', cascade='all, delete-orphan')
    children = relationship('WorldEntry', remote_side=[parent_id], backref='parent')
    relations_from = relationship('WorldEntryRelation', foreign_keys='WorldEntryRelation.from_entry_id', back_populates='from_entry', cascade='all, delete-orphan')
    relations_to = relationship('WorldEntryRelation', foreign_keys='WorldEntryRelation.to_entry_id', back_populates='to_entry', cascade='all, delete-orphan')
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'project_id': self.project_id,
            'type': self.type,
            'name': self.name,
            'category': self.category,
            'description': self.description,
            'content': self.content,
            'notes': self.notes,
            'metadata': self.metadata,
            'parent_id': self.parent_id,
            'map_pin_x': self.map_pin_x,
            'map_pin_y': self.map_pin_y,
            'map_pin_label': self.map_pin_label,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class WorldEntryVersion(db.Model):
    """Version history for world entries."""
    __tablename__ = 'world_entry_versions'
    
    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    entry_id: Mapped[str] = mapped_column(ForeignKey('world_entries.id'))
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[str] = mapped_column(Text, nullable=False)  # JSON snapshot
    source: Mapped[str] = mapped_column(Text, default='manual')
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Relationships
    entry = relationship('WorldEntry', back_populates='versions')
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'entry_id': self.entry_id,
            'version_number': self.version_number,
            'snapshot': self.snapshot,
            'source': self.source,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'notes': self.notes
        }


class WorldEntryRelation(db.Model):
    """Relations between world entries."""
    __tablename__ = 'world_entry_relations'
    
    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_uuid)
    from_entry_id: Mapped[str] = mapped_column(ForeignKey('world_entries.id'))
    to_entry_id: Mapped[str] = mapped_column(ForeignKey('world_entries.id'))
    relation_type: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, default="")
    
    # Relationships
    from_entry = relationship('WorldEntry', foreign_keys=[from_entry_id], back_populates='relations_from')
    to_entry = relationship('WorldEntry', foreign_keys=[to_entry_id], back_populates='relations_to')
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'from_entry_id': self.from_entry_id,
            'to_entry_id': self.to_entry_id,
            'relation_type': self.relation_type,
            'description': self.description
        }


class ActivityLog(db.Model):
    """Activity logging for stats, streaks, and audit trail."""
    __tablename__ = 'activity_log'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), default='default')
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)  # chapter, character, plan, world_entry, ai_action
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    entity_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)  # created, updated, deleted, uploaded, reordered, status_changed
    word_count_delta: Mapped[int] = mapped_column(Integer, default=0)
    details: Mapped[str | None] = mapped_column(Text, default="{}")  # JSON object
    timestamp: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    
    # Relationships
    project = relationship('Project', back_populates='activity_logs')
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'project_id': self.project_id,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'entity_title': self.entity_title,
            'action': self.action,
            'word_count_delta': self.word_count_delta,
            'details': self.details,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }


class Settings(db.Model):
    """Application settings stored as key-value pairs."""
    __tablename__ = 'settings'
    
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-encoded
    
    def to_dict(self) -> dict:
        return {'key': self.key, 'value': self.value}
