"""Bulk Find & Replace across chapters — preview, scope, regex support.

Workflow:
1. preview(pattern, replacement, options) — returns list of matches with
   context per chapter, without modifying anything.
2. apply(pattern, replacement, options) — performs the replacement on
   matching chapters and snapshots each as a new version.

Options:
- use_regex: treat pattern as Python regex (else plain text)
- case_sensitive: case sensitivity (only when not regex)
- whole_word: require word boundaries (only when not regex)
- scope_chapter_ids: list of chapter IDs to scope (empty = all)
- scope_status: only chapters with this status
- max_replacements_per_chapter: safety cap (default 1000)
"""
from __future__ import annotations

import logging
import re
from typing import Any

from core.db import read_session, write_transaction
from core.errors import ValidationError
from services._common import current_project_id, log_activity

log = logging.getLogger("asm.find_replace")


def _build_pattern(
    pattern: str, *,
    use_regex: bool, case_sensitive: bool, whole_word: bool,
) -> re.Pattern:
    """Compile the search pattern into a regex."""
    if use_regex:
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            return re.compile(pattern, flags)
        except re.error as e:
            raise ValidationError(f"Invalid regex: {e}")
    else:
        # Plain text — escape, optionally wrap in word boundaries
        esc = re.escape(pattern)
        if whole_word:
            esc = r"\b" + esc + r"\b"
        flags = 0 if case_sensitive else re.IGNORECASE
        return re.compile(esc, flags)


def _find_matches(
    text: str, pattern: re.Pattern, replacement: str,
    max_per_chapter: int = 1000,
) -> list[dict[str, Any]]:
    """Return list of {position, before, after, context} for each match."""
    out: list[dict[str, Any]] = []
    for i, m in enumerate(pattern.finditer(text)):
        if i >= max_per_chapter:
            out.append({
                "position": -1, "before": "", "after": "",
                "context": f"... truncated at {max_per_chapter} matches ...",
                "truncated": True,
            })
            break
        start, end = m.start(), m.end()
        before = text[start:end]
        # Apply replacement (handles backreferences \1, \g<name>)
        try:
            after = pattern.sub(replacement, before, count=1)
        except re.error as e:
            raise ValidationError(f"Invalid replacement: {e}")
        # Extract surrounding context (50 chars each side)
        ctx_start = max(0, start - 50)
        ctx_end = min(len(text), end + 50)
        ctx = text[ctx_start:ctx_end].replace("\n", " ").replace("\r", "")
        prefix = "…" if ctx_start > 0 else ""
        suffix = "…" if ctx_end < len(text) else ""
        out.append({
            "position": start,
            "before": before,
            "after": after,
            "context": f"{prefix}{ctx}{suffix}",
            "truncated": False,
        })
    return out


def preview(
    pattern: str, replacement: str, *,
    use_regex: bool = False, case_sensitive: bool = False,
    whole_word: bool = False,
    scope_chapter_ids: list[str] | None = None,
    scope_status: str | None = None,
    max_per_chapter: int = 1000,
) -> dict[str, Any]:
    """Find matches across chapters without modifying anything."""
    if not pattern:
        raise ValidationError("Pattern required.")
    if len(pattern) > 500:
        raise ValidationError("Pattern too long (≤ 500 chars).")
    if len(replacement) > 500:
        raise ValidationError("Replacement too long (≤ 500 chars).")
    regex = _build_pattern(
        pattern, use_regex=use_regex,
        case_sensitive=case_sensitive, whole_word=whole_word,
    )
    from models.chapter import Chapter
    with read_session() as s:
        q = s.query(Chapter).filter_by(project_id=current_project_id(s))
        if scope_chapter_ids:
            q = q.filter(Chapter.id.in_(scope_chapter_ids))
        if scope_status and scope_status != "all":
            q = q.filter_by(status=scope_status)
        chapters = list(q.order_by(Chapter.sort_order.asc()).all())

        chapters_with_matches: list[dict[str, Any]] = []
        total_matches = 0
        for ch in chapters:
            text = ch.content or ""
            matches = _find_matches(text, regex, replacement, max_per_chapter)
            if matches:
                chapters_with_matches.append({
                    "chapter_id": ch.id,
                    "chapter_title": ch.title,
                    "status": ch.status,
                    "match_count": sum(1 for m in matches if not m.get("truncated")),
                    "truncated": any(m.get("truncated") for m in matches),
                    "matches": matches[:10],  # preview only first 10 matches per chapter
                })
                total_matches += sum(1 for m in matches if not m.get("truncated"))
        return {
            "pattern": pattern,
            "replacement": replacement,
            "options": {
                "use_regex": use_regex,
                "case_sensitive": case_sensitive,
                "whole_word": whole_word,
                "scope_status": scope_status,
            },
            "chapters_scanned": len(chapters),
            "chapters_with_matches": len(chapters_with_matches),
            "total_matches": total_matches,
            "results": chapters_with_matches,
        }


