"""Glossary & Style Sheet model — writer's bible of consistent terms."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from models import Base


class GlossaryEntry(Base):
    """A canonical term the writer wants to keep consistent across the manuscript.

    Examples:
    - Character name: "Elara Morningstar" (canonical) — alternates: "El", "Lara"
    - Place: "the Shimmering Wastes" — alternates: "the Wastes"
    - Magic term: "aetherbinding" — alternates: "aether-binding", "Aetherbinding"
    - Spelling preference: "colour" (UK) — alternates: "color" (flag as inconsistency)
    - Capitalization: "the Council" — alternates: "the council"
    """
    __tablename__ = "glossary_entries"

    id = Column(String, primary_key=True)
    project_id = Column(String, default="default", index=True)
    term = Column(String(300), nullable=False)            # canonical form
    category = Column(String(60), default="general")      # character/place/magic/item/style/other
    definition = Column(Text)                              # what it means / why it matters
    alternates = Column(Text)                              # JSON array of acceptable alternates
    forbidden = Column(Text)                               # JSON array of variants that should NOT appear
    case_sensitive = Column(Integer, default=0)            # 0/1 — match case-sensitively
    notes = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
