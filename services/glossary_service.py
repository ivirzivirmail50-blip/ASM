"""Glossary & Style Sheet service — keep terms consistent across the manuscript.

A writer's bible of canonical terms. Each entry has:
- term: the canonical form (e.g. "Elara Morningstar")
- alternates: other acceptable spellings (e.g. "El", "Lara")
- forbidden: variants that should NOT appear (e.g. "Ellara", "Elara Morningstar")
- case_sensitive: whether to match case-sensitively
- category: character / place / magic / item / style / other

The scan_chapters() function walks all chapter content and flags any
occurrence of a forbidden variant, plus any near-miss spellings of the
canonical term (using simple Levenshtein distance).
"""
from __future__ import annotations

import logging
import re
from typing import Any

from core.db import read_session, write_transaction
from core.errors import NotFoundError, ValidationError
from models.glossary import GlossaryEntry
from services._common import current_project_id, dump_json, load_json, log_activity, new_uuid, now_utc

log = logging.getLogger("asm.glossary")


CATEGORIES = {
    "character": {"label": "Character",  "icon": "👤", "color": "#a78bfa"},
    "place":     {"label": "Place",      "icon": "📍", "color": "#34d399"},
    "magic":     {"label": "Magic Term", "icon": "✨", "color": "#facc15"},
    "item":      {"label": "Item",       "icon": "🗡", "color": "#f87171"},
    "style":     {"label": "Style Rule", "icon": "📏", "color": "#60a5fa"},
    "other":     {"label": "Other",      "icon": "📝", "color": "#94a3b8"},
}


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def list_entries(*, category: str | None = None) -> list[GlossaryEntry]:
    with read_session() as s:
        q = s.query(GlossaryEntry).filter_by(project_id=current_project_id(s))
        if category and category != "all":
            q = q.filter_by(category=category)
        return list(q.order_by(GlossaryEntry.term.asc()).all())


def get_entry(entry_id: str) -> GlossaryEntry:
    with read_session() as s:
        e = s.get(GlossaryEntry, entry_id)
        if not e:
            raise NotFoundError("Glossary entry not found.")
        return e


