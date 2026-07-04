"""Pacing analysis service — chapter tension & rhythm visualization.

Analyzes:
- Chapter word count distribution
- Dialogue vs. narration ratio
- Sentence length variance (rhythm)
- Scene break detection
- Tension score (based on action words, dialogue density, exclamations)
"""
from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import select

from core.db import read_session
from models.chapter import Chapter
from services._common import current_project_id, load_json

log = logging.getLogger("asm.pacing")

# Action/tension keywords
_TENSION_WORDS = frozenset({
    "fight", "battle", "attack", "kill", "die", "death", "blood", "sword",
    "blade", "strike", "fall", "crash", "burn", "fire", "scream", "shout",
    "rage", "fury", "terror", "fear", "danger", "threat", "enemy", "war",
    "run", "chase", "escape", "flee", "hunt", "trap", "betray", "dark",
    "shadow", "monster", "beast", "dragon", "magic", "spell", "curse",
    "break", "destroy", "shatter", "explode", "force", "power", "storm",
})


def analyze_all() -> dict[str, Any]:
    """Analyze pacing across all chapters.

    Returns:
        chapters: [{title, word_count, dialogue_pct, narration_pct,
                   avg_sentence_len, tension_score, scene_count}, ...]
        summary: {total_words, avg_chapter_words, longest, shortest,
                  avg_tension, overall_rhythm}
    """
    with read_session() as s:
        pid = current_project_id(s)
        chapters = list(s.scalars(
            select(Chapter).where(Chapter.project_id == pid)
            .order_by(Chapter.sort_order.asc())
        ).all())

    results = []
    for ch in chapters:
        content = ch.content or ""
        if not content.strip():
            continue
        results.append({
            "id": ch.id,
            "title": ch.title,
            "sort_order": ch.sort_order,
            "word_count": ch.word_count or 0,
            "status": ch.status,
            **_analyze_chapter(content),
        })

    # Summary
    if results:
        word_counts = [r["word_count"] for r in results]
        tensions = [r["tension_score"] for r in results]
        avg_tension = sum(tensions) / len(tensions) if tensions else 0
        rhythm = _assess_rhythm(results)
        summary = {
            "total_words": sum(word_counts),
            "avg_chapter_words": int(sum(word_counts) / len(word_counts)),
            "longest": max(results, key=lambda r: r["word_count"])["title"] if results else "",
            "shortest": min(results, key=lambda r: r["word_count"])["title"] if results else "",
            "avg_tension": round(avg_tension, 1),
            "overall_rhythm": rhythm,
            "chapter_count": len(results),
        }
    else:
        summary = {"total_words": 0, "avg_chapter_words": 0, "chapter_count": 0,
                   "avg_tension": 0, "overall_rhythm": "No data"}

    return {"chapters": results, "summary": summary}


def _analyze_chapter(content: str) -> dict:
    """Analyze a single chapter's pacing metrics."""
    words = content.split()
    word_count = len(words)

    # Dialogue vs narration
    dialogue_matches = re.findall(r'"[^"]*"', content)
    dialogue_words = sum(len(m.split()) for m in dialogue_matches)
    dialogue_pct = round(dialogue_words / max(word_count, 1) * 100, 1)
    narration_pct = round(100 - dialogue_pct, 1)

    # Sentence analysis
    sentences = [s.strip() for s in re.split(r'[.!?]+', content) if s.strip()]
    sentence_lengths = [len(s.split()) for s in sentences]
    avg_sentence_len = round(sum(sentence_lengths) / max(len(sentence_lengths), 1), 1)

    # Scene breaks
    scene_count = content.count("\n\n\n") + content.count("---") + content.count("***") + 1

    # Tension score (0-10)
    content_lower = content.lower()
    tension_count = sum(1 for w in words if w.lower().strip(".,!?;:\"'") in _TENSION_WORDS)
    exclamation_count = content.count("!")
    question_count = content.count("?")

    # Normalize: tension words per 100 words + punctuation density
    tension_density = (tension_count / max(word_count, 1)) * 100
    punct_density = ((exclamation_count + question_count) / max(word_count, 1)) * 100
    raw_score = tension_density * 2 + punct_density * 3
    tension_score = min(10, round(raw_score, 1))

    return {
        "dialogue_pct": dialogue_pct,
        "narration_pct": narration_pct,
        "avg_sentence_len": avg_sentence_len,
        "scene_count": scene_count,
        "tension_score": tension_score,
        "sentence_count": len(sentences),
        "exclamation_count": exclamation_count,
    }


def _assess_rhythm(chapters: list[dict]) -> str:
    """Assess overall rhythm based on chapter length variance and tension."""
    if len(chapters) < 2:
        return "Insufficient data"

    word_counts = [c["word_count"] for c in chapters]
    avg = sum(word_counts) / len(word_counts)
    variance = sum((w - avg) ** 2 for w in word_counts) / len(word_counts)
    std_dev = variance ** 0.5
    cv = std_dev / avg if avg > 0 else 0  # coefficient of variation

    # Tension trend
    tensions = [c["tension_score"] for c in chapters]
    if len(tensions) >= 3:
        last_third = tensions[len(tensions)*2//3:]
        first_third = tensions[:len(tensions)//3]
        avg_first = sum(first_third) / max(len(first_third), 1)
        avg_last = sum(last_third) / max(len(last_third), 1)
    else:
        avg_first = avg_last = 0

    if cv > 0.5:
        length_assessment = "highly variable chapter lengths"
    elif cv > 0.25:
        length_assessment = "moderately variable chapter lengths"
    else:
        length_assessment = "consistent chapter lengths"

    if avg_last > avg_first + 1.5:
        tension_assessment = "rising tension toward the end"
    elif avg_first > avg_last + 1.5:
        tension_assessment = "falling tension toward the end"
    else:
        tension_assessment = "steady tension throughout"

    return f"{length_assessment}, {tension_assessment}"
