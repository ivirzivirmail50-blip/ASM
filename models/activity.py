"""Activity log (capped at 2000 entries for streaks/heatmap)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from models import Base
from security import limits


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String, default="default", index=True)
    entity_type = Column(String(50), index=True)  # chapter/character/plan/world_entry/ai_action
    entity_id = Column(String(64), index=True)
    entity_title = Column(String(500))
    action = Column(String(50))  # created/updated/deleted/uploaded/reordered/status_changed
    word_count_delta = Column(Integer, default=0)
    details = Column(Text)  # JSON
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


def cap_activity_log(session) -> None:
    """Delete oldest entries beyond the cap. Call after every insert."""
    count = session.query(ActivityLog).count()
    if count <= limits.ACTIVITY_LOG_CAP:
        return
    excess = count - limits.ACTIVITY_LOG_CAP
    # Find the id threshold of the (count - cap)th oldest entry.
    rows = (
        session.query(ActivityLog.id)
        .order_by(ActivityLog.id.asc())
        .limit(excess)
        .all()
    )
    ids_to_delete = [r[0] for r in rows]
    if ids_to_delete:
        session.query(ActivityLog).filter(
            ActivityLog.id.in_(ids_to_delete)
        ).delete(synchronize_session=False)
