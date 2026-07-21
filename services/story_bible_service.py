"""Story Bible Auto-Generator — compile a comprehensive reference document.

Pulls together data from across the manuscript into a single document:
- Title page (story title, author, subtitle, logline)
- Character profiles (all characters with their key fields)
- Character relationship map (who's connected to whom)
- World entries (all locations, lore, factions, etc.)
- Plot summary (chapter synopses concatenated)
- Timeline (all plan items with story_dates, sorted chronologically)
- Glossary terms (from the Glossary module)
- Statistics (word counts, chapter count, etc.)

Output formats: HTML (styled, printable), TXT, MD, JSON.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select

from core.db import read_session
from models.chapter import Chapter
from models.character import Character, CharacterRelationship
from models.glossary import GlossaryEntry
from models.plan import Plan
from models.settings import Setting
from models.world import WorldEntry
from services._common import current_project_id, load_json

log = logging.getLogger("asm.story_bible")


def _esc(s: str) -> str:
    if not s:
        return ""
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&#39;"))


def gather_data() -> dict[str, Any]:
    """Gather all data needed for the story bible."""
    with read_session() as s:
        pid = current_project_id(s)
        # Story metadata
        title = Setting.get(s, "story_title", "My Story")
        author = Setting.get(s, "story_author", "Author")
        subtitle = Setting.get(s, "story_subtitle", "")
        logline = Setting.get(s, "story_logline", "")

        # Chapters
        chapters = list(s.scalars(
            select(Chapter).where(Chapter.project_id == pid)
            .order_by(Chapter.sort_order.asc())
        ))
        chapter_data = [{
            "id": ch.id,
            "title": ch.title,
            "status": ch.status,
            "word_count": ch.word_count or 0,
            "synopsis": ch.synopsis or "",
            "tags": load_json(ch.tags, []),
            "character_ids": load_json(ch.character_ids, []),
        } for ch in chapters]

        # Characters
        characters = list(s.scalars(
            select(Character).where(Character.project_id == pid)
            .order_by(Character.name.asc())
        ))
        char_data = [{
            "id": c.id,
            "name": c.name,
            "role": c.role,
            "age": c.age,
            "gender": c.gender,
            "aliases": load_json(c.aliases, []),
            "avatar_color": c.avatar_color,
            "physical": c.physical or "",
            "psychology": c.psychology or "",
            "background": c.background or "",
            "philosophy": c.philosophy or "",
            "voice": c.voice or "",
            "story_role": c.story_role or "",
        } for c in characters]

        # Relationships
        rels = list(s.scalars(select(CharacterRelationship)))
        char_id_set = {c.id for c in characters}
        rel_data = [{
            "from": r.from_character_id,
            "to": r.to_character_id,
            "type": r.relationship_type,
            "description": r.description or "",
            "bidirectional": bool(r.is_bidirectional),
        } for r in rels
          if r.from_character_id in char_id_set and r.to_character_id in char_id_set]

        # World entries
        world = list(s.scalars(
            select(WorldEntry).where(WorldEntry.project_id == pid)
            .order_by(WorldEntry.type.asc(), WorldEntry.name.asc())
        ))
        world_data = [{
            "id": e.id,
            "type": e.type,
            "name": e.name,
            "category": e.category or "",
            "description": e.description or "",
            "content": e.content or "",
        } for e in world]

        # Plan items with story dates
        plans = list(s.scalars(
            select(Plan).where(
                Plan.project_id == pid,
                Plan.story_date.is_not(None),
            ).order_by(Plan.story_date.asc())
        ))
        timeline_data = [{
            "title": p.title,
            "story_date": p.story_date,
            "event_type": p.event_type or "",
            "track": p.track or "",
            "description": p.description or "",
        } for p in plans]

        # Glossary
        glossary = list(s.scalars(
            select(GlossaryEntry).where(GlossaryEntry.project_id == pid)
            .order_by(GlossaryEntry.term.asc())
        ))
        glossary_data = [{
            "term": g.term,
            "category": g.category,
            "definition": g.definition or "",
            "alternates": load_json(g.alternates, []),
            "forbidden": load_json(g.forbidden, []),
        } for g in glossary]

        # Stats
        total_words = sum(ch.word_count or 0 for ch in chapters)

    return {
        "title": title,
        "author": author,
        "subtitle": subtitle,
        "logline": logline,
        "chapters": chapter_data,
        "characters": char_data,
        "relationships": rel_data,
        "world_entries": world_data,
        "timeline": timeline_data,
        "glossary": glossary_data,
        "stats": {
            "chapter_count": len(chapter_data),
            "character_count": len(char_data),
            "world_count": len(world_data),
            "timeline_event_count": len(timeline_data),
            "glossary_count": len(glossary_data),
            "total_words": total_words,
        },
    }


def render_html(data: dict[str, Any]) -> str:
    """Render the story bible as styled HTML."""
    css = """
    body { font-family: Georgia, serif; max-width: 900px; margin: 2rem auto; padding: 1rem; line-height: 1.7; color: #1a1a1a; }
    h1 { font-size: 2.5rem; text-align: center; margin-bottom: 0.5rem; }
    h2 { font-size: 1.8rem; border-bottom: 2px solid #6366f1; padding-bottom: 0.3rem; margin-top: 3rem; page-break-before: always; }
    h3 { font-size: 1.3rem; margin-top: 1.5rem; }
    .subtitle { text-align: center; font-style: italic; color: #555; }
    .logline { text-align: center; font-size: 1.1rem; margin: 1rem 0; padding: 1rem; background: #f4ecd8; border-radius: 6px; }
    .meta { text-align: center; color: #777; margin-bottom: 2rem; }
    .character-card, .world-card { border: 1px solid #ddd; border-radius: 6px; padding: 1rem; margin: 1rem 0; page-break-inside: avoid; }
    .character-card h3 { margin-top: 0; }
    .avatar { display: inline-block; width: 32px; height: 32px; border-radius: 50%; text-align: center; line-height: 32px; color: white; font-weight: bold; margin-right: 0.5rem; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 3px; background: #e0e4ee; font-size: 0.85rem; margin-right: 4px; }
    .stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin: 1rem 0; }
    .stat { text-align: center; padding: 1rem; background: #f1f3f9; border-radius: 6px; }
    .stat-value { font-size: 1.8rem; font-weight: bold; color: #6366f1; }
    .stat-label { font-size: 0.85rem; color: #555; }
    .chapter-list li { margin: 0.5rem 0; }
    .glossary-term { font-weight: bold; }
    .toc { page-break-after: always; }
    .toc li { margin: 0.3rem 0; }
    """
    parts = [f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{_esc(data['title'])} — Story Bible</title><style>{css}</style></head><body>"]

    # Title page
    parts.append(f"<h1>{_esc(data['title'])}</h1>")
    if data["subtitle"]:
        parts.append(f"<p class='subtitle'>{_esc(data['subtitle'])}</p>")
    parts.append(f"<p class='meta'>by {_esc(data['author'])}</p>")
    if data["logline"]:
        parts.append(f"<div class='logline'><strong>Logline:</strong> {_esc(data['logline'])}</div>")

    # Stats
    st = data["stats"]
    parts.append("<div class='stat-grid'>")
    parts.append(f"<div class='stat'><div class='stat-value'>{st['chapter_count']}</div><div class='stat-label'>Chapters</div></div>")
    parts.append(f"<div class='stat'><div class='stat-value'>{st['character_count']}</div><div class='stat-label'>Characters</div></div>")
    parts.append(f"<div class='stat'><div class='stat-value'>{st['world_count']}</div><div class='stat-label'>World Entries</div></div>")
    parts.append(f"<div class='stat'><div class='stat-value'>{st['total_words']:,}</div><div class='stat-label'>Total Words</div></div>")
    parts.append(f"<div class='stat'><div class='stat-value'>{st['timeline_event_count']}</div><div class='stat-label'>Timeline Events</div></div>")
    parts.append(f"<div class='stat'><div class='stat-value'>{st['glossary_count']}</div><div class='stat-label'>Glossary Terms</div></div>")
    parts.append("</div>")

    # Table of contents
    parts.append("<div class='toc'><h2>Table of Contents</h2><ul>")
    parts.append("<li>1. Plot Summary</li>")
    parts.append(f"<li>2. Characters ({len(data['characters'])})</li>")
    parts.append("<li>3. Character Relationships</li>")
    parts.append(f"<li>4. World Entries ({len(data['world_entries'])})</li>")
    parts.append(f"<li>5. Timeline ({len(data['timeline'])})</li>")
    parts.append(f"<li>6. Glossary ({len(data['glossary'])})</li>")
    parts.append("</ul></div>")

    # Plot summary
    parts.append("<h2>1. Plot Summary</h2>")
    if data["chapters"]:
        parts.append("<ol class='chapter-list'>")
        for ch in data["chapters"]:
            parts.append(f"<li><strong>{_esc(ch['title'])}</strong> ({ch['word_count']} words, {ch['status']})")
            if ch["synopsis"]:
                parts.append(f"<br><em>{_esc(ch['synopsis'])}</em>")
            parts.append("</li>")
        parts.append("</ol>")
    else:
        parts.append("<p>No chapters yet.</p>")

    # Characters
    parts.append(f"<h2>2. Characters ({len(data['characters'])})</h2>")
    if data["characters"]:
        for c in data["characters"]:
            color = c["avatar_color"] or "#6366f1"
            initial = (c["name"][:1] or "?").upper()
            parts.append(f"<div class='character-card'>")
            parts.append(f"<h3><span class='avatar' style='background: {color}'>{initial}</span>{_esc(c['name'])}</h3>")
            parts.append(f"<p><span class='badge'>{_esc(c['role'] or 'no role')}</span>")
            if c["age"]:
                parts.append(f"<span class='badge'>Age: {_esc(c['age'])}</span>")
            if c["gender"]:
                parts.append(f"<span class='badge'>{_esc(c['gender'])}</span>")
            if c["aliases"]:
                parts.append(f"<span class='badge'>Aliases: {_esc(', '.join(c['aliases']))}</span>")
            parts.append("</p>")
            for field, label in [("physical", "Physical"), ("psychology", "Psychology"),
                                  ("background", "Background"), ("philosophy", "Philosophy"),
                                  ("voice", "Voice"), ("story_role", "Story Role")]:
                if c[field]:
                    parts.append(f"<p><strong>{label}:</strong> {_esc(c[field])}</p>")
            parts.append("</div>")
    else:
        parts.append("<p>No characters yet.</p>")

    # Relationships
    parts.append("<h2>3. Character Relationships</h2>")
    if data["relationships"]:
        char_map = {c["id"]: c["name"] for c in data["characters"]}
        parts.append("<ul>")
        for r in data["relationships"]:
            from_name = char_map.get(r["from"], "?")
            to_name = char_map.get(r["to"], "?")
            arrow = "↔" if r["bidirectional"] else "→"
            parts.append(f"<li><strong>{_esc(from_name)}</strong> {arrow} {_esc(r['type'] or 'related to')} {arrow} <strong>{_esc(to_name)}</strong>")
            if r["description"]:
                parts.append(f": {_esc(r['description'])}")
            parts.append("</li>")
        parts.append("</ul>")
    else:
        parts.append("<p>No relationships defined.</p>")

    # World entries
    parts.append(f"<h2>4. World Entries ({len(data['world_entries'])})</h2>")
    if data["world_entries"]:
        by_type: dict[str, list] = {}
        for e in data["world_entries"]:
            by_type.setdefault(e["type"], []).append(e)
        for t, entries in by_type.items():
            parts.append(f"<h3>{_esc(t.title())} ({len(entries)})</h3>")
            for e in entries:
                parts.append(f"<div class='world-card'>")
                parts.append(f"<h3>{_esc(e['name'])}</h3>")
                if e["category"]:
                    parts.append(f"<p><span class='badge'>{_esc(e['category'])}</span></p>")
                if e["description"]:
                    parts.append(f"<p><em>{_esc(e['description'])}</em></p>")
                if e["content"]:
                    parts.append(f"<p>{_esc(e['content'])}</p>")
                parts.append("</div>")
    else:
        parts.append("<p>No world entries yet.</p>")

    # Timeline
    parts.append(f"<h2>5. Timeline ({len(data['timeline'])})</h2>")
    if data["timeline"]:
        parts.append("<ul>")
        for ev in data["timeline"]:
            parts.append(f"<li><strong>{_esc(ev['story_date'])}</strong> — {_esc(ev['title'])}")
            if ev["event_type"]:
                parts.append(f" <span class='badge'>{_esc(ev['event_type'])}</span>")
            if ev["description"]:
                parts.append(f"<br><em>{_esc(ev['description'][:200])}</em>")
            parts.append("</li>")
        parts.append("</ul>")
    else:
        parts.append("<p>No timeline events yet.</p>")

    # Glossary
    parts.append(f"<h2>6. Glossary ({len(data['glossary'])})</h2>")
    if data["glossary"]:
        parts.append("<ul>")
        for g in data["glossary"]:
            parts.append(f"<li><span class='glossary-term'>{_esc(g['term'])}</span> <span class='badge'>{_esc(g['category'])}</span>")
            if g["definition"]:
                parts.append(f": {_esc(g['definition'])}")
            if g["alternates"]:
                parts.append(f" <em>(also: {_esc(', '.join(g['alternates']))})</em>")
            parts.append("</li>")
        parts.append("</ul>")
    else:
        parts.append("<p>No glossary terms yet.</p>")

    parts.append("</body></html>")
    return "".join(parts)


def render_txt(data: dict[str, Any]) -> str:
    parts: list[str] = []
    parts.append(f"{'='*60}")
    parts.append(f"  {data['title']}")
    if data["subtitle"]:
        parts.append(f"  {data['subtitle']}")
    parts.append(f"  by {data['author']}")
    parts.append(f"{'='*60}\n")
    if data["logline"]:
        parts.append(f"LOGLINE: {data['logline']}\n")
    st = data["stats"]
    parts.append(f"Chapters: {st['chapter_count']} | Characters: {st['character_count']} | "
                 f"World: {st['world_count']} | Words: {st['total_words']:,}\n")

    parts.append("\n" + "="*60 + "\nPLOT SUMMARY\n" + "="*60 + "\n")
    for i, ch in enumerate(data["chapters"], 1):
        parts.append(f"\n{i}. {ch['title']} ({ch['word_count']} words, {ch['status']})")
        if ch["synopsis"]:
            parts.append(f"   {ch['synopsis']}")

    parts.append("\n\n" + "="*60 + f"\nCHARACTERS ({len(data['characters'])})\n" + "="*60 + "\n")
    for c in data["characters"]:
        parts.append(f"\n--- {c['name']} ({c['role']}) ---")
        if c["age"]:
            parts.append(f"Age: {c['age']}")
        for field, label in [("physical", "Physical"), ("psychology", "Psychology"),
                              ("background", "Background"), ("philosophy", "Philosophy"),
                              ("voice", "Voice")]:
            if c[field]:
                parts.append(f"{label}: {c[field]}")

    parts.append("\n\n" + "="*60 + "\nWORLD ENTRIES\n" + "="*60 + "\n")
    for e in data["world_entries"]:
        parts.append(f"\n--- {e['name']} ({e['type']}) ---")
        if e["description"]:
            parts.append(e["description"])
        if e["content"]:
            parts.append(e["content"])

    parts.append("\n\n" + "="*60 + "\nTIMELINE\n" + "="*60 + "\n")
    for ev in data["timeline"]:
        parts.append(f"{ev['story_date']} — {ev['title']}")

    parts.append("\n\n" + "="*60 + "\nGLOSSARY\n" + "="*60 + "\n")
    for g in data["glossary"]:
        parts.append(f"{g['term']} ({g['category']}): {g['definition']}")

    return "\n".join(parts)


def render_md(data: dict[str, Any]) -> str:
    parts: list[str] = []
    parts.append(f"# {data['title']}")
    if data["subtitle"]:
        parts.append(f"\n*{data['subtitle']}*")
    parts.append(f"\n*by {data['author']}*\n")
    if data["logline"]:
        parts.append(f"> **Logline:** {data['logline']}\n")
    st = data["stats"]
    parts.append(f"**Stats:** {st['chapter_count']} chapters · {st['character_count']} characters · "
                 f"{st['world_count']} world entries · {st['total_words']:,} words\n")

    parts.append("\n## Plot Summary\n")
    for i, ch in enumerate(data["chapters"], 1):
        parts.append(f"{i}. **{ch['title']}** ({ch['word_count']} words, {ch['status']})")
        if ch["synopsis"]:
            parts.append(f"   - *{ch['synopsis']}*")

    parts.append(f"\n## Characters ({len(data['characters'])})\n")
    for c in data["characters"]:
        parts.append(f"### {c['name']} ({c['role']})\n")
        for field, label in [("physical", "Physical"), ("psychology", "Psychology"),
                              ("background", "Background"), ("philosophy", "Philosophy"),
                              ("voice", "Voice")]:
            if c[field]:
                parts.append(f"**{label}:** {c[field]}\n")

    parts.append(f"\n## World Entries ({len(data['world_entries'])})\n")
    for e in data["world_entries"]:
        parts.append(f"### {e['name']} ({e['type']})\n")
        if e["description"]:
            parts.append(f"*{e['description']}*\n")
        if e["content"]:
            parts.append(f"{e['content']}\n")

    parts.append(f"\n## Timeline ({len(data['timeline'])})\n")
    for ev in data["timeline"]:
        parts.append(f"- **{ev['story_date']}** — {ev['title']}")

    parts.append(f"\n## Glossary ({len(data['glossary'])})\n")
    for g in data["glossary"]:
        parts.append(f"- **{g['term']}** ({g['category']}): {g['definition']}")

    return "\n".join(parts)


def render(data: dict[str, Any], fmt: str) -> tuple[bytes, str, str]:
    """Render the story bible in the requested format. Returns (content, mime, filename)."""
    safe_title = data["title"].replace(" ", "_").lower()[:60] or "story_bible"
    fmt = fmt.lower()
    if fmt == "html":
        return render_html(data).encode("utf-8"), "text/html", f"{safe_title}_story_bible.html"
    if fmt == "txt":
        return render_txt(data).encode("utf-8"), "text/plain", f"{safe_title}_story_bible.txt"
    if fmt == "md":
        return render_md(data).encode("utf-8"), "text/markdown", f"{safe_title}_story_bible.md"
    if fmt == "json":
        return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"), "application/json", f"{safe_title}_story_bible.json"
    raise ValueError(f"Unknown format: {fmt}")
