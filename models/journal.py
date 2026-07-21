"""Daily Writing Journal model — dated entries for the writer's process.

Distinct from activity_log (which is automated event tracking) and Notes
(which are story-related). The Journal is for the writer's personal
process: how the writing went today, what they struggled with, what
they're grateful for, what they want to remember for tomorrow.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Integer, String, Text

from models import Base


class JournalEntry(Base):
    """One journal entry per day (enforced by unique date)."""
    __tablename__ = "journal_entries"

    id = Column(String, primary_key=True)
    project_id = Column(String, default="default", index=True)
    entry_date = Column(Date, nullable=False, index=True, unique=True)
    # The writer's process
    mood = Column(String(40))  # great / good / ok / struggling / blocked
    energy = Column(Integer)   # 1-5
    word_count_goal = Column(Integer)
    word_count_actual = Column(Integer)
    # Free-form content
    wins = Column(Text)         # what went well today
    struggles = Column(Text)    # what was hard
    intentions = Column(Text)   # what to focus on tomorrow
    gratitude = Column(Text)    # one thing to be grateful for
    notes = Column(Text)        # anything else
    # Tagging
    tags = Column(Text)         # JSON array
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


JOURNAL_MOODS = {
    "great":       {"label": "Great",       "icon": "🌟", "color": "#34d399", "score": 5},
    "good":        {"label": "Good",        "icon": "😊", "color": "#60a5fa", "score": 4},
    "ok":          {"label": "OK",          "icon": "😐", "color": "#94a3b8", "score": 3},
    "struggling":  {"label": "Struggling",  "icon": "😤", "color": "#facc15", "score": 2},
    "blocked":     {"label": "Blocked",     "icon": "🚫", "color": "#f87171", "score": 1},
}
