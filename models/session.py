"""Writing Session Timer model — track focused writing sessions (Pomodoro-style).

A session captures:
- start/end timestamps
- duration (seconds)
- word count at start and end (delta = words written)
- session type: pomodoro (25min), short_focus (15min), long_focus (50min), custom
- status: active / paused / completed / abandoned
- pause durations (total paused seconds)
- linked chapter (optional)
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from models import Base


class WritingSession(Base):
    __tablename__ = "writing_sessions"

    id = Column(String, primary_key=True)
    project_id = Column(String, default="default", index=True)
    session_type = Column(String(30), default="pomodoro")  # pomodoro/short_focus/long_focus/custom
    target_minutes = Column(Integer, default=25)
    status = Column(String(20), default="active")  # active/paused/completed/abandoned
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    ended_at = Column(DateTime, nullable=True)
    elapsed_seconds = Column(Integer, default=0)  # active writing time (excludes pauses)
    paused_seconds = Column(Integer, default=0)
    word_count_start = Column(Integer, default=0)
    word_count_end = Column(Integer, default=0)
    words_written = Column(Integer, default=0)  # end - start
    chapter_id = Column(String, ForeignKey("chapters.id"), nullable=True)
    notes = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


SESSION_TYPES = {
    "pomodoro":     {"label": "Pomodoro (25min)",   "icon": "🍅", "minutes": 25},
    "short_focus":  {"label": "Short Focus (15min)", "icon": "⚡", "minutes": 15},
    "long_focus":   {"label": "Long Focus (50min)",  "icon": "🎯", "minutes": 50},
    "sprint":       {"label": "Sprint (10min)",      "icon": "🏃", "minutes": 10},
    "custom":       {"label": "Custom",              "icon": "⚙",  "minutes": None},
}

SESSION_STATUSES = {
    "active":     {"label": "Active",     "icon": "▶", "color": "#22c55e"},
    "paused":     {"label": "Paused",     "icon": "⏸", "color": "#f59e0b"},
    "completed":  {"label": "Completed",  "icon": "✓", "color": "#34d399"},
    "abandoned":  {"label": "Abandoned",  "icon": "✕", "color": "#ef4444"},
}
