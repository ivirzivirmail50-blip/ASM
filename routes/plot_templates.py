"""Plot Structure Templates routes — view templates, apply one to your outline."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request

from core.errors import AsmError
from services import plot_template_service as svc

log = logging.getLogger("asm.routes.plot_templates")
bp = Blueprint("plot_templates", __name__, url_prefix="/plot-templates")


@bp.route("/")
def index():
    templates = svc.list_templates()
    return render_template(
        "plot_templates.html",
        active_nav="plot_templates",
        templates=templates,
    )


@bp.route("/<key>")
def detail(key: str):
    tmpl = svc.get_template(key)
    if not tmpl:
        from flask import abort
        abort(404)
    return render_template(
        "plot_templates.html",
        active_nav="plot_templates",
        templates=svc.list_templates(),
        detail_key=key,
        detail_tmpl=tmpl,
    )


@bp.route("/api/apply", methods=["POST"])
def api_apply():
    data = request.get_json(silent=True) or request.form
    key = data.get("key", "").strip()
    try:
        result = svc.apply_template(key)
        return jsonify({"ok": True, **result})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code
