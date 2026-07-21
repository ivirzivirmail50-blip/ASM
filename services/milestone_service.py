"""Word Count Milestone Celebrations — celebratory feedback for word goals.

Defines milestone thresholds and tracks which ones the writer has reached.
When a milestone is newly reached, the /milestones page shows a celebration.

Milestones (configurable):
- 1,000 words — "First Thousand"
- 5,000 words — "Short Story"
- 10,000 words — "Novella Start"
- 25,000 words — "Quarter Novel"
- 50,000 words — "NaNoWriMo Winner"
- 75,000 words — "Standard Novel"
- 100,000 words — "Epic Novel"
- 150,000 words — "Long Epic"
- 200,000 words — "Doorstopper"
- 300,000 words — "Series Starter"
- 500,000 words — "Prolific"
- 1,000,000 words — "Million Words"

Each milestone has: threshold, name, icon, description, reached (bool), reached_at.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func

from core.db import read_session, write_transaction
from core.cache import cache
from models.milestone import MilestoneCelebration
from models.chapter import Chapter
from models.settings import Setting
from services._common import current_project_id, new_uuid, now_utc

log = logging.getLogger("asm.milestones")


# Milestone definitions
MILESTONES: list[dict[str, Any]] = [
    {"key": "words_1k",    "threshold": 1_000,     "name": "First Thousand",    "icon": "✍",  "desc": "You wrote your first thousand words. The story has begun."},
    {"key": "words_5k",    "threshold": 5_000,     "name": "Short Story",       "icon": "📖", "desc": "Five thousand words — a short story's worth."},
    {"key": "words_10k",   "threshold": 10_000,    "name": "Novella Start",     "icon": "📜", "desc": "Ten thousand words. You're into novella territory."},
    {"key": "words_25k",   "threshold": 25_000,    "name": "Quarter Novel",     "icon": "🎯", "desc": "A quarter of a standard novel. Keep going!"},
    {"key": "words_50k",   "threshold": 50_000,    "name": "NaNoWriMo Winner",  "icon": "🏆", "desc": "Fifty thousand words! You'd win NaNoWriMo."},
    {"key": "words_75k",   "threshold": 75_000,    "name": "Standard Novel",    "icon": "📚", "desc": "Seventy-five thousand words — a full standard novel."},
    {"key": "words_100k",  "threshold": 100_000,   "name": "Epic Novel",        "icon": "🐉", "desc": "One hundred thousand words. Epic territory."},
    {"key": "words_150k",  "threshold": 150_000,   "name": "Long Epic",         "icon": "⚔",  "desc": "One hundred fifty thousand words. A long epic."},
    {"key": "words_200k",  "threshold": 200_000,   "name": "Doorstopper",       "icon": "🚪", "desc": "Two hundred thousand words. A true doorstopper."},
    {"key": "words_300k",  "threshold": 300_000,   "name": "Series Starter",    "icon": "🌟", "desc": "Three hundred thousand words. This could be a series."},
    {"key": "words_500k",  "threshold": 500_000,   "name": "Prolific",          "icon": "💎", "desc": "Half a million words. You are prolific."},
    {"key": "words_1m",    "threshold": 1_000_000, "name": "Million Words",     "icon": "👑", "desc": "One. Million. Words. Legendary."},
]


def _total_words() -> int:
    with read_session() as s:
        result = s.scalar(
            select(func.coalesce(func.sum(Chapter.word_count), 0)).where(
                Chapter.project_id == current_project_id(s)
            )
        )
        return int(result or 0)


def _get_celebrated_keys() -> set[str]:
    with read_session() as s:
        rows = list(s.scalars(
            select(MilestoneCelebration).where(
                MilestoneCelebration.project_id == current_project_id(s)
            )
        ))
        return {r.milestone_key for r in rows}


def check_and_celebrate() -> dict[str, Any]:
    """Check milestones; persist any newly-reached ones.

    Returns: {
        "total_words": int,
        "milestones": [...],  # all milestones with reached status
        "newly_celebrated": [...],  # milestones reached since last check
        "next_milestone": {...} or None,
    }
    """
    total = _total_words()
    celebrated = _get_celebrated_keys()
    newly: list[dict[str, Any]] = []

    for m in MILESTONES:
        if m["threshold"] <= total and m["key"] not in celebrated:
            # Newly reached — persist
            with write_transaction() as s:
                s.add(MilestoneCelebration(
                    id=new_uuid(),
                    project_id=current_project_id(s),
                    milestone_key=m["key"],
                    threshold=m["threshold"],
                    reached_at=now_utc(),
                ))
            newly.append({
                **m,
                "reached": True,
                "reached_at": now_utc().isoformat(),
            })

    # Build full status
    celebrated = _get_celebrated_keys()  # refresh
    all_milestones: list[dict[str, Any]] = []
    for m in MILESTONES:
        is_reached = m["threshold"] <= total
        all_milestones.append({
            **m,
            "reached": is_reached,
            "celebrated": m["key"] in celebrated,
        })

    # Find next milestone (first not reached)
    next_m = next((m for m in all_milestones if not m["reached"]), None)

    return {
        "total_words": total,
        "milestones": all_milestones,
        "newly_celebrated": newly,
        "next_milestone": next_m,
        "progress_to_next": (
            round(total / next_m["threshold"] * 100, 1) if next_m else 100
        ),
        "words_to_next": (next_m["threshold"] - total) if next_m else 0,
    }


def get_status() -> dict[str, Any]:
    """Get milestone status without celebrating new ones."""
    total = _total_words()
    celebrated = _get_celebrated_keys()
    all_milestones: list[dict[str, Any]] = []
    for m in MILESTONES:
        is_reached = m["threshold"] <= total
        all_milestones.append({
            **m,
            "reached": is_reached,
            "celebrated": m["key"] in celebrated,
        })
    next_m = next((m for m in all_milestones if not m["reached"]), None)
    return {
        "total_words": total,
        "milestones": all_milestones,
        "newly_celebrated": [],
        "next_milestone": next_m,
        "progress_to_next": (
            round(total / next_m["threshold"] * 100, 1) if next_m else 100
        ),
        "words_to_next": (next_m["threshold"] - total) if next_m else 0,
    }
