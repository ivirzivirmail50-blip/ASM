"""Scene Card Index service — extract, manage, and reorder scenes across the manuscript.

Scenes are extracted from chapter content by splitting on:
- Three or more newlines (\\n\\n\\n)
- Markdown scene break markers: * * *, ---, ###, * * *
- Explicit "# Scene Title" headers (markdown H1)

The service can:
- extract_from_chapter(chapter_id): scan a chapter and create SceneCards
- extract_all(): scan every chapter in the project
- list_cards(): return cards sorted by global sort_order
- update_card(): edit card metadata (POV, location, mood, etc.)
- reorder(): persist a new sort_order (e.g., after drag-drop)
- move_to_chapter(): reassign a scene to a different chapter
- stats(): aggregate counts (cards per chapter, per mood, per POV)
"""
from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import select, func

from core.db import read_session, write_transaction
from core.errors import NotFoundError, ValidationError
from models.scene import SceneCard, SCENE_STATUSES, SCENE_MOODS, TIME_OF_DAY, CARD_COLORS
from models.chapter import Chapter
from services._common import current_project_id, dump_json, load_json, log_activity, new_uuid, now_utc

log = logging.getLogger("asm.scenes")


# Patterns that mark scene breaks
SCENE_BREAK_PATTERNS = [
    re.compile(r"\n\s*\*\s*\*\s*\*\s*\n", re.MULTILINE),  # * * *
    re.compile(r"\n\s*---+\s*\n", re.MULTILINE),            # ---
    re.compile(r"\n{3,}", re.MULTILINE),                    # 3+ newlines
    re.compile(r"\n\s*###\s*\n", re.MULTILINE),             # ### (scene marker)
]


def _split_into_scenes(content: str) -> list[str]:
    """Split chapter content into individual scenes."""
    if not content:
        return []
    text = content
    # Normalize: replace all scene break patterns with a single marker
    marker = "\n@@@SCENE_BREAK@@@\n"
    for pattern in SCENE_BREAK_PATTERNS:
        text = pattern.sub(marker, text)
    # Split on the marker
    scenes = [s.strip() for s in text.split("@@@SCENE_BREAK@@@") if s.strip()]
    return scenes


def _extract_title(scene_text: str) -> str:
    """Try to extract a title from the first line if it's a markdown header."""
    if not scene_text:
        return ""
    first_line = scene_text.split("\n", 1)[0].strip()
    # Markdown H1/H2/H3
    if first_line.startswith("#"):
        return first_line.lstrip("#").strip()[:500]
    # Otherwise use first 60 chars
    return (first_line[:60] + ("…" if len(first_line) > 60 else ""))[:500]


def _count_words(text: str) -> int:
    if not text:
        return 0
    return len(text.split())


