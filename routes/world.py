"""World routes — index, edit, versions, map."""
from __future__ import annotations

import json
import logging

from flask import (Blueprint, abort, jsonify, render_template, request,
                   url_for)

from core.errors import AsmError, NotFoundError
from services import world_service
from services._common import load_json

log = logging.getLogger("asm.routes.world")
bp = Blueprint("world", __name__, url_prefix="/world")


@bp.route("/")
def index():
    type_ = request.args.get("type", "location")
    search = request.args.get("q", "")
    category = request.args.get("category", "")
    sort = request.args.get("sort", "name")
    page = max(1, request.args.get("page", 1, type=int))
    entries, total = world_service.list_entries(
        type_=type_, search=search or None,
        category=category or None, sort=sort,
        page=page,
    )
    # Get per_page from settings for pagination display
    from core.db import read_session
    from models.settings import Setting
    with read_session() as s:
        per_page = int(Setting.get(s, "world_per_page", 40))
    pages = max(1, (total + per_page - 1) // per_page)
    return render_template("world/index.html", entries=entries,
                           type_=type_, search=search, category=category,
                           sort=sort, page=page, pages=pages, total=total,
                           types=world_service.get_all_types(),
                           active_nav="world")


@bp.route("/new", methods=["GET", "POST"])
def new():
    if request.method == "POST":
        data = request.form
        try:
            metadata = {}
            for k in request.form:
                if k.startswith("metadata_"):
                    field = k[len("metadata_"):]
                    val = data[k].strip()
                    if val:
                        metadata[field] = val
            e = world_service.create_entry(
                type_=data.get("type", "location"),
                name=data.get("name", "").strip(),
                category=data.get("category") or None,
                description=data.get("description") or None,
                content=data.get("content") or None,
                notes=data.get("notes") or None,
                metadata=metadata,
                parent_id=data.get("parent_id") or None,
            )
            return jsonify({"ok": True, "id": e.id,
                            "url": url_for("world.detail", entry_id=e.id)})
        except AsmError as exc:
            return jsonify({"ok": False, "error": exc.user_message}), exc.status_code
    return render_template("world/new.html",
                           types=world_service.get_all_types(),
                           metadata_fields=world_service.METADATA_FIELDS,
                           active_nav="world")


@bp.route("/<entry_id>")
def detail(entry_id: str):
    try:
        e = world_service.get_entry(entry_id)
        out_rels, in_rels = world_service.relations_for(entry_id)
        metadata = load_json(e.metadata_, {}) or {}
        return render_template("world/detail.html", entry=e,
                               metadata=metadata,
                               out_relations=out_rels, in_relations=in_rels,
                               active_nav="world")
    except NotFoundError:
        abort(404)


@bp.route("/<entry_id>/edit", methods=["GET", "POST"])
def edit(entry_id: str):
    try:
        e = world_service.get_entry(entry_id)
    except NotFoundError:
        abort(404)
    if request.method == "POST":
        data = request.form
        try:
            metadata = {}
            for k in request.form:
                if k.startswith("metadata_"):
                    field = k[len("metadata_"):]
                    val = data[k].strip()
                    if val:
                        metadata[field] = val
            world_service.update_entry(entry_id,
                type_=data.get("type") or None,
                name=data.get("name", "").strip(),
                category=data.get("category") or None,
                description=data.get("description") or None,
                content=data.get("content") or None,
                notes=data.get("notes") or None,
                metadata=metadata,
            )
            return jsonify({"ok": True, "url": url_for("world.detail", entry_id=entry_id)})
        except AsmError as exc:
            return jsonify({"ok": False, "error": exc.user_message}), exc.status_code
    metadata = load_json(e.metadata_, {}) or {}
    return render_template("world/edit.html", entry=e, metadata=metadata,
                           types=world_service.get_all_types(),
                           metadata_fields=world_service.METADATA_FIELDS,
                           active_nav="world")


@bp.route("/<entry_id>/delete", methods=["POST"])
def delete(entry_id: str):
    try:
        label = world_service.delete_entry(entry_id)
        return jsonify({"ok": True, "url": url_for("world.index"),
                        "label": label, "undoable": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/<entry_id>/duplicate", methods=["POST"])
def duplicate(entry_id: str):
    try:
        e = world_service.duplicate_entry(entry_id)
        return jsonify({"ok": True, "id": e.id,
                        "url": url_for("world.detail", entry_id=e.id)})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/<entry_id>/versions")
def versions(entry_id: str):
    try:
        e = world_service.get_entry(entry_id)
        vs = world_service.list_versions(entry_id)
        return render_template("world/versions.html", entry=e, versions=vs,
                               active_nav="world")
    except NotFoundError:
        abort(404)


@bp.route("/<entry_id>/versions/compare")
def versions_compare(entry_id: str):
    """Side-by-side compare two versions of a world entry."""
    v1_id = request.args.get("v1")
    v2_id = request.args.get("v2")
    try:
        e = world_service.get_entry(entry_id)
        vs = world_service.list_versions(entry_id)
        vmap = {v.id: v for v in vs}
        if v1_id not in vmap or v2_id not in vmap:
            abort(400, "Invalid version ids")
        from services._common import load_json
        snap1 = load_json(vmap[v1_id].snapshot, {}) or {}
        snap2 = load_json(vmap[v2_id].snapshot, {}) or {}
        # Compute field-level diff
        all_keys = sorted(set(list(snap1.keys()) + list(snap2.keys())))
        diff_rows = []
        for k in all_keys:
            v1 = snap1.get(k, "")
            v2 = snap2.get(k, "")
            if v1 != v2:
                diff_rows.append({"field": k, "v1": v1, "v2": v2, "changed": True})
            else:
                diff_rows.append({"field": k, "v1": v1, "v2": v2, "changed": False})
        return render_template("world/versions_compare.html",
                               entry=e, v1=vmap[v1_id], v2=vmap[v2_id],
                               diff_rows=diff_rows, active_nav="world")
    except NotFoundError:
        abort(404)


@bp.route("/<entry_id>/versions/<version_id>/restore", methods=["POST"])
def restore_version(entry_id: str, version_id: str):
    try:
        world_service.restore_version(entry_id, version_id)
        return jsonify({"ok": True, "url": url_for("world.detail", entry_id=entry_id)})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/reorder", methods=["POST"])
def reorder():
    data = request.get_json(silent=True) or {}
    type_ = data.get("type", "location")
    ordered_ids = data.get("order", [])
    try:
        world_service.reorder_entries(type_, ordered_ids)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/map")
def map_view():
    entries = world_service.get_map_entries()
    # Check if a map image is configured
    from config import Config
    map_image_path = None
    maps_dir = Config.MEDIA_DIR / "maps"
    if maps_dir.exists():
        # Find the most recent map image
        images = sorted(maps_dir.glob("map_*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if images:
            map_image_path = f"/media/maps/{images[0].name}"
    return render_template("world/map.html", entries=entries,
                           map_image_path=map_image_path,
                           active_nav="world_map")


@bp.route("/map/upload", methods=["POST"])
def map_upload():
    """Upload a map background image."""
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file provided"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"ok": False, "error": "Empty filename"}), 400
    # Validate image extension
    allowed = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
    import os
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in allowed:
        return jsonify({"ok": False, "error": f"Extension {ext} not allowed. Use: {', '.join(sorted(allowed))}"}), 400
    # Read the file content into memory (avoids seek issues with Flask's file storage)
    content = f.read()
    actual_size = len(content)
    if actual_size > 10 * 1024 * 1024:
        return jsonify({"ok": False, "error": f"Image too large ({actual_size // 1024} KB, max 10 MB)"}), 400
    if actual_size == 0:
        return jsonify({"ok": False, "error": "File is empty"}), 400
    from config import Config
    maps_dir = Config.MEDIA_DIR / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)
    import time
    safe_name = f"map_{int(time.time())}{ext}"
    target = maps_dir / safe_name
    target.write_bytes(content)
    log.info("Map image uploaded: %s (%d KB)", safe_name, actual_size // 1024)
    return jsonify({"ok": True, "path": f"/media/maps/{safe_name}"})


@bp.route("/hierarchy")
def hierarchy():
    """Tree view of location hierarchy."""
    tree = world_service.get_hierarchy()
    return render_template("world/hierarchy.html", tree=tree,
                           active_nav="world_hierarchy")


@bp.route("/map/pin", methods=["POST"])
def map_save_pin():
    data = request.get_json(silent=True) or {}
    try:
        # Allow null x/y to remove the pin
        x_raw = data.get("x")
        y_raw = data.get("y")
        x = float(x_raw) if x_raw is not None else None
        y = float(y_raw) if y_raw is not None else None
        world_service.update_pin(
            data.get("id"), x, y, data.get("label"),
        )
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "error": f"Invalid coordinates: {exc}"}), 400


@bp.route("/relations/new", methods=["POST"])
def new_relation():
    data = request.get_json(silent=True) or request.form
    try:
        rel = world_service.create_relation(
            from_id=data.get("from_id"),
            to_id=data.get("to_id"),
            rel_type=data.get("type", "located_in"),
            description=data.get("description"),
        )
        return jsonify({"ok": True, "id": rel.id})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/relations/<rel_id>/delete", methods=["POST"])
def delete_relation(rel_id: str):
    try:
        world_service.delete_relation(rel_id)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


# ---- Travel Routes (character journeys on map) ----

@bp.route("/map/routes")
def map_routes_api():
    """Get all travel routes as JSON."""
    from services import travel_service
    return jsonify({"routes": travel_service.get_routes_json()})


@bp.route("/map/routes", methods=["POST"])
def map_routes_create():
    """Create a new travel route."""
    from services import travel_service
    data = request.get_json(silent=True) or {}
    try:
        r = travel_service.create_route(
            character_id=data.get("character_id", ""),
            name=data.get("name", "New Route"),
            color=data.get("color", "#6366f1"),
            waypoints=data.get("waypoints", []),
        )
        return jsonify({"ok": True, "id": r.id})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/map/routes/<route_id>", methods=["POST", "DELETE"])
def map_routes_update(route_id: str):
    """Update or delete a travel route."""
    from services import travel_service
    data = request.get_json(silent=True) or {}
    if data.get("action") == "delete":
        travel_service.delete_route(route_id)
        return jsonify({"ok": True})
    r = travel_service.update_route(route_id, **data)
    if r is None:
        return jsonify({"ok": False, "error": "Route not found"}), 404
    return jsonify({"ok": True})
