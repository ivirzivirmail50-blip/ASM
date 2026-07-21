"""Character routes — list, detail, edit, graph, timeline, compare."""
from __future__ import annotations

import json
import logging

from flask import (Blueprint, abort, jsonify, render_template, request,
                   send_file, url_for)

from core.errors import AsmError, NotFoundError
from services import character_service, chapter_service, export_service
from services._common import load_json

log = logging.getLogger("asm.routes.characters")
bp = Blueprint("characters", __name__, url_prefix="/characters")


@bp.route("/")
def list_view():
    role = request.args.get("role", "all")
    search = request.args.get("q", "")
    sort = request.args.get("sort", "name")
    chars = character_service.list_characters(
        role=role if role != "all" else None,
        search=search or None, sort=sort,
    )
    return render_template("characters/list.html", characters=chars,
                           role=role, search=search, sort=sort,
                           active_nav="characters")


@bp.route("/new", methods=["GET", "POST"])
def new():
    if request.method == "POST":
        data = request.form
        try:
            ch = character_service.create_character(
                name=data.get("name", "").strip(),
                role=data.get("role", "supporting"),
                age=data.get("age") or None,
                gender=data.get("gender") or None,
                aliases=[a.strip() for a in data.get("aliases", "").split(",") if a.strip()],
                physical=data.get("physical") or None,
                psychology=data.get("psychology") or None,
                background=data.get("background") or None,
                philosophy=data.get("philosophy") or None,
                story_role=data.get("story_role") or None,
                voice=data.get("voice") or None,
                notes=data.get("notes") or None,
                philosophy_quotes=[q.strip() for q in data.getlist("quotes") if q.strip()],
            )
            return jsonify({"ok": True, "id": ch.id,
                            "url": url_for("characters.detail", character_id=ch.id)})
        except AsmError as exc:
            return jsonify({"ok": False, "error": exc.user_message}), exc.status_code
    return render_template("characters/new.html", active_nav="characters")


@bp.route("/<character_id>")
def detail(character_id: str):
    try:
        ch = character_service.get_character(character_id)
        groups = character_service.groups_for_character(character_id)
        rels = character_service.relationships_for(character_id)
        arcs = character_service.list_arcs(character_id)
        # Resolve linked chapters
        chapter_ids = load_json(ch.story_role_chapters, [])
        linked_chapters = []
        for cid in chapter_ids:
            try:
                linked_chapters.append(chapter_service.get_chapter(cid))
            except NotFoundError:
                pass
        # Chapters where this character appears
        all_chapters = chapter_service.list_chapters(sort="sort_order")[0]
        appearances = []
        for ch_obj in all_chapters:
            ids = load_json(ch_obj.character_ids, [])
            if character_id in ids:
                appearances.append(ch_obj)
        # All characters for dialogue generator dropdown
        all_chars = character_service.list_characters()
        all_chars_json = [{"id": c.id, "name": c.name} for c in all_chars]
        return render_template("characters/detail.html", character=ch,
                               groups=groups, relationships=rels, arcs=arcs,
                               linked_chapters=linked_chapters,
                               appearances=appearances,
                               aliases=load_json(ch.aliases, []),
                               quotes=load_json(ch.philosophy_quotes, []),
                               all_chars_json=all_chars_json,
                               active_nav="characters")
    except NotFoundError:
        abort(404)


