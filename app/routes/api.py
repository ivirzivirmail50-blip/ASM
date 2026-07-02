from flask import Blueprint, request, jsonify
from app import db
from app.models.story import Story, Chapter, Character, Scene, TimelineEvent, WorldElement, KanbanCard
import json

api_bp = Blueprint('api', __name__)


# Story endpoints
@api_bp.route('/stories', methods=['GET'])
def get_stories():
    stories = Story.query.order_by(Story.updated_at.desc()).all()
    return jsonify([s.to_dict() for s in stories])

@api_bp.route('/stories', methods=['POST'])
def create_story():
    data = request.json
    story = Story(
        title=data.get('title'),
        summary=data.get('summary'),
        content=data.get('content'),
        genre=data.get('genre'),
        status=data.get('status', 'draft')
    )
    db.session.add(story)
    db.session.commit()
    return jsonify(story.to_dict()), 201

@api_bp.route('/stories/<int:story_id>', methods=['GET'])
def get_story(story_id):
    story = Story.query.get_or_404(story_id)
    return jsonify(story.to_dict())

@api_bp.route('/stories/<int:story_id>', methods=['PUT'])
def update_story(story_id):
    story = Story.query.get_or_404(story_id)
    data = request.json
    story.title = data.get('title', story.title)
    story.summary = data.get('summary', story.summary)
    story.content = data.get('content', story.content)
    story.genre = data.get('genre', story.genre)
    story.status = data.get('status', story.status)
    db.session.commit()
    return jsonify(story.to_dict())

@api_bp.route('/stories/<int:story_id>', methods=['DELETE'])
def delete_story(story_id):
    story = Story.query.get_or_404(story_id)
    db.session.delete(story)
    db.session.commit()
    return '', 204


# Chapter endpoints
@api_bp.route('/stories/<int:story_id>/chapters', methods=['GET'])
def get_chapters(story_id):
    chapters = Chapter.query.filter_by(story_id=story_id).order_by(Chapter.chapter_number).all()
    return jsonify([c.to_dict() for c in chapters])

@api_bp.route('/chapters', methods=['POST'])
def create_chapter():
    data = request.json
    chapter = Chapter(
        story_id=data.get('story_id'),
        title=data.get('title'),
        content=data.get('content'),
        chapter_number=data.get('chapter_number'),
        status=data.get('status', 'draft'),
        notes=data.get('notes')
    )
    db.session.add(chapter)
    db.session.commit()
    return jsonify(chapter.to_dict()), 201

