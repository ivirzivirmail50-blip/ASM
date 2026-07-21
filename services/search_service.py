"""Search service backed by FTS5 with LIKE fallback.

Supports:
- FTS5 MATCH for full-text search (default)
- Case-sensitivity toggle (FTS5 is case-insensitive by default; for case-sensitive
  search we post-filter with Python)
- Regex post-filter on FTS results (clearly bounded)
"""
from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import text

from core.db import read_session
from services._common import current_project_id

log = logging.getLogger("asm.search")


def _escape_fts(query: str) -> str:
    """Sanitize a query for FTS5 MATCH (prefix-tokenize)."""
    cleaned = "".join(c if c.isalnum() or c.isspace() else " " for c in query)
    tokens = [t for t in cleaned.split() if t]
    if not tokens:
        return ""
    return " ".join(f'"{t}"*' for t in tokens)


def search_all(query: str, *, limit_per_module: int = 50,
               case_sensitive: bool = False, regex: bool = False) -> dict[str, list[dict]]:
    """Search chapters, characters, and world entries."""
    if not query:
        return {"chapters": [], "characters": [], "world": []}
    chapters = search_chapters(query, limit=limit_per_module,
                               case_sensitive=case_sensitive, regex=regex)
    characters = search_characters(query, limit=limit_per_module,
                                   case_sensitive=case_sensitive, regex=regex)
    world = search_world(query, limit=limit_per_module,
                         case_sensitive=case_sensitive, regex=regex)
    return {"chapters": chapters, "characters": characters, "world": world}


def search_chapters(query: str, *, limit: int = 50,
                    case_sensitive: bool = False,
                    regex: bool = False) -> list[dict]:
    return _fts_search(
        table="chapters_fts",
        entity_table="chapters",
        columns=("title", "synopsis", "content"),
        query=query, limit=limit,
        case_sensitive=case_sensitive, regex=regex,
    )


def search_characters(query: str, *, limit: int = 50,
                      case_sensitive: bool = False,
                      regex: bool = False) -> list[dict]:
    return _fts_search(
        table="characters_fts",
        entity_table="characters",
        columns=("name", "aliases", "physical", "psychology",
                 "background", "philosophy", "voice", "notes"),
        query=query, limit=limit,
        case_sensitive=case_sensitive, regex=regex,
    )


def search_world(query: str, *, limit: int = 50,
                 case_sensitive: bool = False,
                 regex: bool = False) -> list[dict]:
    return _fts_search(
        table="world_fts",
        entity_table="world_entries",
        columns=("name", "description", "content", "notes"),
        query=query, limit=limit,
        case_sensitive=case_sensitive, regex=regex,
    )


def _fts_search(*, table: str, entity_table: str, columns: tuple[str, ...],
                query: str, limit: int = 50,
                case_sensitive: bool = False,
                regex: bool = False) -> list[dict]:
    """FTS5 MATCH search with LIKE fallback + optional regex post-filter."""
    fts_query = _escape_fts(query) if not regex else ""
    with read_session() as s:
        try:
            if fts_query:
                sql = text(f"""
                    SELECT e.id, e.{columns[0]} AS title,
                           snippet({table}, 1, '<mark>', '</mark>', '…', 12) AS snippet
                    FROM {table} f
                    JOIN {entity_table} e ON e.rowid = f.rowid
                    WHERE {table} MATCH :q
                    LIMIT :limit
                """)
                rows = s.execute(sql, {"q": fts_query, "limit": limit}).all()
                results = [{"id": r[0], "title": r[1] or "", "snippet": r[2] or ""}
                           for r in rows]
            else:
                raise RuntimeError("skip to LIKE")
        except (RuntimeError, Exception) as exc:
            err_msg = str(exc).lower()
            if 'match' in err_msg or 'fts' in err_msg or 'no such table' in err_msg or 'skip to like' in err_msg:
                log.warning("FTS5 search failed, falling back to LIKE: %s", exc)
            else:
                raise
            # LIKE fallback (case-insensitive by default in SQLite)
            if case_sensitive:
                like_op = "GLOB"
                like_val = f"*{query}*"
            else:
                like_op = "LIKE"
                like_val = f"%{query}%"
            conds = " OR ".join(f"{c} {like_op} :q" for c in columns)
            sql = text(f"""
                SELECT id, {columns[0]} AS title,
                       substr(coalesce({columns[1]}, ''), 1, 200) AS snippet
                FROM {entity_table}
                WHERE {conds}
                LIMIT :limit
            """)
            rows = s.execute(sql, {"q": like_val, "limit": limit}).all()
            results = [{"id": r[0], "title": r[1] or "", "snippet": r[2] or ""}
                       for r in rows]

    # Regex post-filter (clearly bounded — applied to FTS/LIKE results)
    if regex:
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            pattern = re.compile(query, flags)
        except re.error as exc:
            log.warning("Invalid regex: %s", exc)
            return []
        filtered = []
        for r in results:
            if pattern.search(r["title"]) or pattern.search(r["snippet"]):
                filtered.append(r)
        results = filtered

    # Case-sensitive post-filter (FTS5 is case-insensitive; for case-sensitive
    # search we filter FTS results by exact case match)
    if case_sensitive and not regex:
        filtered = [r for r in results
                    if query in r["title"] or query in r["snippet"]]
        results = filtered

    return results