def create_entry(
    *, term: str, category: str = "other", definition: str = "",
    alternates: list[str] | None = None, forbidden: list[str] | None = None,
    case_sensitive: bool = False, notes: str = "",
) -> GlossaryEntry:
    if not term or len(term) > 300:
        raise ValidationError("Term required, ≤ 300 chars.")
    if category not in CATEGORIES:
        raise ValidationError(f"Category must be one of {list(CATEGORIES)}.")
    eid = new_uuid()
    with write_transaction() as s:
        e = GlossaryEntry(
            id=eid,
            project_id=current_project_id(s),
            term=term.strip(),
            category=category,
            definition=definition or "",
            alternates=dump_json(alternates or []),
            forbidden=dump_json(forbidden or []),
            case_sensitive=1 if case_sensitive else 0,
            notes=notes or "",
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        s.add(e)
        log_activity(
            s, entity_type="glossary", entity_id=eid,
            entity_title=term, action="created",
        )
        s.flush()
        return e


def update_entry(entry_id: str, **fields: Any) -> GlossaryEntry:
    with write_transaction() as s:
        e = s.get(GlossaryEntry, entry_id)
        if not e:
            raise NotFoundError("Glossary entry not found.")
        for k in ("term", "category", "definition", "notes"):
            if k in fields and fields[k] is not None:
                setattr(e, k, fields[k])
        if "alternates" in fields:
            e.alternates = dump_json(fields["alternates"] or [])
        if "forbidden" in fields:
            e.forbidden = dump_json(fields["forbidden"] or [])
        if "case_sensitive" in fields:
            e.case_sensitive = 1 if fields["case_sensitive"] else 0
        e.updated_at = now_utc()
        s.flush()
        return e


def delete_entry(entry_id: str) -> None:
    with write_transaction() as s:
        e = s.get(GlossaryEntry, entry_id)
        if e:
            s.delete(e)


def to_dict(e: GlossaryEntry) -> dict[str, Any]:
    return {
        "id": e.id,
        "term": e.term,
        "category": e.category,
        "category_label": CATEGORIES.get(e.category, {}).get("label", e.category),
        "icon": CATEGORIES.get(e.category, {}).get("icon", "📝"),
        "color": CATEGORIES.get(e.category, {}).get("color", "#94a3b8"),
        "definition": e.definition or "",
        "alternates": load_json(e.alternates, []),
        "forbidden": load_json(e.forbidden, []),
        "case_sensitive": bool(e.case_sensitive),
        "notes": e.notes or "",
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Scan chapters for inconsistencies
# ---------------------------------------------------------------------------

def _find_all(haystack: str, needle: str, case_sensitive: bool) -> list[tuple[int, int]]:
    """Return all (start, end) positions of needle in haystack."""
    if not needle:
        return []
    flags = 0 if case_sensitive else re.IGNORECASE
    # Escape and require word boundary
    pattern = r"\b" + re.escape(needle) + r"\b"
    return [(m.start(), m.end()) for m in re.finditer(pattern, haystack, flags)]


def scan_chapters(*, chapter_id: str | None = None) -> dict[str, Any]:
    """Walk all (or one) chapter and find:

    1. Forbidden variant occurrences (definite inconsistency)
    2. Near-miss spellings of canonical terms (Levenshtein <= 2)
    3. Confirm canonical term is being used (presence check)

    Returns: {
        "chapters_scanned": int,
        "issues": [
            {
                "chapter_id": ..., "chapter_title": ...,
                "type": "forbidden" | "near_miss",
                "term": ..., "found": ...,
                "count": int, "context": "..."
            }
        ],
        "presence": [
            {"term": ..., "category": ..., "count": int, "chapters_in": int}
        ]
    }
    """
    from models.chapter import Chapter
    issues: list[dict[str, Any]] = []
    presence: dict[str, dict[str, Any]] = {}

    entries = list_entries()
    if not entries:
        return {"chapters_scanned": 0, "issues": [], "presence": []}

    with read_session() as s:
        q = s.query(Chapter).filter_by(project_id=current_project_id(s))
        if chapter_id:
            q = q.filter_by(id=chapter_id)
        chapters = list(q.order_by(Chapter.sort_order.asc()).all())

        for ch in chapters:
            text = ch.content or ""
            for e in entries:
                cs = bool(e.case_sensitive)
                # 1. Forbidden occurrences
                for forb in load_json(e.forbidden, []):
                    matches = _find_all(text, forb, cs)
                    if matches:
                        ctx = _extract_context(text, matches[0][0], forb)
                        issues.append({
                            "chapter_id": ch.id,
                            "chapter_title": ch.title,
                            "type": "forbidden",
                            "severity": "high",
                            "term": e.term,
                            "found": forb,
                            "count": len(matches),
                            "context": ctx,
                        })
                # 2. Near-miss spellings (only single-word canonical terms)
                #    We scan for words near the canonical term using Levenshtein.
                if " " not in e.term and len(e.term) >= 4:
                    near_misses = _find_near_misses(
                        text, e.term, cs,
                        max_distance=2,
                        known_ok=load_json(e.alternates, []) + load_json(e.forbidden, []),
                    )
                    for found, distance, count in near_misses:
                        first_pos = _find_all(text, found, cs)[0][0] if count else 0
                        ctx = _extract_context(text, first_pos, found)
                        issues.append({
                            "chapter_id": ch.id,
                            "chapter_title": ch.title,
                            "type": "near_miss",
                            "severity": "medium" if distance == 1 else "low",
                            "term": e.term,
                            "found": found,
                            "distance": distance,
                            "count": count,
                            "context": ctx,
                        })
                # 3. Presence tracking (canonical + alternates)
                canon_count = len(_find_all(text, e.term, cs))
                alt_count = 0
                for alt in load_json(e.alternates, []):
                    alt_count += len(_find_all(text, alt, cs))
                total = canon_count + alt_count
                if total:
                    key = e.id
                    if key not in presence:
                        presence[key] = {
                            "term": e.term, "category": e.category,
                            "icon": CATEGORIES.get(e.category, {}).get("icon", "📝"),
                            "count": 0, "chapters_in": 0,
                        }
                    presence[key]["count"] += total
                    presence[key]["chapters_in"] += 1

    return {
        "chapters_scanned": len(chapters),
        "issues": issues,
        "presence": list(presence.values()),
    }


def _extract_context(text: str, pos: int, needle: str, window: int = 50) -> str:
    """Return text[pos-window : pos+len(needle)+window] with … markers."""
    start = max(0, pos - window)
    end = min(len(text), pos + len(needle) + window)
    snippet = text[start:end]
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    # Collapse newlines for display
    snippet = snippet.replace("\n", " ").replace("\r", "")
    return f"{prefix}{snippet}{suffix}"


def _levenshtein(a: str, b: str) -> int:
    """Standard Levenshtein distance, classic DP."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def _find_near_misses(
    text: str, canonical: str, case_sensitive: bool,
    max_distance: int = 2, known_ok: list[str] | None = None,
) -> list[tuple[str, int, int]]:
    """Find unique words in text that are within max_distance of canonical.

    Skips exact matches and any word in known_ok.
    Returns list of (found_word, distance, count).
    """
    known_ok = known_ok or []
    if case_sensitive:
        words = re.findall(r"\b[A-Za-z]+\b", text)
        canonical_cmp = canonical
        known_ok_cmp = list(known_ok)
    else:
        words = re.findall(r"\b[A-Za-z]+\b", text.lower())
        canonical_cmp = canonical.lower()
        known_ok_cmp = [k.lower() for k in known_ok]
    # Count words
    counts: dict[str, int] = {}
    for w in words:
        counts[w] = counts.get(w, 0) + 1
    out: list[tuple[str, int, int]] = []
    seen: set[str] = set()
    for w in words:
        if w in seen:
            continue
        seen.add(w)
        if w == canonical_cmp or w in known_ok_cmp:
            continue
        # Skip very short words (likely false positives)
        if len(w) < 3 or abs(len(w) - len(canonical_cmp)) > max_distance:
            continue
        d = _levenshtein(w, canonical_cmp)
        if 1 <= d <= max_distance:
            out.append((w, d, counts[w]))
    return out


# ---------------------------------------------------------------------------
# Seed default glossary starter entries
# ---------------------------------------------------------------------------

DEFAULT_GLOSSARY = [
    {
        "term": "the protagonist",
        "category": "character",
        "definition": "Replace this with your protagonist's full name.",
        "alternates": [],
        "forbidden": [],
    },
    {
        "term": "the antagonist",
        "category": "character",
        "definition": "Replace this with your antagonist's name.",
        "alternates": [],
        "forbidden": [],
    },
    {
        "term": "the setting",
        "category": "place",
        "definition": "Replace this with the name of your primary location.",
        "alternates": [],
        "forbidden": [],
    },
]


def seed_default_glossary() -> None:
    existing = list_entries()
    if existing:
        return
    for entry in DEFAULT_GLOSSARY:
        create_entry(**entry)
    log.info("Seeded %d default glossary entries", len(DEFAULT_GLOSSARY))