def extract_from_chapter(chapter_id: str, *, replace_existing: bool = True) -> list[SceneCard]:
    """Scan a chapter and create SceneCards for each scene found.

    If replace_existing=True, all existing cards for this chapter are deleted
    before re-extraction (useful when chapter content has changed).
    """
    with read_session() as s:
        ch = s.get(Chapter, chapter_id)
        if not ch:
            raise NotFoundError("Chapter not found.")
        content = ch.content or ""
        ch_title = ch.title
        ch_sort = ch.sort_order or 0
        pid = current_project_id(s)

    if replace_existing:
        # Delete existing cards for this chapter
        with write_transaction() as s:
            existing = list(s.scalars(
                select(SceneCard).where(SceneCard.chapter_id == chapter_id)
            ))
            for c in existing:
                s.delete(c)

    scenes = _split_into_scenes(content)
    created: list[SceneCard] = []
    for idx, scene_text in enumerate(scenes):
        title = _extract_title(scene_text)
        if not title:
            title = f"{ch_title} — Scene {idx + 1}"
        summary = scene_text[:200].replace("\n", " ").strip()
        if len(scene_text) > 200:
            summary += "…"
        snippet = scene_text[:500].replace("\n", " ").strip()
        if len(scene_text) > 500:
            snippet += "…"
        wc = _count_words(scene_text)

        with write_transaction() as s:
            # Find global max sort_order for this project
            max_order = s.scalar(
                select(func.max(SceneCard.sort_order)).where(
                    SceneCard.project_id == pid
                )
            ) or 0
            card = SceneCard(
                id=new_uuid(),
                project_id=pid,
                chapter_id=chapter_id,
                title=title,
                summary=summary,
                content_snippet=snippet,
                full_text=scene_text,
                scene_break_marker="###",
                sort_order=max_order + 1,
                color=CARD_COLORS[idx % len(CARD_COLORS)],
                status="draft",
                word_count=wc,
                tags=dump_json([]),
                notes="",
                created_at=now_utc(),
                updated_at=now_utc(),
            )
            s.add(card)
            log_activity(
                s, entity_type="scene", entity_id=card.id,
                entity_title=title, action="extracted",
            )
            s.flush()
            created.append(card)
    log.info("Extracted %d scenes from chapter %s", len(created), chapter_id)
    return created


def extract_all(*, replace_existing: bool = True) -> dict[str, Any]:
    """Extract scenes from all chapters in the project."""
    with read_session() as s:
        chapters = list(s.scalars(
            select(Chapter).where(
                Chapter.project_id == current_project_id(s)
            ).order_by(Chapter.sort_order.asc())
        ))
    total_scenes = 0
    per_chapter: list[dict[str, Any]] = []
    for ch in chapters:
        scenes = extract_from_chapter(ch.id, replace_existing=replace_existing)
        total_scenes += len(scenes)
        per_chapter.append({
            "chapter_id": ch.id,
            "chapter_title": ch.title,
            "scene_count": len(scenes),
        })
    return {
        "chapters_scanned": len(chapters),
        "total_scenes": total_scenes,
        "per_chapter": per_chapter,
    }


def list_cards(
    *, chapter_id: str | None = None, mood: str | None = None,
    status: str | None = None, pov_character_id: str | None = None,
) -> list[SceneCard]:
    with read_session() as s:
        q = select(SceneCard).where(SceneCard.project_id == current_project_id(s))
        if chapter_id:
            q = q.where(SceneCard.chapter_id == chapter_id)
        if mood and mood != "all":
            q = q.where(SceneCard.mood == mood)
        if status and status != "all":
            q = q.where(SceneCard.status == status)
        if pov_character_id:
            q = q.where(SceneCard.pov_character_id == pov_character_id)
        return list(s.scalars(q.order_by(SceneCard.sort_order.asc())))


def get_card(card_id: str) -> SceneCard:
    with read_session() as s:
        c = s.get(SceneCard, card_id)
        if not c:
            raise NotFoundError("Scene card not found.")
        return c


def update_card(card_id: str, **fields: Any) -> SceneCard:
    with write_transaction() as s:
        c = s.get(SceneCard, card_id)
        if not c:
            raise NotFoundError("Scene card not found.")
        for k in ("title", "summary", "content_snippet", "full_text",
                  "scene_break_marker", "color", "pov_character_id",
                  "location", "time_of_day", "mood", "status", "notes"):
            if k in fields and fields[k] is not None:
                setattr(c, k, fields[k])
        if "tags" in fields:
            c.tags = dump_json(fields["tags"] or [])
        if "full_text" in fields and fields["full_text"] is not None:
            c.word_count = _count_words(fields["full_text"])
        c.updated_at = now_utc()
        s.flush()
        return c


def move_to_chapter(card_id: str, new_chapter_id: str) -> SceneCard:
    """Reassign a scene card to a different chapter."""
    with write_transaction() as s:
        c = s.get(SceneCard, card_id)
        if not c:
            raise NotFoundError("Scene card not found.")
        # Verify new chapter exists
        ch = s.get(Chapter, new_chapter_id)
        if not ch:
            raise ValidationError("Target chapter does not exist.")
        c.chapter_id = new_chapter_id
        c.updated_at = now_utc()
        s.flush()
        return c


