"""Writing Music Player routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request

from services import music_service as svc

log = logging.getLogger("asm.routes.music")
bp = Blueprint("music", __name__, url_prefix="/music")


@bp.route("/")
def index():
    tracks = svc.list_tracks()
    return render_template(
        "music_player.html",
        active_nav="music",
        tracks=tracks,
    )


@bp.route("/api/tracks")
def api_tracks():
    return jsonify({"ok": True, "tracks": svc.list_tracks()})


@bp.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file provided"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"ok": False, "error": "Empty filename"}), 400
    try:
        content = f.read()
        track = svc.save_track(f.filename, content)
        return jsonify({"ok": True, "track": track})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        log.exception("Upload failed")
        return jsonify({"ok": False, "error": str(exc)}), 500


@bp.route("/api/<path:filename>/delete", methods=["POST"])
def api_delete(filename: str):
    try:
        deleted = svc.delete_track(filename)
        return jsonify({"ok": deleted, "error": "" if deleted else "File not found"})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
