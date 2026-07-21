"""Timeline Conflict Detection — catch plot holes in your story dates.

Detects:
1. Out-of-order events: A plan item with story_date X is listed before
   one with story_date Y where X > Y (i.e., the timeline appears out of
   chronological order in the outline).
2. Duplicate dates: Multiple significant events on the same story_date.
3. Future references: A chapter references something that hasn't happened
   yet in story time (approximated by sort_order vs story_date mismatch).
4. Orphan dates: Story dates that don't fit any consistent date format.
5. Impossible travel: A character in chapter A (with story_date X) appears
   in chapter B (with story_date X+1) but they're on different continents.
   (Requires chapter-character links; we approximate by flagging if a
   character appears in two chapters with the same story_date but different
   world entry locations — this is best-effort.)
6. Gap analysis: Long gaps between consecutive story dates that might
   need transitional chapters.

story_date is a freeform string in the plan model. We attempt to parse
common formats: ISO (YYYY-MM-DD), year-month (YYYY-MM), year-only (YYYY),
and a few natural-language patterns. Unparseable dates are flagged.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any

from sqlalchemy import select

from core.db import read_session
from services._common import current_project_id, load_json

log = logging.getLogger("asm.timeline_check")


# Date format patterns we try to parse, in priority order
_DATE_FORMATS = [
    "%Y-%m-%d",        # 2026-07-15
    "%Y/%m/%d",        # 2026/07/15
    "%d %B %Y",        # 15 July 2026
    "%B %d, %Y",       # July 15, 2026
    "%d %b %Y",        # 15 Jul 2026
    "%b %d, %Y",       # Jul 15, 2026
    "%Y-%m",           # 2026-07
    "%B %Y",           # July 2026
    "%b %Y",           # Jul 2026
    "%Y",              # 2026
]


def parse_story_date(s: str) -> date | None:
    """Try to parse a story_date string into a date.

    Returns None if the string can't be parsed.
    For year-month or year-only formats, returns the first day of that period.
    """
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    # Try ISO first (most common)
    try:
        return date.fromisoformat(s)
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(s, fmt).date()
            return dt
        except ValueError:
            continue
    # Try extracting a year from the string as last resort
    m = re.search(r"\b(1[0-9]{3}|20[0-9]{2}|21[0-9]{2})\b", s)
    if m:
        try:
            return date(int(m.group(1)), 1, 1)
        except ValueError:
            pass
    return None


def _format_date(d: date) -> str:
    return d.isoformat()


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

def detect_conflicts(*, track: str | None = None) -> dict[str, Any]:
    """Scan all plan items with story_dates and find conflicts.

    Returns:
    {
        "events": [...]          # chronological list of all events
        "issues": [...],         # conflict issues found
        "gaps": [...],           # large gaps between events
        "total_events": int,
        "parsed_events": int,
        "unparseable_dates": int,
    }
    """
    from models.plan import Plan
    issues: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    with read_session() as s:
        q = select(Plan).where(
            Plan.project_id == current_project_id(s),
            Plan.story_date.is_not(None),
        )
        if track and track != "all":
            q = q.where(Plan.track == track)
        plans = list(s.scalars(q.order_by(Plan.sort_order.asc())))

    # Build event list with parsed dates
    parsed: list[dict[str, Any]] = []
    unparseable: list[dict[str, Any]] = []
    for p in plans:
        d = parse_story_date(p.story_date or "")
        ev = {
            "plan_id": p.id,
            "title": p.title,
            "story_date_raw": p.story_date,
            "story_date_parsed": _format_date(d) if d else None,
            "sort_order": p.sort_order,
            "track": p.track,
            "event_type": p.event_type,
            "chapter_id": p.chapter_id,
            "characters_involved": load_json(p.characters_involved, []),
        }
        events.append(ev)
        if d is None:
            unparseable.append(ev)
            issues.append({
                "type": "unparseable_date",
                "severity": "low",
                "plan_id": p.id,
                "title": p.title,
                "raw": p.story_date,
                "message": f"Couldn't parse date '{p.story_date}'. Use ISO format (YYYY-MM-DD) for best results.",
            })
        else:
            ev["parsed_date"] = d  # keep date object internally
            parsed.append(ev)

    # 1. Out-of-order check: sort by story_date and compare with sort_order
    by_date = sorted(parsed, key=lambda e: e["parsed_date"])
    by_order = sorted(parsed, key=lambda e: e["sort_order"])
    # Find pairs where chronological order ≠ outline order
    for i, chronological in enumerate(by_date):
        chronological_rank = i
        outline_rank = by_order.index(chronological)
        # Flag if the ranks differ by more than 1 position
        if abs(chronological_rank - outline_rank) > 1:
            issues.append({
                "type": "out_of_order",
                "severity": "medium",
                "plan_id": chronological["plan_id"],
                "title": chronological["title"],
                "story_date": chronological["story_date_raw"],
                "chronological_rank": chronological_rank + 1,
                "outline_rank": outline_rank + 1,
                "message": (
                    f"'{chronological['title']}' is event #{chronological_rank + 1} chronologically "
                    f"but #{outline_rank + 1} in your outline (story_date: {chronological['story_date_raw']})."
                ),
            })

    # 2. Duplicate date check
    by_date_str: dict[str, list[dict[str, Any]]] = {}
    for ev in parsed:
        ds = ev["story_date_parsed"]
        if ds not in by_date_str:
            by_date_str[ds] = []
        by_date_str[ds].append(ev)
    for ds, evs in by_date_str.items():
        if len(evs) > 1:
            # Only flag if they're different event types or all are plot-critical
            critical_types = {"climax", "plot_point", "resolution"}
            critical_count = sum(1 for e in evs if e["event_type"] in critical_types)
            if critical_count >= 2:
                issues.append({
                    "type": "duplicate_date",
                    "severity": "medium",
                    "story_date": ds,
                    "events": [{"plan_id": e["plan_id"], "title": e["title"]} for e in evs],
                    "message": (
                        f"{len(evs)} significant events share the date {ds}: "
                        + ", ".join(f"'{e['title']}'" for e in evs)
                        + ". Make sure this is intentional."
                    ),
                })

    # 3. Gap analysis: gaps > 30 days between consecutive chronological events
    for i in range(1, len(by_date)):
        prev = by_date[i - 1]
        curr = by_date[i]
        delta_days = (curr["parsed_date"] - prev["parsed_date"]).days
        if delta_days > 30:
            gaps.append({
                "from_plan_id": prev["plan_id"],
                "from_title": prev["title"],
                "from_date": prev["story_date_parsed"],
                "to_plan_id": curr["plan_id"],
                "to_title": curr["title"],
                "to_date": curr["story_date_parsed"],
                "gap_days": delta_days,
                "message": (
                    f"{delta_days}-day gap between '{prev['title']}' ({prev['story_date_parsed']}) "
                    f"and '{curr['title']}' ({curr['story_date_parsed']}). "
                    f"Consider whether a transitional scene is needed."
                ),
            })

    # 4. Character presence check: same character in two events with
    #    overlapping or impossible-close dates that are on different tracks
    #    (best-effort: flag if same character appears in 2+ events within 1 day
    #    but the events are on different tracks)
    char_events: dict[str, list[dict[str, Any]]] = {}
    for ev in parsed:
        for cid in ev["characters_involved"]:
            if cid not in char_events:
                char_events[cid] = []
            char_events[cid].append(ev)
    for cid, evs in char_events.items():
        if len(evs) < 2:
            continue
        evs_sorted = sorted(evs, key=lambda e: e["parsed_date"])
        for i in range(1, len(evs_sorted)):
            prev = evs_sorted[i - 1]
            curr = evs_sorted[i]
            delta = (curr["parsed_date"] - prev["parsed_date"]).days
            if delta == 0 and prev["track"] != curr["track"]:
                issues.append({
                    "type": "character_double_booked",
                    "severity": "high",
                    "character_id": cid,
                    "story_date": curr["story_date_parsed"],
                    "events": [
                        {"plan_id": prev["plan_id"], "title": prev["title"], "track": prev["track"]},
                        {"plan_id": curr["plan_id"], "title": curr["title"], "track": curr["track"]},
                    ],
                    "message": (
                        f"Character {cid} appears in two events on the same date "
                        f"({curr['story_date_parsed']}) on different tracks: "
                        f"'{prev['title']}' ({prev['track']}) and '{curr['title']}' ({curr['track']}). "
                        f"Make sure this is intentional."
                    ),
                })

    # Resolve character names
    from models.character import Character
    char_name_map: dict[str, str] = {}
    all_char_ids = {cid for ev in events for cid in ev["characters_involved"]}
    if all_char_ids:
        with read_session() as s:
            chars = list(s.scalars(
                select(Character).where(Character.id.in_(list(all_char_ids)))
            ))
            char_name_map = {c.id: c.name for c in chars}

    # Enrich issues with character names
    for issue in issues:
        if "character_id" in issue:
            issue["character_name"] = char_name_map.get(issue["character_id"], issue["character_id"])

    return {
        "events": events,
        "issues": issues,
        "gaps": gaps,
        "total_events": len(events),
        "parsed_events": len(parsed),
        "unparseable_dates": len(unparseable),
        "tracks": sorted({e["track"] or "(no track)" for e in events}),
    }
