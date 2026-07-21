"""Theme & CSS Editor routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request

from core.errors import AsmError
from services import theme_service as svc

log = logging.getLogger("asm.routes.theme")
bp = Blueprint("theme", __name__, url_prefix="/theme")


@bp.route("/")
def index():
    config = svc.get_config()
    presets = svc.get_preset_list()
    return render_template(
        "theme.html",
        active_nav="theme",
        config=config,
        presets=presets,
        preset_themes=svc.PRESET_THEMES,
    )


@bp.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "GET":
        return jsonify({"ok": True, "config": svc.get_config()})
    data = request.get_json(silent=True) or request.form
    try:
        saved = svc.save_config(dict(data))
        return jsonify({"ok": True, "config": saved})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/css")
def api_css():
    """Return the generated CSS for preview."""
    config = svc.get_config()
    if request.args.get("preview"):
        # Allow previewing a config from query without saving
        config = {
            "preset": request.args.get("preset", config.get("preset", "dark")),
            "overrides": {},
            "font_family": request.args.get("font_family", ""),
            "base_font_size": request.args.get("base_font_size", ""),
            "custom_css": request.args.get("custom_css", ""),
        }
    return jsonify({"ok": True, "css": svc.generate_css(config)})


@bp.route("/api/reset", methods=["POST"])
def api_reset():
    svc.reset_config()
    return jsonify({"ok": True})