def reorder(card_ids: list[str]) -> None:
    """Persist a new sort_order for the given card IDs (in order)."""
    with write_transaction() as s:
        for idx, cid in enumerate(card_ids, start=1):
            c = s.get(SceneCard, cid)
            if c:
                c.sort_order = idx
        s.flush()


def delete_card(card_id: str) -> None:
    with write_transaction() as s:
        c = s.get(SceneCard, card_id)
        if c:
            s.delete(c)


def to_dict(c: SceneCard, *, include_full_text: bool = False) -> dict[str, Any]:
    # Resolve chapter title
    ch_title = ""
    if c.chapter_id:
        with read_session() as s:
            ch = s.get(Chapter, c.chapter_id)
            ch_title = ch.title if ch else ""
    return {
        "id": c.id,
        "chapter_id": c.chapter_id,
        "chapter_title": ch_title,
        "title": c.title or "",
        "summary": c.summary or "",
        "content_snippet": c.content_snippet or "",
        "full_text": c.full_text if include_full_text else None,
        "scene_break_marker": c.scene_break_marker or "###",
        "sort_order": c.sort_order,
        "color": c.color or CARD_COLORS[0],
        "pov_character_id": c.pov_character_id,
        "location": c.location or "",
        "time_of_day": c.time_of_day or "",
        "time_of_day_label": TIME_OF_DAY.get(c.time_of_day or "", c.time_of_day or ""),
        "mood": c.mood or "",
        "mood_label": SCENE_MOODS.get(c.mood or "", {}).get("label", c.mood or ""),
        "mood_icon": SCENE_MOODS.get(c.mood or "", {}).get("icon", ""),
        "mood_color": SCENE_MOODS.get(c.mood or "", {}).get("color", "#94a3b8"),
        "status": c.status or "draft",
        "status_label": SCENE_STATUSES.get(c.status or "draft", {}).get("label", c.status or "draft"),
        "status_icon": SCENE_STATUSES.get(c.status or "draft", {}).get("icon", ""),
        "status_color": SCENE_STATUSES.get(c.status or "draft", {}).get("color", "#94a3b8"),
        "word_count": c.word_count or 0,
        "tags": load_json(c.tags, []),
        "notes": c.notes or "",
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def stats() -> dict[str, Any]:
    cards = list_cards()
    by_chapter: dict[str, dict[str, Any]] = {}
    by_mood: dict[str, int] = {m: 0 for m in SCENE_MOODS}
    by_status: dict[str, int] = {s: 0 for s in SCENE_STATUSES}
    total_words = 0
    for c in cards:
        # Chapter count
        key = c.chapter_id or "(orphan)"
        if key not in by_chapter:
            by_chapter[key] = {"chapter_id": key, "count": 0, "words": 0}
        by_chapter[key]["count"] += 1
        by_chapter[key]["words"] += c.word_count or 0
        # Mood
        if c.mood and c.mood in by_mood:
            by_mood[c.mood] += 1
        # Status
        if c.status and c.status in by_status:
            by_status[c.status] += 1
        total_words += c.word_count or 0
    # Resolve chapter titles
    chapter_list = list(by_chapter.values())
    if chapter_list:
        with read_session() as s:
            for entry in chapter_list:
                if entry["chapter_id"] != "(orphan)":
                    ch = s.get(Chapter, entry["chapter_id"])
                    entry["chapter_title"] = ch.title if ch else "(unknown)"
                else:
                    entry["chapter_title"] = "(orphan)"
    return {
        "total": len(cards),
        "total_words": total_words,
        "by_chapter": chapter_list,
        "by_mood": by_mood,
        "by_status": by_status,
    }
