"""Character Mood Tracker — track character emotional state per chapter.

Each mood entry links a character to a chapter with a mood value.
This builds a mood timeline showing how each character's emotional
state evolves across the story.

Moods: joyful / hopeful / neutral / anxious / angry / sad / afraid / determined
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from core.db import read_session, write_transaction
from core.errors import NotFoundError, ValidationError
from models.char_mood import CharacterMood
from models.chapter import Chapter
from models.character import Character
from services._common import current_project_id, new_uuid, now_utc

log = logging.getLogger("asm.char_mood")


MOODS = {
    "joyful":     {"label": "Joyful",     "icon": "😄", "color": "#fbbf24", "score": 5},
    "hopeful":    {"label": "Hopeful",    "icon": "🌅", "color": "#34d399", "score": 4},
    "neutral":    {"label": "Neutral",    "icon": "😐", "color": "#94a3b8", "score": 3},
    "determined": {"label": "Determined", "icon": "🎯", "color": "#60a5fa", "score": 4},
    "anxious":    {"label": "Anxious",    "icon": "😰", "color": "#f59e0b", "score": 2},
    "afraid":     {"label": "Afraid",     "icon": "😱", "color": "#a78bfa", "score": 1},
    "angry":      {"label": "Angry",      "icon": "😠", "color": "#ef4444", "score": 1},
    "sad":        {"label": "Sad",        "icon": "😢", "color": "#6366f1", "score": 1},
}

INTENSITIES = {
    "low":    {"label": "Low",    "icon": "·"},
    "medium": {"label": "Medium", "icon": "··"},
    "high":   {"label": "High",   "icon": "···"},
}


def list_moods(*, character_id: str | None = None, chapter_id: str | None = None) -> list[CharacterMood]:
    with read_session() as s:
        q = select(CharacterMood).where(CharacterMood.project_id == current_project_id(s))
        if character_id:
            q = q.where(CharacterMood.character_id == character_id)
        if chapter_id:
            q = q.where(CharacterMood.chapter_id == chapter_id)
        return list(s.scalars(q.order_by(CharacterMood.created_at.asc())))


def set_mood(*, character_id: str, chapter_id: str, mood: str,
             intensity: str = "medium", note: str = "") -> CharacterMood:
    if mood not in MOODS:
        raise ValidationError(f"mood must be one of {list(MOODS)}")
    if intensity not in INTENSITIES:
        raise ValidationError(f"intensity must be one of {list(INTENSITIES)}")
    with write_transaction() as s:
        ch = s.get(Character, character_id)
        if not ch:
            raise NotFoundError("Character not found.")
        chapter = s.get(Chapter, chapter_id)
        if not chapter:
            raise NotFoundError("Chapter not found.")
        # Check if mood already exists for this char+chapter — update if so
        existing = s.scalar(
            select(CharacterMood).where(
                CharacterMood.character_id == character_id,
                CharacterMood.chapter_id == chapter_id,
            )
        )
        if existing:
            existing.mood = mood
            existing.intensity = intensity
            existing.note = note
            s.flush()
            return existing
        m = CharacterMood(
            id=new_uuid(),
            project_id=current_project_id(s),
            character_id=character_id,
            chapter_id=chapter_id,
            mood=mood,
            intensity=intensity,
            note=note,
        )
        s.add(m)
        s.flush()
        return m


def delete_mood(mood_id: str) -> None:
    with write_transaction() as s:
        m = s.get(CharacterMood, mood_id)
        if m:
            s.delete(m)


def to_dict(m: CharacterMood) -> dict[str, Any]:
    return {
        "id": m.id,
        "character_id": m.character_id,
        "chapter_id": m.chapter_id,
        "mood": m.mood,
        "mood_label": MOODS.get(m.mood, {}).get("label", m.mood),
        "mood_icon": MOODS.get(m.mood, {}).get("icon", ""),
        "mood_color": MOODS.get(m.mood, {}).get("color", "#94a3b8"),
        "mood_score": MOODS.get(m.mood, {}).get("score", 3),
        "intensity": m.intensity,
        "intensity_label": INTENSITIES.get(m.intensity, {}).get("label", m.intensity),
        "note": m.note or "",
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def get_timeline(*, character_id: str | None = None) -> dict[str, Any]:
    """Build mood timeline across chapters."""
    with read_session() as s:
        chapters = list(s.scalars(
            select(Chapter).where(Chapter.project_id == current_project_id(s))
            .order_by(Chapter.sort_order.asc())
        ))
        characters = list(s.scalars(
            select(Character).where(Character.project_id == current_project_id(s))
            .order_by(Character.name.asc())
        ))
        moods = list_moods(character_id=character_id)

    # Build: {character_id: [{chapter_id, chapter_title, mood, ...}]}
    mood_map: dict[str, list[dict[str, Any]]] = {}
    for m in moods:
        d = to_dict(m)
        ch = next((c for c in chapters if c.id == m.chapter_id), None)
        d["chapter_title"] = ch.title if ch else "?"
        d["chapter_sort_order"] = ch.sort_order if ch else 0
        mood_map.setdefault(m.character_id, []).append(d)

    # Sort each character's moods by chapter sort_order
    for cid in mood_map:
        mood_map[cid].sort(key=lambda x: x["chapter_sort_order"])

    # Build char info
    char_info = {c.id: {"name": c.name, "role": c.role,
                        "avatar_color": c.avatar_color or "#6366f1"} for c in characters}

    return {
        "chapters": [{"id": ch.id, "title": ch.title, "sort_order": ch.sort_order} for ch in chapters],
        "characters": [{"id": c.id, "name": c.name, "role": c.role,
                        "avatar_color": c.avatar_color or "#6366f1"} for c in characters],
        "mood_timeline": {cid: mood_map.get(cid, []) for cid in char_info},
        "char_info": char_info,
        "total_moods": len(moods),
    }
