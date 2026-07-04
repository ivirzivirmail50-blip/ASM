"""Validate service: data health + reference integrity."""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any

from sqlalchemy import select

from core.db import read_session
from models.chapter import Chapter
from models.character import Character
from models.plan import Plan
from models.world import WorldEntry
from services._common import current_project_id

log = logging.getLogger("asm.validate")


def validate_all() -> dict[str, Any]:
    """Run all data health checks. Returns {ok, findings, summary}."""
    findings: list[dict] = []
    with read_session() as s:
        pid = current_project_id(s)
        chapters = list(s.scalars(
            select(Chapter).where(Chapter.project_id == pid)
        ).all())
        characters = list(s.scalars(
            select(Character).where(Character.project_id == pid)
        ).all())
        plans = list(s.scalars(
            select(Plan).where(Plan.project_id == pid)
        ).all())
        world_entries = list(s.scalars(
            select(WorldEntry).where(WorldEntry.project_id == pid)
        ).all())
        char_ids = {c.id for c in characters}
        chapter_ids = {c.id for c in chapters}
        world_ids = {e.id for e in world_entries}
        plan_ids = {p.id for p in plans}

        # 1. Chapter word_count mismatches
        import re
        for ch in chapters:
            actual = 0
            if ch.content:
                cleaned = re.sub(r"\s+", " ", ch.content.strip())
                actual = len(cleaned.split()) if cleaned else 0
            if abs((ch.word_count or 0) - actual) > 1:
                findings.append({
                    "severity": "warning",
                    "category": "word_count",
                    "entity_type": "chapter",
                    "entity_id": ch.id,
                    "entity_title": ch.title,
                    "message": f"Stored word_count={ch.word_count}, recomputed={actual}",
                })

        # 2. Chapter.character_ids referencing missing characters
        for ch in chapters:
            try:
                ids = json.loads(ch.character_ids or "[]")
            except (json.JSONDecodeError, TypeError):
                ids = []
            for cid in ids:
                if cid not in char_ids:
                    findings.append({
                        "severity": "error",
                        "category": "dangling_ref",
                        "entity_type": "chapter",
                        "entity_id": ch.id,
                        "entity_title": ch.title,
                        "message": f"Links to missing character {cid}",
                    })

        # 3. Plan.chapter_id referencing missing chapter
        for p in plans:
            if p.chapter_id and p.chapter_id not in chapter_ids:
                findings.append({
                    "severity": "error",
                    "category": "dangling_ref",
                    "entity_type": "plan",
                    "entity_id": p.id,
                    "entity_title": p.title,
                    "message": f"Links to missing chapter {p.chapter_id}",
                })
            if p.parent_id and p.parent_id not in plan_ids:
                findings.append({
                    "severity": "warning",
                    "category": "dangling_ref",
                    "entity_type": "plan",
                    "entity_id": p.id,
                    "entity_title": p.title,
                    "message": f"Parent plan {p.parent_id} missing",
                })

        # 4. World entry parent_id dangling
        for e in world_entries:
            if e.parent_id and e.parent_id not in world_ids:
                findings.append({
                    "severity": "warning",
                    "category": "dangling_ref",
                    "entity_type": "world_entry",
                    "entity_id": e.id,
                    "entity_title": e.name,
                    "message": f"Parent entry {e.parent_id} missing",
                })

    return {
        "ok": not any(f["severity"] == "error" for f in findings),
        "findings": findings,
        "summary": {
            "total": len(findings),
            "errors": sum(1 for f in findings if f["severity"] == "error"),
            "warnings": sum(1 for f in findings if f["severity"] == "warning"),
        },
    }


def fix_word_counts() -> int:
    """Recompute and fix all chapter word_count mismatches. Returns fixed count."""
    import re
    fixed = 0
    with read_session() as s:
        pid = current_project_id(s)
        chapters = list(s.scalars(
            select(Chapter).where(Chapter.project_id == pid)
        ).all())
        from core.db import write_transaction
        s.close()
    # Use a fresh write transaction
    from core.db import write_transaction as _wt
    with _wt() as ws:
        for ch in chapters:
            actual = 0
            if ch.content:
                cleaned = re.sub(r"\s+", " ", ch.content.strip())
                actual = len(cleaned.split()) if cleaned else 0
            db_ch = ws.get(Chapter, ch.id)
            if db_ch and abs((db_ch.word_count or 0) - actual) > 1:
                db_ch.word_count = actual
                fixed += 1
    return fixed
