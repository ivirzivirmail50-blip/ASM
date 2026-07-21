"""Character Voice Profile service — keep dialogue consistent across chapters.

Each character can have ONE voice profile. The service provides:
- get_or_create: lazy-create a profile for a character
- update: edit profile fields
- scan_dialogue: find all dialogue lines by this character across chapters
  (based on chapter-character links) and report consistency issues:
  - Did they use a word from their "avoided_words" list?
  - Did they use any of their "catchphrases"?
  - Sentence length distribution vs their declared typical_sentence_length
- consistency_summary: a one-paragraph natural-language description of
  the character's voice (for writer reference or AI prompt context)
"""
from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import select

from core.db import read_session, write_transaction
from core.errors import NotFoundError, ValidationError
from models.voice import (
    CharacterVoice, VERBOSITY_LEVELS, FORMALITY_LEVELS, SENTENCE_LENGTHS,
)
from services._common import current_project_id, dump_json, load_json, log_activity, new_uuid, now_utc

log = logging.getLogger("asm.voice")


def get_profile(character_id: str) -> CharacterVoice | None:
    with read_session() as s:
        v = s.scalar(
            select(CharacterVoice).where(CharacterVoice.character_id == character_id)
        )
        return v


def get_or_create(character_id: str) -> CharacterVoice:
    """Get the voice profile for a character, creating an empty one if missing."""
    existing = get_profile(character_id)
    if existing:
        return existing
    # Verify character exists
    from models.character import Character
    with write_transaction() as s:
        c = s.get(Character, character_id)
        if not c:
            raise NotFoundError("Character not found.")
        v = CharacterVoice(
            id=new_uuid(),
            character_id=character_id,
            project_id=current_project_id(s),
            speech_verbosity="moderate",
            formality="neutral",
            typical_sentence_length="medium",
            uses_contractions=True,
            favorite_words=dump_json([]),
            avoided_words=dump_json([]),
            catchphrases=dump_json([]),
            favorite_topics=dump_json([]),
            avoids_topics=dump_json([]),
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        s.add(v)
        log_activity(
            s, entity_type="voice", entity_id=v.id,
            entity_title=f"Voice profile for {c.name}", action="created",
        )
        s.flush()
        return v


def update_profile(character_id: str, **fields: Any) -> CharacterVoice:
    # Ensure exists
    get_or_create(character_id)
    with write_transaction() as s:
        v = s.scalar(
            select(CharacterVoice).where(CharacterVoice.character_id == character_id)
        )
        if not v:
            raise NotFoundError("Voice profile not found.")
        for k in ("speech_verbosity", "formality", "typical_sentence_length",
                  "speech_quirks", "example_dialogue", "notes"):
            if k in fields and fields[k] is not None:
                setattr(v, k, fields[k])
        if "uses_contractions" in fields:
            v.uses_contractions = bool(fields["uses_contractions"])
        for arr_field in ("favorite_words", "avoided_words", "catchphrases",
                          "favorite_topics", "avoids_topics"):
            if arr_field in fields:
                setattr(v, arr_field, dump_json(fields[arr_field] or []))
        v.updated_at = now_utc()
        s.flush()
        return v


def to_dict(v: CharacterVoice) -> dict[str, Any]:
    return {
        "id": v.id,
        "character_id": v.character_id,
        "speech_verbosity": v.speech_verbosity,
        "verbosity_label": VERBOSITY_LEVELS.get(v.speech_verbosity, {}).get("label", v.speech_verbosity),
        "verbosity_desc": VERBOSITY_LEVELS.get(v.speech_verbosity, {}).get("desc", ""),
        "formality": v.formality,
        "formality_label": FORMALITY_LEVELS.get(v.formality, {}).get("label", v.formality),
        "formality_desc": FORMALITY_LEVELS.get(v.formality, {}).get("desc", ""),
        "typical_sentence_length": v.typical_sentence_length,
        "sentence_length_label": SENTENCE_LENGTHS.get(v.typical_sentence_length, {}).get("label", v.typical_sentence_length),
        "sentence_length_desc": SENTENCE_LENGTHS.get(v.typical_sentence_length, {}).get("desc", ""),
        "uses_contractions": bool(v.uses_contractions),
        "favorite_words": load_json(v.favorite_words, []),
        "avoided_words": load_json(v.avoided_words, []),
        "catchphrases": load_json(v.catchphrases, []),
        "favorite_topics": load_json(v.favorite_topics, []),
        "avoids_topics": load_json(v.avoids_topics, []),
        "speech_quirks": v.speech_quirks or "",
        "example_dialogue": v.example_dialogue or "",
        "notes": v.notes or "",
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "updated_at": v.updated_at.isoformat() if v.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Dialogue scanning
# ---------------------------------------------------------------------------

_DIALOGUE_RE = re.compile(r'["\u201c\u201d](.*?)["\u201c\u201d]', re.DOTALL)


def _extract_dialogue_lines(text: str) -> list[str]:
    """Extract individual quoted lines from chapter content."""
    if not text:
        return []
    return [m.group(1).strip() for m in _DIALOGUE_RE.finditer(text) if m.group(1).strip()]


def _sentence_count(text: str) -> int:
    if not text:
        return 0
    return max(1, len(re.findall(r"[.!?]+(?=\s|$)", text)))


def _word_count(text: str) -> int:
    if not text:
        return 0
    return len(text.split())


def scan_dialogue(character_id: str) -> dict[str, Any]:
    """Find dialogue lines attributed to this character across chapters.

    We don't have explicit line→character attribution, so we approximate:
    1. Find chapters this character is linked to
    2. Extract all dialogue lines from those chapters
    3. Flag any line containing a word from their "avoided_words" list
    4. Count how many of their "catchphrases" appear
    5. Compute average sentence length and compare to their declared style
    """
    from models.chapter import Chapter
    from models.character import Character
    v = get_profile(character_id)
    if not v:
        return {
            "character_id": character_id,
            "issues": [],
            "dialogue_lines_found": 0,
            "chapters_scanned": 0,
            "summary": "No voice profile exists for this character yet.",
        }
    avoided = [w.lower() for w in load_json(v.avoided_words, [])]
    catchphrases = load_json(v.catchphrases, [])
    favorite = [w.lower() for w in load_json(v.favorite_words, [])]

    issues: list[dict[str, Any]] = []
    catchphrase_hits = 0
    favorite_hits = 0
    all_dialogue: list[dict[str, Any]] = []
    chapters_scanned = 0

    with read_session() as s:
        character = s.get(Character, character_id)
        char_name = character.name if character else "(unknown)"
        # Find chapters linked to this character
        chapters = list(s.scalars(
            select(Chapter).where(Chapter.project_id == current_project_id(s))
            .order_by(Chapter.sort_order.asc())
        ).all())
        for ch in chapters:
            char_ids = load_json(ch.character_ids, [])
            if character_id not in char_ids:
                continue
            chapters_scanned += 1
            text = ch.content or ""
            lines = _extract_dialogue_lines(text)
            for line in lines:
                line_lower = line.lower()
                # Check avoided words
                for aw in avoided:
                    if aw and aw in line_lower:
                        # Extract a small context window
                        idx = line_lower.find(aw)
                        ctx_start = max(0, idx - 30)
                        ctx_end = min(len(line), idx + len(aw) + 30)
                        issues.append({
                            "chapter_id": ch.id,
                            "chapter_title": ch.title,
                            "type": "avoided_word",
                            "severity": "high",
                            "word": aw,
                            "context": line[max(0, idx - 30):min(len(line), idx + len(aw) + 30)],
                        })
                # Check catchphrases
                for cp in catchphrases:
                    if cp and cp.lower() in line_lower:
                        catchphrase_hits += 1
                # Check favorite words
                for fw in favorite:
                    if fw and fw in line_lower:
                        favorite_hits += 1
                all_dialogue.append({
                    "chapter_id": ch.id,
                    "chapter_title": ch.title,
                    "text": line,
                    "sentence_count": _sentence_count(line),
                    "word_count": _word_count(line),
                    "avg_sentence_length": round(_word_count(line) / max(1, _sentence_count(line)), 1),
                })

    # Compare avg sentence length to declared style
    declared = v.typical_sentence_length
    actual_avg = 0
    if all_dialogue:
        actual_avg = round(sum(d["avg_sentence_length"] for d in all_dialogue) / len(all_dialogue), 1)
    expected_ranges = {"short": (5, 10), "medium": (10, 20), "long": (20, 100)}
    expected_range = expected_ranges.get(declared, (10, 20))
    length_match = "consistent"
    if actual_avg > 0:
        if actual_avg < expected_range[0]:
            length_match = "shorter_than_declared"
        elif actual_avg > expected_range[1]:
            length_match = "longer_than_declared"

    return {
        "character_id": character_id,
        "character_name": char_name,
        "chapters_scanned": chapters_scanned,
        "dialogue_lines_found": len(all_dialogue),
        "issues": issues,
        "catchphrase_hits": catchphrase_hits,
        "favorite_word_hits": favorite_hits,
        "actual_avg_sentence_length": actual_avg,
        "declared_sentence_length": declared,
        "declared_range": list(expected_range),
        "length_match": length_match,
        "dialogue_sample": all_dialogue[:10],
    }


def consistency_summary(character_id: str) -> str:
    """Build a one-paragraph natural-language description of this character's voice.
    Useful for writer reference or as AI prompt context.
    """
    v = get_profile(character_id)
    if not v:
        return "No voice profile defined."
    from models.character import Character
    with read_session() as s:
        c = s.get(Character, character_id)
        name = c.name if c else "This character"
    parts: list[str] = []
    parts.append(f"{name} speaks in a {VERBOSITY_LEVELS.get(v.speech_verbosity, {}).get('label', 'moderate').lower()} manner")
    parts.append(f"with {FORMALITY_LEVELS.get(v.formality, {}).get('label', 'neutral').lower()} formality")
    parts.append(f"and {SENTENCE_LENGTHS.get(v.typical_sentence_length, {}).get('label', 'medium').lower()}-length sentences.")
    if not v.uses_contractions:
        parts.append("They avoid contractions, preferring full forms.")
    fav = load_json(v.favorite_words, [])
    if fav:
        parts.append(f"They favor words like: {', '.join(fav[:5])}.")
    avoid = load_json(v.avoided_words, [])
    if avoid:
        parts.append(f"They would never say: {', '.join(avoid[:5])}.")
    cps = load_json(v.catchphrases, [])
    if cps:
        parts.append(f"Signature phrases: {'; '.join(cps[:3])}.")
    if v.speech_quirks:
        parts.append(f"Quirks: {v.speech_quirks}.")
    fav_topics = load_json(v.favorite_topics, [])
    if fav_topics:
        parts.append(f"They love to talk about: {', '.join(fav_topics[:5])}.")
    avoid_topics = load_json(v.avoids_topics, [])
    if avoid_topics:
        parts.append(f"They avoid discussing: {', '.join(avoid_topics[:5])}.")
    if v.example_dialogue:
        parts.append(f"Example: \"{v.example_dialogue[:200]}\"")
    return " ".join(parts)
