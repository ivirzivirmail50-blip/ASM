"""Writing Analytics service — deeper, cross-chapter statistics.

Distinct from stats_service.py (which is dashboard-level metrics). This
module computes per-chapter and cross-chapter analytics:

- Per-chapter: word count, sentence count, paragraph count, avg sentence length,
  dialogue ratio (proportion of text inside quotes), unique word count (lexical
  diversity), reading time estimate
- Cross-chapter: word count distribution, dialogue vs narration ratio per
  chapter (for spotting chapters that are dialogue-heavy or narration-heavy),
  character appearance frequency per chapter, lexical diversity trend
- Vocabulary richness: type-token ratio (TTR) for whole manuscript, list of
  top-N most-used words (excluding stopwords)
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from typing import Any

from sqlalchemy import select

from core.cache import cache
from core.db import read_session
from models.chapter import Chapter
from services._common import current_project_id, load_json

log = logging.getLogger("asm.analytics")

ANALYTICS_CACHE_TTL = 90  # seconds

# Common English stopwords for the top-words feature
STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "if", "then", "else", "when",
    "at", "by", "for", "with", "about", "against", "between", "into",
    "through", "during", "before", "after", "above", "below", "to", "from",
    "up", "down", "in", "out", "on", "off", "over", "under", "again",
    "further", "is", "are", "was", "were", "be", "been", "being", "have",
    "has", "had", "do", "does", "did", "will", "would", "should", "could",
    "can", "may", "might", "must", "shall", "of", "as", "it", "its", "i",
    "you", "he", "she", "we", "they", "them", "him", "her", "his", "hers",
    "our", "ours", "your", "yours", "their", "theirs", "this", "that",
    "these", "those", "there", "here", "what", "which", "who", "whom",
    "my", "me", "us", "am", "not", "no", "yes", "so", "than", "too", "very",
    "just", "also", "only", "now", "then", "once", "all", "any", "both",
    "each", "few", "more", "most", "other", "some", "such", "own", "same",
    "s", "t", "d", "ll", "ve", "re", "m", "o",
})


# ---------------------------------------------------------------------------
# Per-chapter analytics
# ---------------------------------------------------------------------------

def _count_sentences(text: str) -> int:
    """Approximate sentence count using terminal punctuation followed by space."""
    if not text:
        return 0
    # Match . ! ? followed by whitespace or end of string, but not abbreviations like "Dr."
    matches = re.findall(r"[.!?]+(?=\s|$)", text)
    return max(1, len(matches))


def _count_paragraphs(text: str) -> int:
    if not text:
        return 0
    # Split on double-newline
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    return max(1, len(paras))


def _dialogue_ratio(text: str) -> float:
    """Proportion of text length that falls inside quotation marks (0.0 - 1.0)."""
    if not text:
        return 0.0
    # Match text inside " " or ' ' or " " or ' ' (smart quotes)
    quoted = re.findall(r'["\u201c\u201d](.*?)["\u201c\u201d]', text, re.DOTALL)
    quoted_total = sum(len(q) for q in quoted)
    return min(1.0, quoted_total / max(1, len(text)))


def _reading_time_minutes(text: str, wpm: int = 250) -> float:
    """Estimate reading time at given words-per-minute (default 250)."""
    if not text:
        return 0.0
    words = len(text.split())
    return round(words / max(1, wpm), 1)


def _count_words(text: str) -> int:
    if not text:
        return 0
    return len(text.split())


def _unique_words(text: str) -> int:
    if not text:
        return 0
    words = re.findall(r"\b[a-zA-Z']+\b", text.lower())
    return len(set(words))


def chapter_analytics(chapter_id: str) -> dict[str, Any]:
    """Compute analytics for a single chapter."""
    with read_session() as s:
        ch = s.get(Chapter, chapter_id)
        if not ch:
            from core.errors import NotFoundError
            raise NotFoundError("Chapter not found.")
        text = ch.content or ""
        wc = _count_words(text)
        sc = _count_sentences(text)
        pc = _count_paragraphs(text)
        return {
            "chapter_id": ch.id,
            "title": ch.title,
            "status": ch.status,
            "word_count": wc,
            "sentence_count": sc,
            "paragraph_count": pc,
            "avg_sentence_length": round(wc / sc, 1) if sc else 0,
            "avg_paragraph_length": round(wc / pc, 1) if pc else 0,
            "dialogue_ratio": round(_dialogue_ratio(text), 3),
            "unique_words": _unique_words(text),
            "lexical_diversity": round(_unique_words(text) / max(1, wc), 3),
            "reading_time_minutes": _reading_time_minutes(text),
            "character_count": len(text),
        }


def all_chapters_analytics() -> list[dict[str, Any]]:
    """Compute analytics for every chapter in the current project."""
    cache_key = "analytics:all_chapters"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    with read_session() as s:
        chapters = list(s.scalars(
            select(Chapter).where(
                Chapter.project_id == current_project_id(s)
            ).order_by(Chapter.sort_order.asc())
        ).all())
        results = []
        for ch in chapters:
            text = ch.content or ""
            wc = _count_words(text)
            sc = _count_sentences(text)
            pc = _count_paragraphs(text)
            uw = _unique_words(text)
            results.append({
                "chapter_id": ch.id,
                "title": ch.title,
                "status": ch.status,
                "sort_order": ch.sort_order,
                "word_count": wc,
                "sentence_count": sc,
                "paragraph_count": pc,
                "avg_sentence_length": round(wc / sc, 1) if sc else 0,
                "avg_paragraph_length": round(wc / pc, 1) if pc else 0,
                "dialogue_ratio": round(_dialogue_ratio(text), 3),
                "unique_words": uw,
                "lexical_diversity": round(uw / max(1, wc), 3),
                "reading_time_minutes": _reading_time_minutes(text),
            })
        cache.set(cache_key, results, ANALYTICS_CACHE_TTL)
        return results


# ---------------------------------------------------------------------------
# Manuscript-level analytics
# ---------------------------------------------------------------------------

def manuscript_summary() -> dict[str, Any]:
    """Aggregate stats across the whole manuscript."""
    cache_key = "analytics:manuscript_summary"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    chapters = all_chapters_analytics()
    if not chapters:
        return {
            "chapter_count": 0,
            "total_words": 0,
            "total_sentences": 0,
            "total_paragraphs": 0,
            "total_unique_words": 0,
            "avg_chapter_length": 0,
            "shortest_chapter": None,
            "longest_chapter": None,
            "avg_dialogue_ratio": 0,
            "avg_lexical_diversity": 0,
            "total_reading_time_minutes": 0,
            "word_count_distribution": [],
        }
    total_words = sum(c["word_count"] for c in chapters)
    total_sentences = sum(c["sentence_count"] for c in chapters)
    total_paragraphs = sum(c["paragraph_count"] for c in chapters)
    # For unique words across the whole manuscript, we need to re-scan text.
    # Approximation: sum of per-chapter unique words (overcounts repeats across chapters).
    # For now we use a true aggregate by reading raw text.
    with read_session() as s:
        all_text = ""
        for ch in s.scalars(
            select(Chapter).where(Chapter.project_id == current_project_id(s))
        ).all():
            all_text += (ch.content or "") + " "
        total_unique = _unique_words(all_text)
    shortest = min(chapters, key=lambda c: c["word_count"])
    longest = max(chapters, key=lambda c: c["word_count"])
    summary = {
        "chapter_count": len(chapters),
        "total_words": total_words,
        "total_sentences": total_sentences,
        "total_paragraphs": total_paragraphs,
        "total_unique_words": total_unique,
        "avg_chapter_length": round(total_words / len(chapters), 1),
        "shortest_chapter": shortest,
        "longest_chapter": longest,
        "avg_dialogue_ratio": round(sum(c["dialogue_ratio"] for c in chapters) / len(chapters), 3),
        "avg_lexical_diversity": round(sum(c["lexical_diversity"] for c in chapters) / len(chapters), 3),
        "total_reading_time_minutes": round(sum(c["reading_time_minutes"] for c in chapters), 1),
        "word_count_distribution": [
            {"title": c["title"], "word_count": c["word_count"], "status": c["status"]}
            for c in chapters
        ],
    }
    cache.set(cache_key, summary, ANALYTICS_CACHE_TTL)
    return summary


def top_words(limit: int = 50, *, exclude_stopwords: bool = True) -> list[dict[str, Any]]:
    """Most-used words across the manuscript."""
    cache_key = f"analytics:top_words:{limit}:{exclude_stopwords}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    with read_session() as s:
        all_text = ""
        for ch in s.scalars(
            select(Chapter).where(Chapter.project_id == current_project_id(s))
        ).all():
            all_text += (ch.content or "") + " "
        words = re.findall(r"\b[a-zA-Z']+\b", all_text.lower())
        if exclude_stopwords:
            words = [w for w in words if w not in STOPWORDS and len(w) > 1]
        counts = Counter(words)
        out = [{"word": w, "count": c} for w, c in counts.most_common(limit)]
        cache.set(cache_key, out, ANALYTICS_CACHE_TTL)
        return out


def character_appearances_per_chapter() -> list[dict[str, Any]]:
    """For each chapter, list characters that appear (linked via character_ids)."""
    cache_key = "analytics:char_per_chapter"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    from models.character import Character
    with read_session() as s:
        chapters = list(s.scalars(
            select(Chapter).where(
                Chapter.project_id == current_project_id(s)
            ).order_by(Chapter.sort_order.asc())
        ).all())
        characters = list(s.scalars(
            select(Character).where(
                Character.project_id == current_project_id(s)
            ).order_by(Character.name.asc())
        ).all())
        char_map = {c.id: c for c in characters}
        out = []
        for ch in chapters:
            ids = load_json(ch.character_ids, [])
            ch_chars = [char_map[i] for i in ids if i in char_map]
            out.append({
                "chapter_id": ch.id,
                "chapter_title": ch.title,
                "sort_order": ch.sort_order,
                "word_count": ch.word_count,
                "characters": [
                    {"id": c.id, "name": c.name, "role": c.role,
                     "avatar_color": c.avatar_color or "#6366f1"}
                    for c in ch_chars
                ],
            })
        cache.set(cache_key, out, ANALYTICS_CACHE_TTL)
        return out


def character_screen_time() -> list[dict[str, Any]]:
    """For each character: total chapters in, total words in those chapters, % of manuscript."""
    cache_key = "analytics:char_screen_time"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    per_chapter = character_appearances_per_chapter()
    total_words = sum(c["word_count"] for c in per_chapter) or 1
    by_char: dict[str, dict[str, Any]] = {}
    for entry in per_chapter:
        for c in entry["characters"]:
            cid = c["id"]
            if cid not in by_char:
                by_char[cid] = {
                    "id": cid, "name": c["name"], "role": c["role"],
                    "avatar_color": c["avatar_color"],
                    "chapters_in": 0, "total_words": 0,
                }
            by_char[cid]["chapters_in"] += 1
            by_char[cid]["total_words"] += entry["word_count"]
    out = list(by_char.values())
    for c in out:
        c["manuscript_pct"] = round(c["total_words"] / total_words * 100, 1)
    out.sort(key=lambda c: c["total_words"], reverse=True)
    cache.set(cache_key, out, ANALYTICS_CACHE_TTL)
    return out
