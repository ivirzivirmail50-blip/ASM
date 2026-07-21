"""Manuscript Snapshot Diff — compare manuscript state between two points in time.

Uses chapter_versions (snapshots) and activity_log to reconstruct what the
manuscript looked like at a given date/time, then diffs two snapshots:

- Added chapters (created between the two dates)
- Removed chapters (deleted between the two dates — best-effort via activity log)
- Modified chapters (content changed — shows word count delta + diff excerpt)
- Net word count change

The "snapshot" is reconstructed by:
1. For each chapter, find the most recent version at or before the target date
2. If no version exists at that date, the chapter didn't exist yet
3. Compare the two reconstructed states

Output: HTML, TXT, or JSON summary.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from core.db import read_session
from models.chapter import Chapter, ChapterVersion
from models.activity import ActivityLog
from services._common import current_project_id, load_json

log = logging.getLogger("asm.snapshot_diff")


def _reconstruct_at(target_date: datetime) -> dict[str, dict[str, Any]]:
    """Reconstruct the manuscript state at a given datetime.

    Returns {chapter_id: {title, content, word_count, version_number}}.
    Only includes chapters that existed at that time.
    """
    with read_session() as s:
        pid = current_project_id(s)
        # All chapters currently in the project
        chapters = list(s.scalars(
            select(Chapter).where(Chapter.project_id == pid)
        ))
        # For deleted chapters, we can't recover content, but we can detect
        # them via activity log (action='deleted'). For now, only reconstruct
        # existing chapters using their version history.
        result: dict[str, dict[str, Any]] = {}
        for ch in chapters:
            # Find the most recent version at or before target_date
            version = s.scalar(
                select(ChapterVersion).where(
                    ChapterVersion.chapter_id == ch.id,
                    ChapterVersion.uploaded_at <= target_date,
                ).order_by(ChapterVersion.version_number.desc())
            )
            if version:
                result[ch.id] = {
                    "title": ch.title,  # use current title (we don't version titles)
                    "content": version.content or "",
                    "word_count": version.word_count or 0,
                    "version_number": version.version_number,
                    "version_date": version.uploaded_at.isoformat() if version.uploaded_at else None,
                }
            elif ch.created_at and ch.created_at.replace(tzinfo=timezone.utc) <= target_date:
                # Chapter existed but no version snapshot — use current content as fallback
                result[ch.id] = {
                    "title": ch.title,
                    "content": ch.content or "",
                    "word_count": ch.word_count or 0,
                    "version_number": 0,
                    "version_date": ch.created_at.isoformat() if ch.created_at else None,
                }
        return result


def get_available_dates() -> list[dict[str, Any]]:
    """Return all dates that have version snapshots (for the date picker)."""
    with read_session() as s:
        versions = list(s.scalars(
            select(ChapterVersion).order_by(ChapterVersion.uploaded_at.desc())
        ))
        seen_dates: set[str] = set()
        dates: list[dict[str, Any]] = []
        for v in versions:
            if not v.uploaded_at:
                continue
            d = v.uploaded_at.date().isoformat()
            if d in seen_dates:
                continue
            seen_dates.add(d)
            dates.append({
                "date": d,
                "datetime": v.uploaded_at.isoformat(),
                "label": v.uploaded_at.strftime("%Y-%m-%d %H:%M"),
            })
        return dates


def compute_diff(from_date: datetime, to_date: datetime) -> dict[str, Any]:
    """Compute the diff between two manuscript snapshots."""
    if from_date > to_date:
        from_date, to_date = to_date, from_date

    state_from = _reconstruct_at(from_date)
    state_to = _reconstruct_at(to_date)

    from_ids = set(state_from.keys())
    to_ids = set(state_to.keys())

    added_ids = to_ids - from_ids
    removed_ids = from_ids - to_ids
    common_ids = from_ids & to_ids

    added: list[dict[str, Any]] = []
    for cid in added_ids:
        ch = state_to[cid]
        added.append({
            "chapter_id": cid,
            "title": ch["title"],
            "word_count": ch["word_count"],
        })

    removed: list[dict[str, Any]] = []
    for cid in removed_ids:
        ch = state_from[cid]
        removed.append({
            "chapter_id": cid,
            "title": ch["title"],
            "word_count": ch["word_count"],
        })

    modified: list[dict[str, Any]] = []
    for cid in common_ids:
        old = state_from[cid]
        new = state_to[cid]
        if old["content"] != new["content"] or old["word_count"] != new["word_count"]:
            wc_delta = new["word_count"] - old["word_count"]
            # Find the first differing line for a preview
            old_lines = old["content"].split("\n")
            new_lines = new["content"].split("\n")
            diff_preview = _find_first_diff(old_lines, new_lines)
            modified.append({
                "chapter_id": cid,
                "title": new["title"],
                "old_word_count": old["word_count"],
                "new_word_count": new["word_count"],
                "word_count_delta": wc_delta,
                "old_version": old["version_number"],
                "new_version": new["version_number"],
                "diff_preview": diff_preview,
            })

    total_words_from = sum(c["word_count"] for c in state_from.values())
    total_words_to = sum(c["word_count"] for c in state_to.values())

    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "from_chapter_count": len(state_from),
        "to_chapter_count": len(state_to),
        "added": added,
        "removed": removed,
        "modified": modified,
        "added_count": len(added),
        "removed_count": len(removed),
        "modified_count": len(modified),
        "total_words_from": total_words_from,
        "total_words_to": total_words_to,
        "net_word_change": total_words_to - total_words_from,
    }


def _find_first_diff(old_lines: list[str], new_lines: list[str]) -> dict[str, str]:
    """Find the first line that differs between old and new."""
    max_len = max(len(old_lines), len(new_lines))
    for i in range(max_len):
        old_line = old_lines[i] if i < len(old_lines) else ""
        new_line = new_lines[i] if i < len(new_lines) else ""
        if old_line != new_line:
            return {
                "line_number": i + 1,
                "old": old_line[:200],
                "new": new_line[:200],
            }
    return {"line_number": 0, "old": "", "new": ""}


def render_diff_html(diff: dict[str, Any]) -> str:
    """Render the diff as HTML."""
    parts = [f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>Manuscript Diff</title>
<style>
body {{ font-family: Georgia, serif; max-width: 900px; margin: 2rem auto; padding: 1rem; line-height: 1.7; }}
h1 {{ color: #6366f1; }}
h2 {{ border-bottom: 2px solid #6366f1; padding-bottom: 0.3rem; margin-top: 2rem; }}
.added {{ color: #22c55e; }}
.removed {{ color: #ef4444; }}
.modified {{ color: #f59e0b; }}
.summary {{ background: #f1f3f9; padding: 1rem; border-radius: 6px; margin: 1rem 0; }}
.chapter {{ border: 1px solid #ddd; border-radius: 6px; padding: 1rem; margin: 0.5rem 0; }}
.diff-preview {{ background: #f9f9f9; padding: 0.5rem; border-radius: 4px; font-family: monospace; font-size: 0.85rem; }}
.delta-pos {{ color: #22c55e; font-weight: bold; }}
.delta-neg {{ color: #ef4444; font-weight: bold; }}
</style></head><body>"""]

    parts.append(f"<h1>📖 Manuscript Diff</h1>")
    parts.append(f"<p><strong>From:</strong> {diff['from_date']}<br><strong>To:</strong> {diff['to_date']}</p>")

    parts.append("<div class='summary'>")
    parts.append(f"<strong>Summary:</strong> ")
    parts.append(f"{diff['from_chapter_count']} → {diff['to_chapter_count']} chapters, ")
    delta = diff['net_word_change']
    delta_class = "delta-pos" if delta >= 0 else "delta-neg"
    parts.append(f"<span class='{delta_class}'>{'+' if delta >= 0 else ''}{delta:,}</span> net words")
    parts.append("</div>")

    if diff["added"]:
        parts.append(f"<h2 class='added'>+ Added Chapters ({len(diff['added'])})</h2>")
        for ch in diff["added"]:
            parts.append(f"<div class='chapter'><strong>{ch['title']}</strong> — {ch['word_count']} words</div>")

    if diff["removed"]:
        parts.append(f"<h2 class='removed'>− Removed Chapters ({len(diff['removed'])})</h2>")
        for ch in diff["removed"]:
            parts.append(f"<div class='chapter'><strong>{ch['title']}</strong> — was {ch['word_count']} words</div>")

    if diff["modified"]:
        parts.append(f"<h2 class='modified'>~ Modified Chapters ({len(diff['modified'])})</h2>")
        for ch in diff["modified"]:
            delta = ch["word_count_delta"]
            delta_class = "delta-pos" if delta >= 0 else "delta-neg"
            parts.append(f"<div class='chapter'>")
            parts.append(f"<strong>{ch['title']}</strong> ")
            parts.append(f"<span class='{delta_class}'>({'+' if delta >= 0 else ''}{delta} words)</span><br>")
            parts.append(f"<span class='text-mute'>v{ch['old_version']} → v{ch['new_version']}</span>")
            if ch["diff_preview"]["line_number"] > 0:
                parts.append(f"<div class='diff-preview'>")
                parts.append(f"<div class='removed'>- L{ch['diff_preview']['line_number']}: {ch['diff_preview']['old']}</div>")
                parts.append(f"<div class='added'>+ L{ch['diff_preview']['line_number']}: {ch['diff_preview']['new']}</div>")
                parts.append(f"</div>")
            parts.append("</div>")

    if not (diff["added"] or diff["removed"] or diff["modified"]):
        parts.append("<p>No changes between these dates.</p>")

    parts.append("</body></html>")
    return "".join(parts)
