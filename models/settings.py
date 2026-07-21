"""Settings (key/value with JSON-encoded values)."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Column, String, Text

from models import Base


DEFAULT_SETTINGS: dict[str, str] = {
    "active_project_id": "default",
    "story_title": "My Story",
    "story_author": "Author",
    "story_genre": "",
    "story_description": "",
    "daily_word_goal": "500",
    "total_word_goal": "80000",
    "manuscript_font": "Courier",
    "manuscript_font_size": "12",
    "manuscript_line_spacing": "2.0",
    "manuscript_margins": "1.0",
    "autosave_interval_seconds": "3",
    "version_snapshot_interval_minutes": "15",
    "auto_backup_enabled": "true",
    "auto_backup_interval_hours": "6",
    "theme": "dark",
    "sidebar_collapsed": "false",
    "editor_font": "serif",
    "editor_font_size": "16",
    "chapter_viewer_font": "serif",
    "chapter_viewer_font_size": "16",
    "chapter_sort_default": "sort_order",
    "character_sort_default": "name",
    "default_chapter_status": "draft",
    "world_types": '["location","lore","faction","glossary"]',
    "ai.enabled": "false",
    "ai.provider": "ollama",
    "ai.api_base": "http://localhost:11434",
    "ai.api_key": "",
    "ai.model": "",
    "ai.timeout_seconds": "180",
    "ai.disclosure_accepted": "false",
    "chapters_per_page": "30",
    "world_per_page": "40",
    "search_results_per_module": "50",
}


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(Text)

    @classmethod
    def get(cls, session, key: str, default: Any = None) -> Any:
        row = session.query(cls).filter_by(key=key).first()
        if row is None or row.value is None:
            return default
        try:
            return json.loads(row.value)
        except (json.JSONDecodeError, TypeError):
            return row.value

    @classmethod
    def set(cls, session, key: str, value: Any) -> None:
        v = json.dumps(value) if not isinstance(value, str) else json.dumps(value)
        row = session.query(cls).filter_by(key=key).first()
        if row is None:
            session.add(cls(key=key, value=v))
        else:
            row.value = v

    @classmethod
    def all_settings(cls, session) -> dict[str, Any]:
        rows = session.query(cls).all()
        out = dict(DEFAULT_SETTINGS)  # ensure defaults exist
        for r in rows:
            try:
                out[r.key] = json.loads(r.value) if r.value else r.value
            except (json.JSONDecodeError, TypeError):
                out[r.key] = r.value
        return out
