"""Travel route model — character journeys on the world map."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from models import Base


class TravelRoute(Base):
    """A character's travel route between map pins."""
    __tablename__ = "travel_routes"

    id = Column(String, primary_key=True)
    project_id = Column(String, default="default", index=True)
    character_id = Column(String, index=True)
    name = Column(String(200))
    color = Column(String(20), default="#6366f1")
    waypoints = Column(Text)  # JSON: [{x, y, label, entry_id}, ...]
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
