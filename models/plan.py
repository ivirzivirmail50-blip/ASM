"""Plans (Kanban/timeline/outline) + subtasks."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text

from models import Base


class Plan(Base):
    __tablename__ = "plans"

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id"), default="default", index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    status = Column(String(40), default="idea", index=True)
    column = Column(String(40), default="idea")
    sort_order = Column(Integer, default=0, index=True)
    chapter_id = Column(String, ForeignKey("chapters.id"))
    parent_id = Column(String, ForeignKey("plans.id"))
    depends_on_id = Column(String, ForeignKey("plans.id"))
    story_date = Column(String(80))
    event_type = Column(String(60))  # plot_point/character_moment/climax/resolution/custom
    track = Column(String(80))  # timeline lane
    characters_involved = Column(Text)  # JSON array
    deadline = Column(Date)
    effort_estimate = Column(Integer)
    tags = Column(Text)  # JSON array
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class PlanSubtask(Base):
    __tablename__ = "plan_subtasks"

    id = Column(String, primary_key=True)
    plan_id = Column(String, ForeignKey("plans.id"), index=True)
    title = Column(String(500), nullable=False)
    is_completed = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
