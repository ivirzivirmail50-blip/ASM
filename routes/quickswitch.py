"""Quick Switch route — global command palette for fast navigation."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from services import chapter_service, character_service, plan_service, world_service

log = logging.getLogger("asm.routes.quickswitch")
bp = Blueprint("quickswitch", __name__)


@bp.route("/search-all")
def search_all_entities():
    """Search across all entity types for the Quick Switch palette.

    Returns a flat list of {type, id, title, subtitle, url} items.
    """
    q = (request.args.get("q") or "").strip().lower()[:200]

    # Navigation shortcuts — always shown (filtered by query if non-empty)
    nav_items = [
        {"type": "nav", "title": "Dashboard", "subtitle": "Go to Story Cockpit", "icon": "⬢", "url": "/"},
        {"type": "nav", "title": "Books / Series", "subtitle": "Manage multiple books", "icon": "📖", "url": "/projects"},
        {"type": "nav", "title": "New Chapter", "subtitle": "Create a new chapter", "icon": "+", "url": "/chapters/new"},
        {"type": "nav", "title": "New Character", "subtitle": "Create a new character", "icon": "+", "url": "/characters/new"},
        {"type": "nav", "title": "New Plan Item", "subtitle": "Create a new plan item", "icon": "+", "url": "/plans/new"},
        {"type": "nav", "title": "New World Entry", "subtitle": "Create a new world entry", "icon": "+", "url": "/world/new"},
        {"type": "nav", "title": "Relationship Graph", "subtitle": "View character graph", "icon": "⦿", "url": "/characters/graph"},
        {"type": "nav", "title": "Kanban Board", "subtitle": "View plan board", "icon": "▦", "url": "/plans/"},
        {"type": "nav", "title": "Search", "subtitle": "Full-text search", "icon": "⌕", "url": "/search/"},
        {"type": "nav", "title": "Story Lint", "subtitle": "Run consistency checks", "icon": "🔍", "url": "/lint"},
        {"type": "nav", "title": "Settings", "subtitle": "Configure the app", "icon": "⚙", "url": "/settings/"},
        {"type": "nav", "title": "Export Center", "subtitle": "Export manuscript & more", "icon": "↧", "url": "/export/"},
        {"type": "nav", "title": "Bulk Import", "subtitle": "Import multiple files", "icon": "↥", "url": "/chapters/bulk-import"},
    ]

    if not q:
        return jsonify({"results": nav_items})

    results = []
    limit = 10  # per type

    # Chapters
    try:
        chapters, _ = chapter_service.list_chapters(search=q, per_page=limit)
        for ch in chapters:
            results.append({
                "type": "chapter",
                "id": ch.id,
                "title": ch.title,
                "subtitle": f"Chapter {ch.sort_order} · {ch.word_count} words · {ch.status}",
                "icon": "▤",
                "url": f"/chapters/{ch.id}",
            })
    except Exception:
        pass

    # Characters
    try:
        chars = character_service.list_characters(search=q)
        for c in chars[:limit]:
            results.append({
                "type": "character",
                "id": c.id,
                "title": c.name,
                "subtitle": f"{c.role} · {c.age or '—'} · {c.gender or '—'}",
                "icon": "♛",
                "url": f"/characters/{c.id}",
            })
    except Exception:
        pass

    # Plans
    try:
        plans = plan_service.list_plans()
        for p in plans:
            if q in (p.title or "").lower() or q in (p.description or "").lower():
                results.append({
                    "type": "plan",
                    "id": p.id,
                    "title": p.title,
                    "subtitle": f"{p.status} · {p.track or 'No track'}",
                    "icon": "▦",
                    "url": f"/plans/{p.id}",
                })
            if len([r for r in results if r["type"] == "plan"]) >= limit:
                break
    except Exception:
        pass

    # World entries
    try:
        entries, _ = world_service.list_entries(search=q, per_page=limit)
        for e in entries:
            results.append({
                "type": "world_entry",
                "id": e.id,
                "title": e.name,
                "subtitle": f"{e.type} · {e.category or '—'}",
                "icon": "🌍",
                "url": f"/world/{e.id}",
            })
    except Exception:
        pass

    # Navigation shortcuts — filter by query
    for item in nav_items:
        if q in item["title"].lower() or q in item["subtitle"].lower():
            results.append(item)

    # Cap total results
    return jsonify({"results": results[:30]})
