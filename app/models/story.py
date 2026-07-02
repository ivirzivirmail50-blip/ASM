from datetime import datetime
from app import db

class Story(db.Model):
    __tablename__ = 'story'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.Text)
    content = db.Column(db.Text)
    genre = db.Column(db.String(100))
    status = db.Column(db.String(50), default='draft')  # draft, writing, complete
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    chapters = db.relationship('Chapter', backref='story', lazy=True, cascade='all, delete-orphan')
    characters = db.relationship('Character', backref='story', lazy=True, cascade='all, delete-orphan')
    scenes = db.relationship('Scene', backref='story', lazy=True, cascade='all, delete-orphan')
    timeline_events = db.relationship('TimelineEvent', backref='story', lazy=True, cascade='all, delete-orphan')
    world_elements = db.relationship('WorldElement', backref='story', lazy=True, cascade='all, delete-orphan')
    kanban_cards = db.relationship('KanbanCard', backref='story', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'summary': self.summary,
            'content': self.content,
            'genre': self.genre,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Chapter(db.Model):
    __tablename__ = 'chapter'
    
    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('story.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    chapter_number = db.Column(db.Integer)
    word_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), default='draft')  # draft, writing, complete
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'story_id': self.story_id,
            'title': self.title,
            'content': self.content,
            'chapter_number': self.chapter_number,
            'word_count': self.word_count,
            'status': self.status,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Character(db.Model):
    __tablename__ = 'character'
    
    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('story.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    role = db.Column(db.String(100))  # protagonist, antagonist, supporting, etc.
    traits = db.Column(db.Text)  # JSON array of traits
    background = db.Column(db.Text)
    motivations = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'story_id': self.story_id,
            'name': self.name,
            'description': self.description,
            'role': self.role,
            'traits': self.traits,
            'background': self.background,
            'motivations': self.motivations,
            'image_url': self.image_url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Scene(db.Model):
    __tablename__ = 'scene'
    
    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('story.id'), nullable=False)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapter.id'))
    title = db.Column(db.String(200))
    location = db.Column(db.String(200))
    characters_involved = db.Column(db.Text)  # JSON array of character IDs
    description = db.Column(db.Text)
    scene_order = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    chapter = db.relationship('Chapter', backref='scenes')
    
    def to_dict(self):
        return {
            'id': self.id,
            'story_id': self.story_id,
            'chapter_id': self.chapter_id,
            'title': self.title,
            'location': self.location,
            'characters_involved': self.characters_involved,
            'description': self.description,
            'scene_order': self.scene_order,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class TimelineEvent(db.Model):
    __tablename__ = 'timeline_event'
    
    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('story.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    event_date = db.Column(db.String(100))  # Can be relative or absolute
    event_order = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'story_id': self.story_id,
            'title': self.title,
            'description': self.description,
            'event_date': self.event_date,
            'event_order': self.event_order,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class WorldElement(db.Model):
    __tablename__ = 'world_element'
    
    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('story.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    element_type = db.Column(db.String(50))  # location, culture, magic_system, technology, etc.
    description = db.Column(db.Text)
    details = db.Column(db.Text)  # JSON for structured data
    parent_id = db.Column(db.Integer, db.ForeignKey('world_element.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    children = db.relationship('WorldElement', backref=db.backref('parent', remote_side=[id]))
    
    def to_dict(self):
        return {
            'id': self.id,
            'story_id': self.story_id,
            'name': self.name,
            'element_type': self.element_type,
            'description': self.description,
            'details': self.details,
            'parent_id': self.parent_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class KanbanCard(db.Model):
    __tablename__ = 'kanban_card'
    
    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('story.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    column = db.Column(db.String(50), default='todo')  # todo, in_progress, review, done
    priority = db.Column(db.String(20), default='medium')  # low, medium, high
    card_order = db.Column(db.Integer, default=0)
    assigned_character = db.Column(db.String(100))
    due_date = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'story_id': self.story_id,
            'title': self.title,
            'description': self.description,
            'column': self.column,
            'priority': self.priority,
            'card_order': self.card_order,
            'assigned_character': self.assigned_character,
            'due_date': self.due_date,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