@bp.route("/<character_id>/edit", methods=["GET", "POST"])
def edit(character_id: str):
    try:
        ch = character_service.get_character(character_id)
    except NotFoundError:
        abort(404)
    if request.method == "POST":
        data = request.form
        try:
            fields = {
                "name": data.get("name", "").strip(),
                "role": data.get("role", "supporting"),
                "age": data.get("age") or None,
                "gender": data.get("gender") or None,
                "physical": data.get("physical") or None,
                "psychology": data.get("psychology") or None,
                "background": data.get("background") or None,
                "philosophy": data.get("philosophy") or None,
                "story_role": data.get("story_role") or None,
                "voice": data.get("voice") or None,
                "notes": data.get("notes") or None,
                "aliases": [a.strip() for a in data.get("aliases", "").split(",") if a.strip()],
                "philosophy_quotes": [q.strip() for q in data.getlist("quotes") if q.strip()],
            }
            ch = character_service.update_character(character_id, **fields)
            return jsonify({"ok": True, "id": ch.id,
                            "url": url_for("characters.detail", character_id=ch.id)})
        except AsmError as exc:
            return jsonify({"ok": False, "error": exc.user_message}), exc.status_code
    return render_template("characters/edit.html", character=ch,
                           aliases=load_json(ch.aliases, []),
                           quotes=load_json(ch.philosophy_quotes, []),
                           active_nav="characters")


