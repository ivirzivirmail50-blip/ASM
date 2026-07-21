"""Word Frequency Analyzer — find overused words and repetition patterns.

Analyzes chapter content to find:
- Top N most frequent words (excluding stopwords)
- Overused words (appears more than expected threshold)
- Repeated phrases (2-3 word sequences that repeat)
- Character name frequency (how often each character is mentioned)
- Per-chapter word frequency comparison

Useful for catching lazy repetition ("she smiled", "he nodded" overuse).
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Any

from sqlalchemy import select

from core.cache import cache
from core.db import read_session
from models.chapter import Chapter
from models.character import Character
from services._common import current_project_id, load_json

log = logging.getLogger("asm.word_freq")

CACHE_TTL = 120

# Extended stopwords (common English + common writing words)
STOPWORDS = frozenset("""
the a an and or but if then else when at by for with about against between into
through during before after above below to from up down in out on off over under
again further is are was were be been being have has had do does did will would
should could can may might must shall of as it its i you he she we they them him
her his hers our ours your yours their theirs this that these those there here
what which who whom my me us am not no yes so than too very just also only now
then once all any both each few more most other some such own same s t d ll ve re m o
said says say saying get got go goes going went come comes came take takes took
make makes made see sees saw look looks looked know knows knew think thinks thought
feel feels felt want wants wanted need needs needed like likes liked
""".split())


def _tokenize(text: str) -> list[str]:
    """Extract lowercase word tokens (letters + apostrophes)."""
    if not text:
        return []
    return re.findall(r"\b[a-z][a-z']*\b", text.lower())


def _extract_phrases(text: str, n: int = 2) -> list[str]:
    """Extract n-word phrases from text."""
    if not text:
        return []
    words = re.findall(r"\b[a-z][a-z']*\b", text.lower())
    if len(words) < n:
        return []
    return [" ".join(words[i:i+n]) for i in range(len(words) - n + 1)]


def analyze_chapter(chapter_id: str, *, top_n: int = 50) -> dict[str, Any]:
    """Analyze word frequency in a single chapter."""
    cache_key = f"wordfreq:chapter:{chapter_id}:{top_n}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    with read_session() as s:
        ch = s.get(Chapter, chapter_id)
        if not ch:
            from core.errors import NotFoundError
            raise NotFoundError("Chapter not found.")
        content = ch.content or ""
        title = ch.title

    words = _tokenize(content)
    total_words = len(words)

    # All words frequency
    all_counts = Counter(words)

    # Non-stopword frequency
    non_stop = [(w, c) for w, c in all_counts.most_common(top_n * 3)
                if w not in STOPWORDS and len(w) > 2][:top_n]

    # Overused detection: word appears more than (total_words / 100) times
    # i.e., more than ~1% of the chapter
    threshold = max(5, total_words // 100)
    overused = [{"word": w, "count": c, "pct": round(c / max(1, total_words) * 100, 2)}
                for w, c in all_counts.most_common()
                if w not in STOPWORDS and len(w) > 3 and c >= threshold][:20]

    # Repeated 2-word phrases
    phrases_2 = Counter(_extract_phrases(content, 2))
    repeated_phrases = [{"phrase": p, "count": c}
                        for p, c in phrases_2.most_common(20) if c >= 3]

    result = {
        "chapter_id": chapter_id,
        "chapter_title": title,
        "total_words": total_words,
        "unique_words": len(all_counts),
        "lexical_diversity": round(len(all_counts) / max(1, total_words), 3),
        "top_words": [{"word": w, "count": c} for w, c in non_stop],
        "overused": overused,
        "repeated_phrases": repeated_phrases,
        "overuse_threshold": threshold,
    }
    cache.set(cache_key, result, CACHE_TTL)
    return result


def analyze_manuscript(*, top_n: int = 50) -> dict[str, Any]:
    """Analyze word frequency across the entire manuscript."""
    cache_key = f"wordfreq:manuscript:{top_n}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    with read_session() as s:
        chapters = list(s.scalars(
            select(Chapter).where(Chapter.project_id == current_project_id(s))
            .order_by(Chapter.sort_order.asc())
        ))
        all_text = ""
        per_chapter: list[dict[str, Any]] = []
        for ch in chapters:
            content = ch.content or ""
            all_text += " " + content
            ch_analysis = analyze_chapter(ch.id, top_n=20)
            per_chapter.append({
                "chapter_id": ch.id,
                "chapter_title": ch.title,
                "total_words": ch_analysis["total_words"],
                "unique_words": ch_analysis["unique_words"],
                "top_5": ch_analysis["top_words"][:5],
            })

    words = _tokenize(all_text)
    total_words = len(words)
    all_counts = Counter(words)

    # Top non-stopwords
    non_stop = [(w, c) for w, c in all_counts.most_common(top_n * 3)
                if w not in STOPWORDS and len(w) > 2][:top_n]

    # Overused (manuscript-wide threshold: 1 per 200 words)
    threshold = max(10, total_words // 200)
    overused = [{"word": w, "count": c, "pct": round(c / max(1, total_words) * 100, 2)}
                for w, c in all_counts.most_common()
                if w not in STOPWORDS and len(w) > 3 and c >= threshold][:30]

    # Repeated phrases
    phrases_2 = Counter(_extract_phrases(all_text, 2))
    phrases_3 = Counter(_extract_phrases(all_text, 3))
    repeated_2 = [{"phrase": p, "count": c} for p, c in phrases_2.most_common(20) if c >= 3]
    repeated_3 = [{"phrase": p, "count": c} for p, c in phrases_3.most_common(15) if c >= 3]

    # Character name frequency
    char_mentions: list[dict[str, Any]] = []
    with read_session() as s:
        characters = list(s.scalars(
            select(Character).where(Character.project_id == current_project_id(s))
        ))
        for c in characters:
            count = all_counts.get(c.name.lower(), 0)
            # Also check aliases
            aliases = load_json(c.aliases, [])
            for alias in aliases:
                count += all_counts.get(alias.lower(), 0)
            if count > 0:
                char_mentions.append({
                    "name": c.name, "role": c.role, "count": count,
                    "avatar_color": c.avatar_color or "#6366f1",
                })
    char_mentions.sort(key=lambda x: x["count"], reverse=True)

    result = {
        "total_words": total_words,
        "unique_words": len(all_counts),
        "lexical_diversity": round(len(all_counts) / max(1, total_words), 3),
        "top_words": [{"word": w, "count": c} for w, c in non_stop],
        "overused": overused,
        "repeated_phrases_2": repeated_2,
        "repeated_phrases_3": repeated_3,
        "character_mentions": char_mentions,
        "per_chapter": per_chapter,
        "overuse_threshold": threshold,
    }
    cache.set(cache_key, result, CACHE_TTL)
    return result
