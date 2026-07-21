"""Scene Card model — individual scenes within a chapter.

A scene is a unit of action within a chapter, typically separated by
blank lines (\\n\\n\\n) or explicit scene breaks (* * *). The Scene Card
Index lets the writer view and reorder scenes across the manuscript
as if they were physical index cards (corkboard at scene level).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from models import Base


class SceneCard(Base):
    """A single scene extracted from a chapter.

    Scenes can be:
    - Auto-extracted from chapter content (split on \\n\\n\\n or * * *)
    - Manually created as standalone scene ideas (chapter_id can be null)
    - Reordered across chapters (sort_order is global within the project)
    """
    __tablename__ = "scene_cards"

    id = Column(String, primary_key=True)
    project_id = Column(String, default="default", index=True)
    chapter_id = Column(String, ForeignKey("chapters.id"), nullable=True, index=True)
    title = Column(String(500))
    summary = Column(Text)         # 1-2 sentence summary for the corkboard card
    content_snippet = Column(Text)  # first ~500 chars of the actual scene text
    full_text = Column(Text)        # the complete scene text (when extracted)
    scene_break_marker = Column(String(20), default="###")  # the visual marker
    sort_order = Column(Integer, default=0, index=True)  # global across project
    # Corkboard card metadata
    color = Column(String(20))     # card color for visual organization
    pov_character_id = Column(String, ForeignKey("characters.id"), nullable=True)
    location = Column(String(200))  # where the scene takes place
    time_of_day = Column(String(40))  # morning/afternoon/evening/night
    mood = Column(String(40))       # tense / calm / humorous / dark / hopeful
    status = Column(String(20), default="draft")  # draft/revised/final
    word_count = Column(Integer, default=0)
    tags = Column(Text)             # JSON array
    notes = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


SCENE_STATUSES = {
    "draft":   {"label": "Draft",   "icon": "📝", "color": "#94a3b8"},
    "revised": {"label": "Revised", "icon": "✎",  "color": "#facc15"},
    "final":   {"label": "Final",   "icon": "✓",  "color": "#34d399"},
}

SCENE_MOODS = {
    "tense":    {"label": "Tense",    "icon": "⚡", "color": "#f87171"},
    "calm":     {"label": "Calm",     "icon": "🍃", "color": "#34d399"},
    "humorous": {"label": "Humorous", "icon": "😄", "color": "#facc15"},
    "dark":     {"label": "Dark",     "icon": "🌑", "color": "#6366f1"},
    "hopeful":  {"label": "Hopeful",  "icon": "🌅", "color": "#fb923c"},
    "romantic": {"label": "Romantic", "icon": "❤",  "color": "#ec4899"},
    "mysterious": {"label": "Mysterious", "icon": "🔍", "color": "#a78bfa"},
}

TIME_OF_DAY = {
    "morning":   "🌅 Morning",
    "afternoon": "☀ Afternoon",
    "evening":   "🌆 Evening",
    "night":     "🌙 Night",
    "dawn":      "🌅 Dawn",
    "dusk":      "🌆 Dusk",
}

CARD_COLORS = [
    "#fef3c7",  # amber-100
    "#dbeafe",  # blue-100
    "#d1fae5",  # emerald-100
    "#fce7f3",  # pink-100
    "#ede9fe",  # violet-100
    "#fee2e2",  # red-100
    "#fef9c3",  # yellow-100
    "#e0e7ff",  # indigo-100
]