@bp.route("/<character_id>/delete", methods=["POST"])
def delete(character_id: str):
    try:
        label = character_service.delete_character(character_id)
        return jsonify({"ok": True, "url": url_for("characters.list_view"),
                        "label": label, "undoable": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/graph")
def graph():
    chars = character_service.list_characters()
    groups = character_service.list_groups()
    rels = character_service.list_relationships()
    return render_template("characters/graph.html", characters=chars,
                           groups=groups, relationships=rels,
                           active_nav="characters_graph")


@bp.route("/groups", methods=["GET", "POST"])
def groups():
    """Manage character groups: CRUD + drag-drop members between groups."""
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form
        action = data.get("action", "create")
        try:
            if action == "create":
                g = character_service.create_group(
                    data.get("name", "").strip(),
                    description=data.get("description") or None,
                    color=data.get("color", "#6366f1"),
                )
                return jsonify({"ok": True, "id": g.id, "name": g.name})
            elif action == "delete":
                gid = data.get("group_id")
                from core.db import write_transaction
                from models.character import CharacterGroup, CharacterGroupMember
                with write_transaction() as s:
                    s.query(CharacterGroupMember).filter_by(group_id=gid).delete()
                    g = s.get(CharacterGroup, gid)
                    if g:
                        s.delete(g)
                return jsonify({"ok": True})
            elif action == "assign":
                character_service.assign_to_group(
                    data.get("character_id"), data.get("group_id"))
                return jsonify({"ok": True})
            elif action == "remove":
                character_service.remove_from_group(
                    data.get("character_id"), data.get("group_id"))
                return jsonify({"ok": True})
            elif action == "update":
                from core.db import write_transaction
                from models.character import CharacterGroup
                with write_transaction() as s:
                    g = s.get(CharacterGroup, data.get("group_id"))
                    if g:
                        if data.get("name"):
                            g.name = data["name"]
                        if data.get("description") is not None:
                            g.description = data["description"]
                        if data.get("color"):
                            g.color = data["color"]
                return jsonify({"ok": True})
            return jsonify({"ok": False, "error": "Unknown action"}), 400
        except AsmError as exc:
            return jsonify({"ok": False, "error": exc.user_message}), exc.status_code
    # GET: render page
    groups_list = character_service.list_groups()
    all_chars = character_service.list_characters()
    # Build group → members mapping
    group_members = {}
    for g in groups_list:
        group_members[g.id] = character_service.characters_in_group(g.id)
    # Find ungrouped characters
    grouped_ids = set()
    for members in group_members.values():
        for m in members:
            grouped_ids.add(m.id)
    ungrouped = [c for c in all_chars if c.id not in grouped_ids]
    return render_template("characters/groups.html", groups=groups_list,
                           group_members=group_members,
                           ungrouped=ungrouped,
                           active_nav="characters_groups")


@bp.route("/graph/data")
def graph_data():
    """JSON endpoint: nodes + edges for vis-network."""
    chars = character_service.list_characters()
    groups = character_service.list_groups()
    rels = character_service.list_relationships()
    # Group memberships
    group_members: dict[str, list[str]] = {}
    for g in groups:
        members = character_service.characters_in_group(g.id)
        group_members[g.id] = [m.id for m in members]

    # Build set of valid node IDs (characters + groups)
    char_ids = {c.id for c in chars}
    group_ids = {g.id for g in groups}

    nodes = []
    for c in chars:
        # Find primary group for color
        color = c.avatar_color or "#6366f1"
        nodes.append({
            "id": c.id,
            "label": c.name,
            "title": f"{c.name} ({c.role})",
            "color": color,
            "x": c.graph_x,
            "y": c.graph_y,
            "shape": "dot",
            "size": 22 if c.role == "protagonist" else (18 if c.role == "antagonist" else 14),
            "font": {"color": "#e2e8f0", "size": 13},
        })
    edges = []
    for r in rels:
        from_id = r.from_character_id
        to_id = r.to_character_id
        # Check if from/to is a group (stored with g- prefix) or character
        from_is_group = from_id.startswith("g-") and from_id[2:] in group_ids
        to_is_group = to_id.startswith("g-") and to_id[2:] in group_ids
        from_valid = from_id in char_ids or from_is_group
        to_valid = to_id in char_ids or to_is_group
        if not from_valid or not to_valid:
            continue  # skip orphaned relationships
        color = _edge_color(r.relationship_type)
        # Use display label showing group name if it's a group
        from_label = ""
        to_label = ""
        if from_is_group:
            g = next((x for x in groups if x.id == from_id[2:]), None)
            from_label = g.name if g else from_id
        if to_is_group:
            g = next((x for x in groups if x.id == to_id[2:]), None)
            to_label = g.name if g else to_id
        edges.append({
            "id": r.id,
            "from": from_id,
            "to": to_id,
            "label": r.relationship_type.replace("_", " "),
            "title": r.description or r.relationship_type.replace("_", " "),
            "color": {"color": color, "highlight": color, "hover": color},
            "dashes": r.relationship_type in ("rival_of", "enemy_of", "betrayed_by"),
            "arrows": {} if r.is_bidirectional else {"to": {"enabled": True}},
            "width": 2,
        })
    # Group-to-group edges (dashed)
    for g1 in groups:
        for g2 in groups:
            if g1.id >= g2.id:
                continue
            # Are there members with relationships across?
            m1 = group_members.get(g1.id, [])
            m2 = group_members.get(g2.id, [])
            has_cross = any(
                any(r.from_character_id == a and r.to_character_id == b
                    for r in rels)
                for a in m1 for b in m2
            )
            if has_cross:
                edges.append({
                    "id": f"g2g-{g1.id}-{g2.id}",
                    "from": f"g-{g1.id}", "to": f"g-{g2.id}",
                    "label": "group link", "color": {"color": "#ef4444"},
                    "dashes": True, "width": 1,
                })
    # Group nodes — use "g-<id>" as node ID so backend can distinguish groups from characters
    for g in groups:
        nodes.append({
            "id": f"g-{g.id}",
            "label": g.name,
            "title": g.description or g.name,
            "color": g.color or "#6366f1",
            "shape": "ellipse",
            "size": 25,
            "font": {"color": "#fff", "size": 12, "bold": True},
            "group": True,
        })
        # Group-to-member edges (dashed orange)
        for m in group_members.get(g.id, []):
            edges.append({
                "id": f"g2m-{g.id}-{m}",
                "from": f"g-{g.id}", "to": m,
                "color": {"color": "#f59e0b"},
                "dashes": True, "width": 1,
            })
    return jsonify({"nodes": nodes, "edges": edges,
                    "groups": [{"id": g.id, "name": g.name, "color": g.color}
                               for g in groups]})


def _edge_color(rel_type: str) -> str:
    return {
        "married_to": "#ec4899", "loves": "#ec4899",
        "parent_of": "#22c55e", "mentors": "#22c55e",
        "friend_of": "#3b82f6", "serves": "#3b82f6",
        "rival_of": "#ef4444", "enemy_of": "#ef4444", "betrayed_by": "#ef4444",
        "custom": "#a78bfa",
    }.get(rel_type, "#94a3b8")


@bp.route("/graph/save-position", methods=["POST"])
def graph_save_position():
    data = request.get_json(silent=True) or {}
    cid = data.get("id")
    x = int(data.get("x", 0))
    y = int(data.get("y", 0))
    try:
        character_service.update_graph_position(cid, x, y)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/relationships/new", methods=["POST"])
def new_relationship():
    data = request.get_json(silent=True) or request.form
    try:
        rel = character_service.create_relationship(
            from_id=data.get("from_id"),
            to_id=data.get("to_id"),
            rel_type=data.get("type", "custom"),
            description=data.get("description"),
            bidirectional=bool(data.get("bidirectional", False)),
        )
        return jsonify({"ok": True, "id": rel.id})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/relationships/<rel_id>/delete", methods=["POST"])
def delete_relationship(rel_id: str):
    try:
        character_service.delete_relationship(rel_id)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/<character_id>/arcs", methods=["POST"])
def create_arc(character_id: str):
    """Create a character arc."""
    data = request.get_json(silent=True) or request.form
    try:
        stages = data.get("stages")
        if isinstance(stages, str):
            import json
            try:
                stages = json.loads(stages)
            except (json.JSONDecodeError, TypeError):
                stages = []
        arc = character_service.create_arc(
            character_id,
            data.get("arc_name", "").strip(),
            description=data.get("description") or None,
            stages=stages or [],
        )
        return jsonify({"ok": True, "id": arc.id, "arc_name": arc.arc_name})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/arcs/<arc_id>", methods=["POST", "DELETE"])
def update_arc(arc_id: str):
    """Update or delete a character arc."""
    data = request.get_json(silent=True) or request.form
    action = data.get("action", "update")
    try:
        if action == "delete":
            character_service.delete_arc(arc_id)
            return jsonify({"ok": True})
        # Update
        stages = data.get("stages")
        if isinstance(stages, str):
            import json
            try:
                stages = json.loads(stages)
            except (json.JSONDecodeError, TypeError):
                stages = None
        kwargs = {}
        if data.get("arc_name") is not None:
            kwargs["arc_name"] = data["arc_name"]
        if data.get("description") is not None:
            kwargs["description"] = data["description"]
        if stages is not None:
            kwargs["stages"] = stages
        arc = character_service.update_arc(arc_id, **kwargs)
        return jsonify({"ok": True, "id": arc.id})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/<character_id>/export/<fmt>")
def export(character_id: str, fmt: str):
    try:
        content, mimetype, filename = export_service.export_character_sheet(character_id, fmt)
        import io
        return send_file(io.BytesIO(content), mimetype=mimetype,
                         as_attachment=True, download_name=filename)
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/compare")
def compare():
    from services import character_service
    all_chars = character_service.list_characters()
    ch1_id = request.args.get("ch1")
    ch2_id = request.args.get("ch2")
    export_fmt = request.args.get("export")
    ch1 = character_service.get_character(ch1_id) if ch1_id else None
    ch2 = character_service.get_character(ch2_id) if ch2_id else None
    # Export comparison
    if export_fmt and ch1 and ch2:
        from services.export_service import _character_sheet_pdf
        if export_fmt == "txt":
            text = _comparison_as_text(ch1, ch2)
            from flask import Response
            return Response(text, mimetype="text/plain",
                            headers={"Content-Disposition":
                                     f"attachment; filename=compare_{ch1.name}_vs_{ch2.name}.txt"})
        if export_fmt == "pdf":
            pdf_data = _comparison_as_pdf(ch1, ch2)
            import io
            return send_file(io.BytesIO(pdf_data), mimetype="application/pdf",
                             as_attachment=True,
                             download_name=f"compare_{ch1.name}_vs_{ch2.name}.pdf")
    return render_template("characters/compare.html",
                           all_chars=all_chars, ch1=ch1, ch2=ch2,
                           active_nav="characters")


def _comparison_as_text(ch1, ch2) -> str:
    from services._common import load_json
    lines = [f"CHARACTER COMPARISON: {ch1.name} vs {ch2.name}",
             "=" * 60, ""]
    fields = [
        ("Role", "role"), ("Age", "age"), ("Gender", "gender"),
        ("Aliases", "aliases"), ("Physical", "physical"),
        ("Psychology", "psychology"), ("Background", "background"),
        ("Philosophy", "philosophy"), ("Story Role", "story_role"),
        ("Voice", "voice"), ("Notes", "notes"),
    ]
    for label, key in fields:
        if key == "aliases":
            v1 = ", ".join(load_json(getattr(ch1, key), []))
            v2 = ", ".join(load_json(getattr(ch2, key), []))
        else:
            v1 = getattr(ch1, key, "") or "—"
            v2 = getattr(ch2, key, "") or "—"
        lines.append(f"--- {label} ---")
        lines.append(f"  {ch1.name}: {v1}")
        lines.append(f"  {ch2.name}: {v2}")
        diff = "  (DIFFERENT)" if v1 != v2 else "  (same)"
        lines.append(diff)
        lines.append("")
    return "\n".join(lines)


def _comparison_as_pdf(ch1, ch2) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                     Table, TableStyle)
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from services._common import load_json
    import io as _io

    buf = _io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("Title", parent=styles["Title"],
                           alignment=TA_CENTER, fontSize=18, spaceAfter=12)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"],
                        fontSize=12, spaceBefore=10, spaceAfter=6,
                        textColor=colors.HexColor("#6366f1"))
    body = ParagraphStyle("Body", parent=styles["BodyText"],
                          fontSize=9, leading=12, spaceAfter=4)
    story = [
        Paragraph(f"{ch1.name} vs {ch2.name}", title),
        Spacer(1, 12),
    ]
    fields = [
        ("Role", "role"), ("Age", "age"), ("Gender", "gender"),
        ("Physical", "physical"), ("Psychology", "psychology"),
        ("Background", "background"), ("Philosophy", "philosophy"),
        ("Story Role", "story_role"), ("Voice", "voice"), ("Notes", "notes"),
    ]
    for label, key in fields:
        v1 = (getattr(ch1, key, "") or "—")
        v2 = (getattr(ch2, key, "") or "—")
        v1 = v1.replace("&", "&amp;").replace("<", "&lt;") if isinstance(v1, str) else str(v1)
        v2 = v2.replace("&", "&amp;").replace("<", "&lt;") if isinstance(v2, str) else str(v2)
        diff = " ⚠" if v1 != v2 else ""
        story.append(Paragraph(f"{label}{diff}", h2))
        data = [
            [Paragraph(f"<b>{ch1.name}</b>", body), Paragraph(f"<b>{ch2.name}</b>", body)],
            [Paragraph(v1, body), Paragraph(v2, body)],
        ]
        t = Table(data, colWidths=[3.4*inch, 3.4*inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a2240")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#2c365d")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 8))
    doc.build(story)
    return buf.getvalue()


@bp.route("/<character_id>/timeline")
def timeline(character_id: str):
    """Character timeline: vertical list of appearances across chapters + arc markers."""
    try:
        from services import chapter_service
        ch = character_service.get_character(character_id)
        arcs = character_service.list_arcs(character_id)
        # All chapters sorted by sort_order
        all_chapters = chapter_service.list_chapters(sort="sort_order")[0]
        appearances = []
        for ch_obj in all_chapters:
            ids = load_json(ch_obj.character_ids, [])
            if character_id in ids:
                appearances.append(ch_obj)
        # Group arc stages by chapter id
        arc_stage_map: dict[str, list[dict]] = {}
        for arc in arcs:
            stages = load_json(arc.stages, [])
            for stage in stages:
                for cid in (stage.get("chapter_ids") or []):
                    arc_stage_map.setdefault(cid, []).append({
                        "arc_name": arc.arc_name,
                        "stage_name": stage.get("name"),
                        "status": stage.get("status"),
                    })
        return render_template("characters/timeline.html", character=ch,
                               appearances=appearances, arcs=arcs,
                               arc_stage_map=arc_stage_map,
                               active_nav="characters")
    except NotFoundError:
        abort(404)
