"""Chapter routes — list, upload, detail, edit, versions, diff, reorder."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from flask import (Blueprint, abort, jsonify, render_template, request,
                   send_file, url_for)

from core.errors import AsmError, NotFoundError, ValidationError
from services import chapter_service, diff_service
from services._common import load_json

log = logging.getLogger("asm.routes.chapters")
bp = Blueprint("chapters", __name__, url_prefix="/chapters")


@bp.route("/")
def list_view():
    page = max(1, request.args.get("page", 1, type=int))
    status = request.args.get("status", "all")
    sort = request.args.get("sort", "sort_order")
    search = request.args.get("q", "")
    chapters, total = chapter_service.list_chapters(
        status=status if status != "all" else None,
        sort=sort, search=search or None, page=page,
    )
    per_page = 30
    pages = max(1, (total + per_page - 1) // per_page)
    return render_template(
        "chapters/list.html",
        chapters=chapters, total=total, page=page, pages=pages,
        status=status, sort=sort, search=search,
        active_nav="chapters",
    )


@bp.route("/new", methods=["GET", "POST"])
def new():
    if request.method == "POST":
        data = request.form
        try:
            ch = chapter_service.create_chapter(
                title=data.get("title", "").strip(),
                content=data.get("content", "").strip(),
                synopsis=data.get("synopsis", "").strip(),
                status=data.get("status", "draft"),
                target_word_count=int(data.get("target_word_count") or 0) or None,
                tags=[t.strip() for t in data.get("tags", "").split(",") if t.strip()],
                character_ids=request.form.getlist("character_ids"),
            )
            return jsonify({"ok": True, "id": ch.id,
                            "url": url_for("chapters.detail", chapter_id=ch.id)})
        except AsmError as exc:
            return jsonify({"ok": False, "error": exc.user_message}), exc.status_code
    # GET: render form
    from services import character_service
    characters = character_service.list_characters()
    prompt = request.args.get("prompt", "")
    template_id = request.args.get("template", "")
    prefill_content = ""
    prefill_synopsis = ""
    if template_id:
        try:
            from services.snippet_service import get_snippet
            t = get_snippet(template_id)
            prefill_content = t.content or ""
        except Exception:
            pass
    elif prompt:
        # Insert the prompt as a quoted epigraph at the top of the chapter
        prefill_content = f"> {prompt}\n\n"
        prefill_synopsis = prompt[:200]
    return render_template("chapters/new.html", characters=characters,
                           active_nav="chapters",
                           prefill_content=prefill_content,
                           prefill_synopsis=prefill_synopsis)


@bp.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        if "file" not in request.files:
            return jsonify({"ok": False, "error": "No file provided"}), 400
        f = request.files["file"]
        if not f.filename:
            return jsonify({"ok": False, "error": "Empty filename"}), 400
        try:
            content = f.read()
            ch = chapter_service.upload_new_chapter(
                filename=f.filename, content=content,
                title=request.form.get("title") or None,
                status=request.form.get("status", "draft"),
            )
            return jsonify({"ok": True, "id": ch.id,
                            "url": url_for("chapters.detail", chapter_id=ch.id)})
        except AsmError as exc:
            return jsonify({"ok": False, "error": exc.user_message}), exc.status_code
    return render_template("chapters/upload.html", active_nav="chapters")


@bp.route("/bulk-import", methods=["GET", "POST"])
def bulk_import():
    """Bulk import multiple files as chapters or world entries.

    POST expects multipart/form-data with:
    - files[]: multiple files
    - import_as: "chapter" or "world_entry"
    - world_type: (for world_entry) e.g. "lore", "location"
    - status: (for chapter) default "draft"
    """
    if request.method == "POST":
        files = request.files.getlist("files")
        if not files or not files[0].filename:
            return jsonify({"ok": False, "error": "No files provided"}), 400
        import_as = request.form.get("import_as", "chapter")
        world_type = request.form.get("world_type", "lore")
        status = request.form.get("status", "draft")
        results = []
        errors = []
        for f in files:
            if not f.filename:
                continue
            try:
                content = f.read()
                if import_as == "chapter":
                    ch = chapter_service.upload_new_chapter(
                        filename=f.filename, content=content,
                        status=status,
                    )
                    results.append({
                        "filename": f.filename,
                        "ok": True,
                        "title": ch.title,
                        "id": ch.id,
                        "url": url_for("chapters.detail", chapter_id=ch.id),
                    })
                elif import_as == "world_entry":
                    from services import world_service
                    from security.upload import parse_uploaded_file
                    import os
                    text, fmt = parse_uploaded_file(f.filename, content)
                    name = os.path.splitext(f.filename)[0][:300]
                    e = world_service.create_entry(
                        type_=world_type,
                        name=name,
                        content=text,
                        description=f"Imported from {f.filename}",
                    )
                    results.append({
                        "filename": f.filename,
                        "ok": True,
                        "title": e.name,
                        "id": e.id,
                        "url": url_for("world.detail", entry_id=e.id),
                    })
            except Exception as exc:
                errors.append({"filename": f.filename, "error": str(exc)})
        return jsonify({
            "ok": len(errors) == 0,
            "imported": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors,
        })
    return render_template("chapters/bulk_import.html", active_nav="chapters")


@bp.route("/<chapter_id>")
def detail(chapter_id: str):
    try:
        ch = chapter_service.get_chapter(chapter_id)
        versions = chapter_service.get_chapter_with_versions(chapter_id)[1]
        prev_n, next_n = chapter_service.get_neighbors(chapter_id)
        from services import character_service
        # Resolve linked characters
        char_ids = load_json(ch.character_ids, [])
        characters = [character_service.get_character(cid) for cid in char_ids]
        return render_template("chapters/detail.html", chapter=ch,
                               versions=versions, prev_ch=prev_n, next_ch=next_n,
                               characters=characters, tags=load_json(ch.tags, []),
                               active_nav="chapters")
    except NotFoundError:
        abort(404)


@bp.route("/<chapter_id>/edit", methods=["GET", "POST"])
def edit(chapter_id: str):
    try:
        ch = chapter_service.get_chapter(chapter_id)
    except NotFoundError:
        abort(404)
    if request.method == "POST":
        data = request.form
        try:
            ch = chapter_service.update_chapter(
                chapter_id,
                title=data.get("title", "").strip() or None,
                content=data.get("content", "").strip(),
                synopsis=data.get("synopsis", "").strip() or None,
                status=data.get("status") or None,
                target_word_count=int(data.get("target_word_count") or 0) or None,
                tags=[t.strip() for t in data.get("tags", "").split(",") if t.strip()],
                character_ids=request.form.getlist("character_ids"),
                create_version=True,
            )
            return jsonify({"ok": True, "id": ch.id,
                            "url": url_for("chapters.detail", chapter_id=ch.id)})
        except AsmError as exc:
            return jsonify({"ok": False, "error": exc.user_message}), exc.status_code
    from services import character_service
    characters = character_service.list_characters()
    return render_template("chapters/edit.html", chapter=ch,
                           characters=characters,
                           tags=load_json(ch.tags, []),
                           linked_char_ids=load_json(ch.character_ids, []),
                           active_nav="chapters")


@bp.route("/<chapter_id>/autosave", methods=["POST"])
def autosave(chapter_id: str):
    """Autosave content only — no version row created."""
    try:
        data = request.get_json(silent=True) or {}
        content = data.get("content", "")
        ch = chapter_service.update_chapter(
            chapter_id, content=content, create_version=False,
        )
        return jsonify({"ok": True, "word_count": ch.word_count})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/<chapter_id>/cycle-status", methods=["POST"])
def cycle_status(chapter_id: str):
    """Cycle chapter status: draft → revised → final → draft. Creates a version snapshot."""
    try:
        ch = chapter_service.get_chapter(chapter_id)
        next_status = {"draft": "revised", "revised": "final", "final": "draft"}.get(
            ch.status, "draft"
        )
        ch = chapter_service.update_chapter(
            chapter_id, status=next_status, create_version=True,
            version_source="status_change",
            version_notes=f"Status: {ch.status} → {next_status}",
        )
        return jsonify({"ok": True, "status": next_status})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/<chapter_id>/delete", methods=["POST"])
def delete(chapter_id: str):
    try:
        label = chapter_service.delete_chapter(chapter_id)
        return jsonify({"ok": True, "url": url_for("chapters.list_view"),
                        "label": label, "undoable": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/reorder", methods=["POST"])
def reorder():
    data = request.get_json(silent=True) or {}
    ordered_ids = data.get("order", [])
    try:
        chapter_service.reorder_chapters(ordered_ids)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/bulk-status", methods=["POST"])
def bulk_status():
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])
    new_status = data.get("status", "")
    try:
        chapter_service.bulk_status(ids, new_status)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/<chapter_id>/versions")
def versions(chapter_id: str):
    try:
        ch, vs = chapter_service.get_chapter_with_versions(chapter_id)
        return render_template("chapters/versions.html", chapter=ch, versions=vs,
                               active_nav="chapters")
    except NotFoundError:
        abort(404)


@bp.route("/<chapter_id>/versions/compare")
def versions_compare(chapter_id: str):
    v1 = request.args.get("v1")
    v2 = request.args.get("v2")
    try:
        ch = chapter_service.get_chapter(chapter_id)
        vs = chapter_service.get_chapter_with_versions(chapter_id)[1]
        vmap = {v.id: v for v in vs}
        if v1 not in vmap or v2 not in vmap:
            abort(400, "Invalid version ids")
        a = vmap[v1].content or ""
        b = vmap[v2].content or ""
        diff = diff_service.line_diff(a, b)
        return render_template(
            "chapters/versions_compare.html", chapter=ch,
            v1=vmap[v1], v2=vmap[v2], diff=diff,
            stats=diff_service.stats(a, b),
            active_nav="chapters",
        )
    except NotFoundError:
        abort(404)


@bp.route("/<chapter_id>/reupload", methods=["POST"])
def reupload(chapter_id: str):
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"ok": False, "error": "Empty filename"}), 400
    try:
        content = f.read()
        ch = chapter_service.reupload_chapter(chapter_id, filename=f.filename, content=content)
        return jsonify({"ok": True, "id": ch.id,
                        "url": url_for("chapters.detail", chapter_id=ch.id)})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/<chapter_id>/split", methods=["POST"])
def split(chapter_id: str):
    data = request.get_json(silent=True) or {}
    split_at = int(data.get("at", 1))
    try:
        ch, new_ch = chapter_service.split_chapter(chapter_id, split_at)
        return jsonify({"ok": True, "original_id": ch.id, "new_id": new_ch.id})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/<chapter_id>/merge", methods=["POST"])
def merge(chapter_id: str):
    data = request.get_json(silent=True) or {}
    other_id = data.get("with")
    if not other_id:
        return jsonify({"ok": False, "error": "Missing 'with'"}), 400
    try:
        ch = chapter_service.merge_chapters(chapter_id, other_id)
        return jsonify({"ok": True, "id": ch.id,
                        "url": url_for("chapters.detail", chapter_id=ch.id)})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/<chapter_id>/versions/<version_id>/restore", methods=["POST"])
def restore_version(chapter_id: str, version_id: str):
    try:
        chapter_service.restore_version(chapter_id, version_id)
        return jsonify({"ok": True,
                        "url": url_for("chapters.detail", chapter_id=chapter_id)})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/<chapter_id>/versions/save", methods=["POST"])
def save_version(chapter_id: str):
    """Save the current chapter content as a new version snapshot."""
    try:
        ch = chapter_service.get_chapter(chapter_id)
        # Force a version snapshot by calling update with current content
        chapter_service.update_chapter(
            chapter_id, content=ch.content, create_version=True,
            version_source="manual", version_notes="Manual save (Ctrl+S)",
        )
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/<chapter_id>/diff/export", methods=["POST"])
def export_diff(chapter_id: str):
    """Export a diff between two versions (or chapter vs version) as TXT or HTML."""
    data = request.get_json(silent=True) or request.form
    v1 = data.get("v1")
    v2 = data.get("v2")
    fmt = (data.get("format") or "txt").lower()
    try:
        ch = chapter_service.get_chapter(chapter_id)
        vs = chapter_service.get_chapter_with_versions(chapter_id)[1]
        vmap = {v.id: v for v in vs}
        if v1 not in vmap or v2 not in vmap:
            return jsonify({"ok": False, "error": "Invalid version ids"}), 400
        a = vmap[v1].content or ""
        b = vmap[v2].content or ""
        diff = diff_service.line_diff(a, b)
        if fmt == "html":
            html = diff_service.render_html_diff(a, b)
            from flask import Response
            return Response(html, mimetype="text/html",
                            headers={"Content-Disposition":
                                     f"attachment; filename=diff_{chapter_id}.html"})
        # TXT
        lines = []
        for d in diff:
            sign = {"eq": " ", "add": "+", "del": "-"}[d["op"]]
            lines.append(f"{sign} {d['text']}")
        from flask import Response
        return Response("\n".join(lines), mimetype="text/plain",
                        headers={"Content-Disposition":
                                 f"attachment; filename=diff_{chapter_id}.txt"})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/compare")
def compare_two():
    """Compare two different chapters."""
    ch1 = request.args.get("ch1")
    ch2 = request.args.get("ch2")
    all_chapters = chapter_service.list_chapters(sort="sort_order")[0]
    if not ch1 or not ch2:
        return render_template("chapters/compare.html", ch1=None, ch2=None,
                                diff=None, all_chapters=all_chapters,
                                active_nav="chapters")
    try:
        c1 = chapter_service.get_chapter(ch1)
        c2 = chapter_service.get_chapter(ch2)
        a = c1.content or ""
        b = c2.content or ""
        diff = diff_service.line_diff(a, b)
        return render_template("chapters/compare.html",
                                ch1=c1, ch2=c2, diff=diff,
                                stats=diff_service.stats(a, b),
                                all_chapters=all_chapters,
                                active_nav="chapters")
    except NotFoundError:
        abort(404)


@bp.route("/<chapter_id>/export/<fmt>")
def export(chapter_id: str, fmt: str):
    try:
        content, mimetype, filename = chapter_service_get_export(chapter_id, fmt)
        import io
        return send_file(io.BytesIO(content), mimetype=mimetype,
                         as_attachment=True, download_name=filename)
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


def chapter_service_get_export(chapter_id, fmt):
    from services import export_service
    return export_service.export_chapter(chapter_id, fmt)


@bp.route("/import-center")
def import_center():
    """Dedicated import center page."""
    return render_template("import_center.html", active_nav="import")


# ---- Editorial Checklist ----

@bp.route("/<chapter_id>/checklist")
def get_checklist(chapter_id: str):
    """Get editorial checklist for a chapter."""
    from services import checklist_service
    items = checklist_service.get_checklist(chapter_id)
    progress = checklist_service.get_progress(chapter_id)
    return jsonify({
        "ok": True,
        "items": [{"id": i.id, "text": i.item_text, "checked": i.is_checked,
                   "category": i.category, "sort_order": i.sort_order} for i in items],
        "progress": progress,
    })


@bp.route("/<chapter_id>/checklist/add", methods=["POST"])
def checklist_add(chapter_id: str):
    from services import checklist_service
    data = request.get_json(silent=True) or {}
    try:
        item = checklist_service.add_item(chapter_id, data.get("text", ""),
                                           data.get("category", "general"))
        return jsonify({"ok": True, "id": item.id})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/checklist/<item_id>/toggle", methods=["POST"])
def checklist_toggle(item_id: str):
    from services import checklist_service
    new_state = checklist_service.toggle_item(item_id)
    return jsonify({"ok": True, "checked": new_state})


@bp.route("/checklist/<item_id>/delete", methods=["POST"])
def checklist_delete(item_id: str):
    from services import checklist_service
    checklist_service.delete_item(item_id)
    return jsonify({"ok": True})
