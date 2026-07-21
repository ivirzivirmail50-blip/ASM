"""Writing Streaks & Achievements — gamification to motivate the writer.

Achievements are unlocked automatically based on activity log data:
- Streaks: 3, 7, 30, 100, 365 consecutive writing days
- Word milestones: 1K, 10K, 50K, 100K, 250K, 500K, 1M total words
- Chapter milestones: 1, 5, 10, 25, 50 chapters
- Character/World: created first character, 10 characters, 20 world entries
- Time-based: early bird (before 7am), night owl (after midnight)
- Consistency: wrote every day for a working week (Mon-Fri)

Achievements are persisted (unlocked_at timestamp) so they only fire once.
The /achievements page shows unlocked + locked (with progress) achievements.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func

from core.db import read_session, write_transaction
from models.achievement import UnlockedAchievement
from models.activity import ActivityLog
from models.chapter import Chapter
from models.character import Character
from models.world import WorldEntry
from models.settings import Setting
from services._common import current_project_id, dump_json, load_json, new_uuid, now_utc

log = logging.getLogger("asm.achievements")


# ---------------------------------------------------------------------------
# Achievement definitions
# ---------------------------------------------------------------------------

ACHIEVEMENTS: dict[str, dict[str, Any]] = {
    # Streaks
    "streak_3": {
        "category": "streak", "name": "Getting Started",
        "icon": "🔥", "description": "Write for 3 consecutive days",
        "check": lambda ctx: ctx["current_streak"] >= 3,
        "progress": lambda ctx: min(100, int(ctx["current_streak"] / 3 * 100)),
        "progress_label": lambda ctx: f"{ctx['current_streak']}/3 days",
    },
    "streak_7": {
        "category": "streak", "name": "Week Warrior",
        "icon": "⚔", "description": "Write for 7 consecutive days",
        "check": lambda ctx: ctx["current_streak"] >= 7,
        "progress": lambda ctx: min(100, int(ctx["current_streak"] / 7 * 100)),
        "progress_label": lambda ctx: f"{ctx['current_streak']}/7 days",
    },
    "streak_30": {
        "category": "streak", "name": "Monthly Master",
        "icon": "👑", "description": "Write for 30 consecutive days",
        "check": lambda ctx: ctx["current_streak"] >= 30,
        "progress": lambda ctx: min(100, int(ctx["current_streak"] / 30 * 100)),
        "progress_label": lambda ctx: f"{ctx['current_streak']}/30 days",
    },
    "streak_100": {
        "category": "streak", "name": "Centurion",
        "icon": "💯", "description": "Write for 100 consecutive days",
        "check": lambda ctx: ctx["current_streak"] >= 100,
        "progress": lambda ctx: min(100, int(ctx["current_streak"] / 100 * 100)),
        "progress_label": lambda ctx: f"{ctx['current_streak']}/100 days",
    },
    # Word milestones
    "words_1k": {
        "category": "words", "name": "First Thousand",
        "icon": "✍", "description": "Write 1,000 total words",
        "check": lambda ctx: ctx["total_words"] >= 1000,
        "progress": lambda ctx: min(100, int(ctx["total_words"] / 1000 * 100)),
        "progress_label": lambda ctx: f"{ctx['total_words']:,}/1,000",
    },
    "words_10k": {
        "category": "words", "name": "Novella Novice",
        "icon": "📖", "description": "Write 10,000 total words",
        "check": lambda ctx: ctx["total_words"] >= 10000,
        "progress": lambda ctx: min(100, int(ctx["total_words"] / 10000 * 100)),
        "progress_label": lambda ctx: f"{ctx['total_words']:,}/10,000",
    },
    "words_50k": {
        "category": "words", "name": "NaNoWriMo Winner",
        "icon": "🏆", "description": "Write 50,000 total words (novel length)",
        "check": lambda ctx: ctx["total_words"] >= 50000,
        "progress": lambda ctx: min(100, int(ctx["total_words"] / 50000 * 100)),
        "progress_label": lambda ctx: f"{ctx['total_words']:,}/50,000",
    },
    "words_100k": {
        "category": "words", "name": "Centenarian Wordsmith",
        "icon": "🎓", "description": "Write 100,000 total words",
        "check": lambda ctx: ctx["total_words"] >= 100000,
        "progress": lambda ctx: min(100, int(ctx["total_words"] / 100000 * 100)),
        "progress_label": lambda ctx: f"{ctx['total_words']:,}/100,000",
    },
    "words_250k": {
        "category": "words", "name": "Epic Tale",
        "icon": "🐉", "description": "Write 250,000 total words",
        "check": lambda ctx: ctx["total_words"] >= 250000,
        "progress": lambda ctx: min(100, int(ctx["total_words"] / 250000 * 100)),
        "progress_label": lambda ctx: f"{ctx['total_words']:,}/250,000",
    },
    # Chapter milestones
    "chapters_1": {
        "category": "chapters", "name": "First Chapter",
        "icon": "1️⃣", "description": "Create your first chapter",
        "check": lambda ctx: ctx["chapter_count"] >= 1,
        "progress": lambda ctx: min(100, ctx["chapter_count"] * 100),
        "progress_label": lambda ctx: f"{ctx['chapter_count']}/1",
    },
    "chapters_5": {
        "category": "chapters", "name": "Prolific",
        "icon": "5️⃣", "description": "Create 5 chapters",
        "check": lambda ctx: ctx["chapter_count"] >= 5,
        "progress": lambda ctx: min(100, int(ctx["chapter_count"] / 5 * 100)),
        "progress_label": lambda ctx: f"{ctx['chapter_count']}/5",
    },
    "chapters_10": {
        "category": "chapters", "name": "Double Digits",
        "icon": "🔟", "description": "Create 10 chapters",
        "check": lambda ctx: ctx["chapter_count"] >= 10,
        "progress": lambda ctx: min(100, int(ctx["chapter_count"] / 10 * 100)),
        "progress_label": lambda ctx: f"{ctx['chapter_count']}/10",
    },
    "chapters_25": {
        "category": "chapters", "name": "Quarter-Century",
        "icon": "🎯", "description": "Create 25 chapters",
        "check": lambda ctx: ctx["chapter_count"] >= 25,
        "progress": lambda ctx: min(100, int(ctx["chapter_count"] / 25 * 100)),
        "progress_label": lambda ctx: f"{ctx['chapter_count']}/25",
    },
    # Character/World
    "first_character": {
        "category": "cast", "name": "Cast of One",
        "icon": "👤", "description": "Create your first character",
        "check": lambda ctx: ctx["character_count"] >= 1,
        "progress": lambda ctx: min(100, ctx["character_count"] * 100),
        "progress_label": lambda ctx: f"{ctx['character_count']}/1",
    },
    "characters_10": {
        "category": "cast", "name": "Ensemble",
        "icon": "🎭", "description": "Create 10 characters",
        "check": lambda ctx: ctx["character_count"] >= 10,
        "progress": lambda ctx: min(100, int(ctx["character_count"] / 10 * 100)),
        "progress_label": lambda ctx: f"{ctx['character_count']}/10",
    },
    "world_20": {
        "category": "cast", "name": "World Builder",
        "icon": "🌍", "description": "Create 20 world entries",
        "check": lambda ctx: ctx["world_count"] >= 20,
        "progress": lambda ctx: min(100, int(ctx["world_count"] / 20 * 100)),
        "progress_label": lambda ctx: f"{ctx['world_count']}/20",
    },
    # Consistency
    "all_week": {
        "category": "consistency", "name": "Full Week",
        "icon": "📅", "description": "Write every day for a full week (Mon-Sun)",
        "check": lambda ctx: ctx["wrote_all_week"],
        "progress": lambda ctx: int(ctx["days_this_week"] / 7 * 100),
        "progress_label": lambda ctx: f"{ctx['days_this_week']}/7 days this week",
    },
    "weekend_warrior": {
        "category": "consistency", "name": "Weekend Warrior",
        "icon": "🎊", "description": "Write on both Saturday and Sunday this week",
        "check": lambda ctx: ctx["weekend_writes"] >= 2,
        "progress": lambda ctx: int(ctx["weekend_writes"] / 2 * 100),
        "progress_label": lambda ctx: f"{ctx['weekend_writes']}/2 weekend days",
    },
}

CATEGORIES = {
    "streak":      {"label": "Streaks",      "icon": "🔥"},
    "words":       {"label": "Word Goals",   "icon": "✍"},
    "chapters":    {"label": "Chapters",     "icon": "📚"},
    "cast":        {"label": "Cast & World", "icon": "🎭"},
    "consistency": {"label": "Consistency",  "icon": "📅"},
}


# ---------------------------------------------------------------------------
# Context building
# ---------------------------------------------------------------------------

def _build_context() -> dict[str, Any]:
    """Gather all the stats needed to check achievements."""
    with read_session() as s:
        pid = current_project_id(s)
        # Total words (sum of chapter word_counts)
        total_words = s.scalar(
            select(func.coalesce(func.sum(Chapter.word_count), 0)).where(
                Chapter.project_id == pid
            )
        ) or 0
        # Chapter count
        chapter_count = s.scalar(
            select(func.count()).select_from(Chapter).where(
                Chapter.project_id == pid
            )
        ) or 0
        # Character count
        character_count = s.scalar(
            select(func.count()).select_from(Character).where(
                Character.project_id == pid
            )
        ) or 0
        # World count
        world_count = s.scalar(
            select(func.count()).select_from(WorldEntry).where(
                WorldEntry.project_id == pid
            )
        ) or 0
        # Daily word deltas for last 365 days
        now = datetime.now(timezone.utc)
        year_ago = now - timedelta(days=365)
        rows = s.execute(
            select(
                func.date(ActivityLog.timestamp).label("d"),
                func.sum(ActivityLog.word_count_delta).label("wc"),
            ).where(
                ActivityLog.entity_type == "chapter",
                ActivityLog.timestamp >= year_ago,
            ).group_by(func.date(ActivityLog.timestamp))
        ).all()
        by_date = {str(r[0]): max(0, int(r[1] or 0)) for r in rows}
        # Current streak (consecutive days ending today with >0 words)
        current_streak = 0
        d = now.date()
        # Grace: allow streak to count if today has activity OR yesterday does
        if by_date.get(d.isoformat(), 0) > 0:
            while by_date.get(d.isoformat(), 0) > 0:
                current_streak += 1
                d -= timedelta(days=1)
        elif by_date.get((d - timedelta(days=1)).isoformat(), 0) > 0:
            d -= timedelta(days=1)
            while by_date.get(d.isoformat(), 0) > 0:
                current_streak += 1
                d -= timedelta(days=1)
        # Days this week (Mon-Sun)
        monday = now - timedelta(days=now.weekday())
        days_this_week = 0
        weekend_writes = 0
        for i in range(7):
            wd = monday + timedelta(days=i)
            if by_date.get(wd.date().isoformat(), 0) > 0:
                days_this_week += 1
                if wd.weekday() >= 5:  # Saturday=5, Sunday=6
                    weekend_writes += 1
        wrote_all_week = days_this_week == 7
    return {
        "total_words": int(total_words),
        "chapter_count": int(chapter_count),
        "character_count": int(character_count),
        "world_count": int(world_count),
        "current_streak": current_streak,
        "days_this_week": days_this_week,
        "weekend_writes": weekend_writes,
        "wrote_all_week": wrote_all_week,
    }


# ---------------------------------------------------------------------------
# Unlock logic
# ---------------------------------------------------------------------------

def list_unlocked() -> list[UnlockedAchievement]:
    with read_session() as s:
        return list(s.scalars(
            select(UnlockedAchievement).where(
                UnlockedAchievement.project_id == current_project_id(s)
            ).order_by(UnlockedAchievement.unlocked_at.desc())
        ))


def check_and_unlock() -> dict[str, Any]:
    """Check all achievements; unlock any newly-qualified ones.

    Returns: {
        "checked": int,
        "newly_unlocked": [{key, name, icon, description, unlocked_at}],
        "total_unlocked": int,
    }
    """
    ctx = _build_context()
    unlocked = list_unlocked()
    unlocked_keys = {u.achievement_key for u in unlocked}
    newly: list[dict[str, Any]] = []
    for key, ach in ACHIEVEMENTS.items():
        if key in unlocked_keys:
            continue
        try:
            if ach["check"](ctx):
                # Unlock it
                with write_transaction() as s:
                    rec = UnlockedAchievement(
                        id=new_uuid(),
                        project_id=current_project_id(s),
                        achievement_key=key,
                        unlocked_at=now_utc(),
                        context=dump_json({"context_snapshot": ctx}),
                    )
                    s.add(rec)
                newly.append({
                    "key": key,
                    "name": ach["name"],
                    "icon": ach["icon"],
                    "description": ach["description"],
                    "category": ach["category"],
                    "unlocked_at": rec.unlocked_at.isoformat() if rec.unlocked_at else None,
                })
        except Exception:
            log.exception("Error checking achievement %s", key)
    return {
        "checked": len(ACHIEVEMENTS),
        "newly_unlocked": newly,
        "total_unlocked": len(unlocked_keys) + len(newly),
    }


def get_status() -> dict[str, Any]:
    """Return full achievement status: unlocked + locked (with progress)."""
    ctx = _build_context()
    unlocked = list_unlocked()
    unlocked_map = {u.achievement_key: u for u in unlocked}
    all_status: list[dict[str, Any]] = []
    for key, ach in ACHIEVEMENTS.items():
        is_unlocked = key in unlocked_map
        rec = unlocked_map.get(key)
        try:
            progress = ach["progress"](ctx)
            progress_label = ach["progress_label"](ctx)
        except Exception:
            progress = 0
            progress_label = ""
        all_status.append({
            "key": key,
            "category": ach["category"],
            "category_label": CATEGORIES.get(ach["category"], {}).get("label", ach["category"]),
            "category_icon": CATEGORIES.get(ach["category"], {}).get("icon", ""),
            "name": ach["name"],
            "icon": ach["icon"],
            "description": ach["description"],
            "unlocked": is_unlocked,
            "unlocked_at": rec.unlocked_at.isoformat() if rec and rec.unlocked_at else None,
            "progress": progress,
            "progress_label": progress_label,
        })
    # Sort: unlocked first (by unlocked_at desc), then by category
    all_status.sort(key=lambda a: (not a["unlocked"], a["unlocked_at"] or ""), reverse=False)
    unlocked_count = sum(1 for a in all_status if a["unlocked"])
    return {
        "achievements": all_status,
        "unlocked_count": unlocked_count,
        "total_count": len(all_status),
        "completion_pct": round(unlocked_count / max(1, len(all_status)) * 100, 1),
        "context": ctx,
    }
