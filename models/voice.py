"""Character Voice Profile model — speech patterns, vocabulary, dialogue style.

Each character can have one voice profile that captures how they speak,
so the writer (or AI assistant) can keep dialogue consistent across chapters.

Fields:
- character_id: link to Character
- speech_verbosity: terse / moderate / verbose
- formality: informal / neutral / formal / archaic
- favorite_words: JSON list of words/phrases the character uses often
- avoided_words: JSON list of words the character would never use
- catchphrases: JSON list of signature phrases
- speech_quirks: text describing stutters, accents, verbal tics
- typical_sentence_length: short (5-10) / medium (10-20) / long (20+)
- uses_contractions: bool
- favorite_topics: JSON list
- avoids_topics: JSON list
- example_dialogue: text — a representative sample
- notes: freeform
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from models import Base


class CharacterVoice(Base):
    """A character's speech profile, used for dialogue consistency."""
    __tablename__ = "character_voices"

    id = Column(String, primary_key=True)
    character_id = Column(String, ForeignKey("characters.id"), nullable=False, index=True, unique=True)
    project_id = Column(String, default="default", index=True)

    # Quantitative speech style
    speech_verbosity = Column(String(20), default="moderate")    # terse / moderate / verbose
    formality = Column(String(20), default="neutral")             # informal / neutral / formal / archaic
    typical_sentence_length = Column(String(20), default="medium") # short / medium / long
    uses_contractions = Column(Boolean, default=True)

    # Vocabulary
    favorite_words = Column(Text)    # JSON array
    avoided_words = Column(Text)     # JSON array
    catchphrases = Column(Text)      # JSON array

    # Qualitative
    speech_quirks = Column(Text)     # "stutters on 's', drops 'g' from -ing"
    favorite_topics = Column(Text)   # JSON array
    avoids_topics = Column(Text)     # JSON array
    example_dialogue = Column(Text)  # representative sample

    notes = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


VERBOSITY_LEVELS = {
    "terse":    {"label": "Terse",    "desc": "Short, clipped responses. Few words.", "icon": "🗯"},
    "moderate": {"label": "Moderate", "desc": "Average length. Speaks in full sentences.", "icon": "💬"},
    "verbose":  {"label": "Verbose",  "desc": "Long, elaborate. Loves to monologue.", "icon": "📝"},
}

FORMALITY_LEVELS = {
    "informal":  {"label": "Informal",  "desc": "Slang, contractions, casual vocabulary.", "icon": "😎"},
    "neutral":   {"label": "Neutral",   "desc": "Everyday standard speech.", "icon": "😐"},
    "formal":    {"label": "Formal",    "desc": "Polished, educated, polite.", "icon": "🎩"},
    "archaic":   {"label": "Archaic",   "desc": "Old-fashioned, period-appropriate.", "icon": "📜"},
}

SENTENCE_LENGTHS = {
    "short":  {"label": "Short",  "desc": "5-10 words per sentence.", "icon": "•"},
    "medium": {"label": "Medium", "desc": "10-20 words per sentence.", "icon": "••"},
    "long":   {"label": "Long",   "desc": "20+ words per sentence.", "icon": "•••"},
}