@api_bp.route('/chapters/<int:chapter_id>', methods=['PUT'])
def update_chapter(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    data = request.json
    chapter.title = data.get('title', chapter.title)
    chapter.content = data.get('content', chapter.content)
    chapter.status = data.get('status', chapter.status)
    chapter.notes = data.get('notes', chapter.notes)
    db.session.commit()
    return jsonify(chapter.to_dict())

@api_bp.route('/chapters/<int:chapter_id>', methods=['DELETE'])
def delete_chapter(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    db.session.delete(chapter)
    db.session.commit()
    return '', 204


# Character endpoints
@api_bp.route('/stories/<int:story_id>/characters', methods=['GET'])
def get_characters(story_id):
    characters = Character.query.filter_by(story_id=story_id).all()
    return jsonify([c.to_dict() for c in characters])

@api_bp.route('/characters', methods=['POST'])
def create_character():
    data = request.json
    character = Character(
        story_id=data.get('story_id'),
        name=data.get('name'),
        description=data.get('description'),
        role=data.get('role'),
        traits=json.dumps(data.get('traits', [])),
        background=data.get('background'),
        motivations=data.get('motivations')
    )
    db.session.add(character)
    db.session.commit()
    return jsonify(character.to_dict()), 201

@api_bp.route('/characters/<int:character_id>', methods=['PUT'])
def update_character(character_id):
    character = Character.query.get_or_404(character_id)
    data = request.json
    character.name = data.get('name', character.name)
    character.description = data.get('description', character.description)
    character.role = data.get('role', character.role)
    character.traits = json.dumps(data.get('traits', []))
    character.background = data.get('background', character.background)
    character.motivations = data.get('motivations', character.motivations)
    db.session.commit()
    return jsonify(character.to_dict())

@api_bp.route('/characters/<int:character_id>', methods=['DELETE'])
def delete_character(character_id):
    character = Character.query.get_or_404(character_id)
    db.session.delete(character)
    db.session.commit()
    return '', 204


# Kanban endpoints
@api_bp.route('/stories/<int:story_id>/kanban', methods=['GET'])
def get_kanban(story_id):
    cards = KanbanCard.query.filter_by(story_id=story_id).order_by(KanbanCard.card_order).all()
    return jsonify([c.to_dict() for c in cards])

@api_bp.route('/kanban', methods=['POST'])
def create_kanban_card():
    data = request.json
    card = KanbanCard(
        story_id=data.get('story_id'),
        title=data.get('title'),
        description=data.get('description'),
        column=data.get('column', 'todo'),
        priority=data.get('priority', 'medium'),
        card_order=data.get('card_order', 0),
        assigned_character=data.get('assigned_character'),
        due_date=data.get('due_date')
    )
    db.session.add(card)
    db.session.commit()
    return jsonify(card.to_dict()), 201

@api_bp.route('/kanban/<int:card_id>', methods=['PUT'])
def update_kanban_card(card_id):
    card = KanbanCard.query.get_or_404(card_id)
    data = request.json
    card.title = data.get('title', card.title)
    card.description = data.get('description', card.description)
    card.column = data.get('column', card.column)
    card.priority = data.get('priority', card.priority)
    card.card_order = data.get('card_order', card.card_order)
    card.assigned_character = data.get('assigned_character', card.assigned_character)
    card.due_date = data.get('due_date', card.due_date)
    db.session.commit()
    return jsonify(card.to_dict())

@api_bp.route('/kanban/<int:card_id>', methods=['DELETE'])
def delete_kanban_card(card_id):
    card = KanbanCard.query.get_or_404(card_id)
    db.session.delete(card)
    db.session.commit()
    return '', 204


# Timeline endpoints
@api_bp.route('/stories/<int:story_id>/timeline', methods=['GET'])
def get_timeline(story_id):
    events = TimelineEvent.query.filter_by(story_id=story_id).order_by(TimelineEvent.event_order).all()
    return jsonify([e.to_dict() for e in events])

@api_bp.route('/timeline', methods=['POST'])
def create_timeline_event():
    data = request.json
    event = TimelineEvent(
        story_id=data.get('story_id'),
        title=data.get('title'),
        description=data.get('description'),
        event_date=data.get('event_date'),
        event_order=data.get('event_order')
    )
    db.session.add(event)
    db.session.commit()
    return jsonify(event.to_dict()), 201

@api_bp.route('/timeline/<int:event_id>', methods=['PUT'])
def update_timeline_event(event_id):
    event = TimelineEvent.query.get_or_404(event_id)
    data = request.json
    event.title = data.get('title', event.title)
    event.description = data.get('description', event.description)
    event.event_date = data.get('event_date', event.event_date)
    event.event_order = data.get('event_order', event.event_order)
    db.session.commit()
    return jsonify(event.to_dict())

@api_bp.route('/timeline/<int:event_id>', methods=['DELETE'])
def delete_timeline_event(event_id):
    event = TimelineEvent.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    return '', 204


# World Building endpoints
@api_bp.route('/stories/<int:story_id>/world', methods=['GET'])
def get_world_elements(story_id):
    elements = WorldElement.query.filter_by(story_id=story_id).all()
    return jsonify([e.to_dict() for e in elements])

@api_bp.route('/world', methods=['POST'])
def create_world_element():
    data = request.json
    element = WorldElement(
        story_id=data.get('story_id'),
        name=data.get('name'),
        element_type=data.get('element_type'),
        description=data.get('description'),
        details=json.dumps(data.get('details', {})),
        parent_id=data.get('parent_id')
    )
    db.session.add(element)
    db.session.commit()
    return jsonify(element.to_dict()), 201

@api_bp.route('/world/<int:element_id>', methods=['PUT'])
def update_world_element(element_id):
    element = WorldElement.query.get_or_404(element_id)
    data = request.json
    element.name = data.get('name', element.name)
    element.element_type = data.get('element_type', element.element_type)
    element.description = data.get('description', element.description)
    element.details = json.dumps(data.get('details', {}))
    element.parent_id = data.get('parent_id', element.parent_id)
    db.session.commit()
    return jsonify(element.to_dict())

@api_bp.route('/world/<int:element_id>', methods=['DELETE'])
def delete_world_element(element_id):
    element = WorldElement.query.get_or_404(element_id)
    db.session.delete(element)
    db.session.commit()
    return '', 204


# Search endpoint
@api_bp.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    
    results = Story.query.filter(
        db.or_(
            Story.title.ilike(f'%{query}%'),
            Story.summary.ilike(f'%{query}%'),
            Story.content.ilike(f'%{query}%')
        )
    ).all()
    
    return jsonify([r.to_dict() for r in results])


# Dashboard stats
@api_bp.route('/stats', methods=['GET'])
def get_stats():
    total_stories = Story.query.count()
    total_chapters = Chapter.query.count()
    total_characters = Character.query.count()
    
    stories_by_status = db.session.query(
        Story.status, db.func.count(Story.id)
    ).group_by(Story.status).all()
    
    return jsonify({
        'total_stories': total_stories,
        'total_chapters': total_chapters,
        'total_characters': total_characters,
        'stories_by_status': dict(stories_by_status)
    })
