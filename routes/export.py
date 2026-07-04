"""Export routes."""
from __future__ import annotations

import io
import logging

from flask import (Blueprint, jsonify, render_template, request,
                   send_file)

from core.errors import AsmError
from services import export_service
from services.compile_presets import get_all_presets, get_preset, apply_preset_to_settings

log = logging.getLogger("asm.routes.export")
bp = Blueprint("export", __name__, url_prefix="/export")


@bp.route("/")
def index():
    presets = get_all_presets()
    return render_template("export.html", presets=presets, active_nav="export")


@bp.route("/presets")
def list_presets():
    """List all compile presets (JSON API for Quick Switch / UI)."""
    return jsonify({"presets": get_all_presets()})


@bp.route("/presets/<key>/apply", methods=["POST"])
def apply_preset(key: str):
    """Apply a compile preset to manuscript settings."""
    settings = apply_preset_to_settings(key)
    if not settings:
        return jsonify({"ok": False, "error": "Unknown preset"}), 400
    from core.db import write_transaction
    from models.settings import Setting
    with write_transaction() as s:
        for k, v in settings.items():
            Setting.set(s, k, v)
    return jsonify({"ok": True, "preset": key, "settings": settings})


@bp.route("/manuscript/<fmt>")
def manuscript(fmt: str):
    try:
        content, mimetype, filename = export_service.export_manuscript(fmt)
        return send_file(io.BytesIO(content), mimetype=mimetype,
                         as_attachment=True, download_name=filename)
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/world-bible/<fmt>")
def world_bible(fmt: str):
    try:
        content, mimetype, filename = export_service.export_world_bible(fmt)
        return send_file(io.BytesIO(content), mimetype=mimetype,
                         as_attachment=True, download_name=filename)
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/full-project/<fmt>")
def full_project(fmt: str):
    include_secrets = request.args.get("include_secrets", "0") == "1"
    try:
        content, mimetype, filename = export_service.export_full_project(
            fmt, include_secrets=include_secrets,
        )
        return send_file(io.BytesIO(content), mimetype=mimetype,
                         as_attachment=True, download_name=filename)
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


# ---- Async export with progress ----

@bp.route("/async/<entity_type>/<fmt>")
def async_start(entity_type: str, fmt: str):
    """Start a background export task. Returns task_id."""
    entity_id = request.args.get("entity_id")
    try:
        task_id = export_service.async_export(entity_type, fmt, entity_id=entity_id)
        return jsonify({"ok": True, "task_id": task_id})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/status/<task_id>")
def status(task_id: str):
    """Poll export task status."""
    result = export_service.get_export_status(task_id)
    if result is None:
        return jsonify({"ok": False, "error": "Task not found or expired"}), 404
    return jsonify({"ok": True, **result})


@bp.route("/download/<task_id>")
def download(task_id: str):
    """Download completed export file."""
    result = export_service.get_export_file(task_id)
    if result is None:
        return jsonify({"ok": False, "error": "File not ready or task expired"}), 404
    content, mime, filename = result
    return send_file(io.BytesIO(content), mimetype=mime,
                     as_attachment=True, download_name=filename)
