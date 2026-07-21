"""SQLAlchemy ORM models for Absolute Story Manager."""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all models."""


# Import all model modules so they register on Base.metadata.
from models import (  # noqa: E402,F401
    project, settings, activity, chapter, character, plan, world, undo,
    travel_route, beta_comment, ai_history, inspiration, note, glossary,
    submission, voice, reference, scene, journal, achievement, spellcheck,
    session, chapter_deps, milestone, char_mood,
)
from services.snippet_service import Snippet  # noqa: E402,F401
from services.checklist_service import ChapterChecklist  # noqa: E402,F401

ALL_MODELS = (project, settings, activity, chapter, character, plan, world, undo,
              travel_route, beta_comment, ai_history, inspiration, note, glossary,
              submission, voice, reference, scene, journal, achievement, spellcheck,
              session, chapter_deps, milestone, char_mood)
