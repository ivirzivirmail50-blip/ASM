"""Submission Tracker model — track where you sent your manuscript and the response."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Integer, String, Text

from models import Base


class Submission(Base):
    """A submission of a manuscript (or story/chapter) to a market.

    Used to track:
    - Where you submitted (market name, type: magazine/agent/publisher/contest)
    - What you submitted (chapter / project)
    - When you sent it
    - Status: drafting / submitted / in_review / accepted / rejected / withdrawn / published
    - Response date (and days-to-respond auto-computed)
    - Notes (cover letter, feedback received, etc.)
    """
    __tablename__ = "submissions"

    id = Column(String, primary_key=True)
    project_id = Column(String, default="default", index=True)
    title = Column(String(500), nullable=False)             # what you submitted
    market_name = Column(String(300), nullable=False)        # magazine / agent / publisher / contest
    market_type = Column(String(40), default="magazine")     # magazine / agent / publisher / contest / anthology
    chapter_id = Column(String, nullable=True)               # optional link to a chapter
    status = Column(String(40), default="drafting", index=True)
    submitted_date = Column(Date, nullable=True)             # when you sent it
    response_date = Column(Date, nullable=True)              # when they responded
    days_to_respond = Column(Integer, nullable=True)         # auto-computed
    response_type = Column(String(40), nullable=True)        # accept / reject / revise / withdrawn / n/a
    cover_letter = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


SUBMISSION_STATUSES = {
    "drafting":   {"label": "Drafting",      "icon": "📝", "color": "#94a3b8", "order": 1},
    "submitted":  {"label": "Submitted",     "icon": "📤", "color": "#60a5fa", "order": 2},
    "in_review":  {"label": "In Review",     "icon": "⏳", "color": "#facc15", "order": 3},
    "accepted":   {"label": "Accepted",      "icon": "✓",  "color": "#34d399", "order": 4},
    "rejected":   {"label": "Rejected",      "icon": "✕",  "color": "#f87171", "order": 5},
    "withdrawn":  {"label": "Withdrawn",     "icon": "↩",  "color": "#a78bfa", "order": 6},
    "published":  {"label": "Published",     "icon": "🎉", "color": "#10b981", "order": 7},
}

MARKET_TYPES = {
    "magazine":   {"label": "Magazine",     "icon": "📰"},
    "agent":      {"label": "Agent",        "icon": "🤝"},
    "publisher":  {"label": "Publisher",    "icon": "📚"},
    "contest":    {"label": "Contest",      "icon": "🏆"},
    "anthology":  {"label": "Anthology",    "icon": "📖"},
    "other":      {"label": "Other",        "icon": "📝"},
}