def apply(
    pattern: str, replacement: str, *,
    use_regex: bool = False, case_sensitive: bool = False,
    whole_word: bool = False,
    scope_chapter_ids: list[str] | None = None,
    scope_status: str | None = None,
    max_per_chapter: int = 1000,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Apply the replacement across matching chapters.

    Each affected chapter is updated via chapter_service.update_chapter
    so version snapshots are created.
    """
    if dry_run:
        return preview(
            pattern, replacement,
            use_regex=use_regex, case_sensitive=case_sensitive,
            whole_word=whole_word,
            scope_chapter_ids=scope_chapter_ids,
            scope_status=scope_status,
            max_per_chapter=max_per_chapter,
        )
    # Run preview first to validate input
    pre = preview(
        pattern, replacement,
        use_regex=use_regex, case_sensitive=case_sensitive,
        whole_word=whole_word,
        scope_chapter_ids=scope_chapter_ids,
        scope_status=scope_status,
        max_per_chapter=max_per_chapter,
    )
    if not pre["chapters_with_matches"]:
        return {
            "applied": False,
            "chapters_modified": 0,
            "total_replacements": 0,
            "details": [],
        }

    regex = _build_pattern(
        pattern, use_regex=use_regex,
        case_sensitive=case_sensitive, whole_word=whole_word,
    )
    # Import inside function to avoid potential circular imports
    from services.chapter_service import update_chapter
    from models.chapter import Chapter

    # Read fresh copies of chapters to modify
    chapter_ids = [r["chapter_id"] for r in pre["results"]]
    details: list[dict[str, Any]] = []
    total_replacements = 0

    # Re-read with new session, modify each chapter
    with read_session() as s:
        chs = list(s.query(Chapter).filter(Chapter.id.in_(chapter_ids)).all())
        ch_map = {c.id: c for c in chs}

    for r in pre["results"]:
        ch_id = r["chapter_id"]
        ch = ch_map.get(ch_id)
        if not ch:
            continue
        old_content = ch.content or ""
        # Apply replacement globally
        try:
            new_content, n = regex.subn(replacement, old_content)
        except re.error as e:
            raise ValidationError(f"Replacement failed: {e}")
        if n == 0:
            continue
        # Save via update_chapter so versioning kicks in
        update_chapter(
            ch_id,
            content=new_content,
            create_version=True,
            version_source="find_replace",
            version_notes=f"Find & Replace: '{pattern}' → '{replacement}' ({n} match{n*'s' if n!=1 else ''})",
        )
        total_replacements += n
        details.append({
            "chapter_id": ch_id,
            "chapter_title": r["chapter_title"],
            "replacements": n,
        })

    # Log activity
    with write_transaction() as s:
        log_activity(
            s, entity_type="chapter", entity_id="(bulk)",
            entity_title=f"Find & Replace: '{pattern}' → '{replacement}'",
            action="find_replace",
            details={
                "chapters_modified": len(details),
                "total_replacements": total_replacements,
                "pattern": pattern,
                "replacement": replacement,
            },
        )

    return {
        "applied": True,
        "chapters_modified": len(details),
        "total_replacements": total_replacements,
        "details": details,
    }
