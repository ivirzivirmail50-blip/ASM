"""Scrivener export routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request, send_file

from services import scrivener_export_service as svc

log = logging.getLogger("asm.routes.scrivener")
bp = Blueprint("scrivener", __name__, url_prefix="/scrivener")


@bp.route("/")
def index():
    return render_template("scrivener_export.html", active_nav="scrivener")


@bp.route("/download")
def download():
    include_synopsis = request.args.get("synopsis", "1") != "0"
    include_tags = request.args.get("tags", "1") != "0"
    status_filter = request.args.get("status", "all")
    try:
        content, filename = svc.generate_scriv_package(
            include_synopsis=include_synopsis,
            include_tags=include_tags,
            status_filter=status_filter,
        )
        import io
        return send_file(
            io.BytesIO(content),
            mimetype="application/zip",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        log.exception("Scrivener export failed")
        return jsonify({"ok": False, "error": str(exc)}), 500
