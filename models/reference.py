"""Research & Reference model — track sources, links, quotes, citations.

A writer's research library: books, articles, websites, interviews,
documentaries, with optional quotes/excerpts and chapter links.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from models import Base


class Reference(Base):
    """A research source: book, article, website, interview, etc.

    Can have:
    - quotes/excerpts (JSON array of {text, page, notes})
    - chapter links (which chapters cite this reference)
    - read status: unread / reading / read
    - priority: low / medium / high
    """
    __tablename__ = "references"

    id = Column(String, primary_key=True)
    project_id = Column(String, default="default", index=True)
    title = Column(String(500), nullable=False)
    author = Column(String(300))
    url = Column(Text)
    source_type = Column(String(40), default="article")  # book/article/website/video/interview/podcast/other
    publication_date = Column(String(40))  # freeform: "2023", "June 2024", etc.
    publisher = Column(String(300))
    isbn_or_doi = Column(String(100))
    description = Column(Text)
    quotes = Column(Text)  # JSON array of {text, page, notes}
    tags = Column(Text)    # JSON array
    chapter_ids = Column(Text)  # JSON array of linked chapter IDs
    read_status = Column(String(20), default="unread")  # unread / reading / read
    priority = Column(String(20), default="medium")  # low / medium / high
    rating = Column(Integer)  # 1-5 stars
    notes = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


REFERENCE_TYPES = {
    "book":       {"label": "Book",        "icon": "📚"},
    "article":    {"label": "Article",     "icon": "📰"},
    "website":    {"label": "Website",     "icon": "🌐"},
    "video":      {"label": "Video",       "icon": "🎥"},
    "interview":  {"label": "Interview",   "icon": "🎤"},
    "podcast":    {"label": "Podcast",     "icon": "🎧"},
    "document":   {"label": "Document",    "icon": "📄"},
    "other":      {"label": "Other",       "icon": "📝"},
}

READ_STATUSES = {
    "unread":  {"label": "Unread",  "icon": "📭", "color": "#94a3b8"},
    "reading": {"label": "Reading", "icon": "📖", "color": "#facc15"},
    "read":    {"label": "Read",    "icon": "✓",  "color": "#34d399"},
}

PRIORITIES = {
    "low":    {"label": "Low",    "icon": "↓", "color": "#94a3b8"},
    "medium": {"label": "Medium", "icon": "=", "color": "#facc15"},
    "high":   {"label": "High",   "icon": "↑", "color": "#f87171"},
}
