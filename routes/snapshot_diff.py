"""Manuscript Snapshot Diff routes."""
from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, jsonify, render_template, request, send_file

from services import snapshot_diff_service as svc

log = logging.getLogger("asm.routes.snapshot_diff")
bp = Blueprint("snapshot_diff", __name__, url_prefix="/snapshot-diff")


def _parse_dt(s: str) -> datetime:
    if not s:
        return datetime.now()
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.now()


@bp.route("/")
def index():
    dates = svc.get_available_dates()
    return render_template(
        "snapshot_diff.html",
        active_nav="snapshot_diff",
        dates=dates,
    )


@bp.route("/api/diff")
def api_diff():
    from_str = request.args.get("from", "")
    to_str = request.args.get("to", "")
    if not from_str or not to_str:
        return jsonify({"ok": False, "error": "Both from and to dates are required"}), 400
    from_dt = _parse_dt(from_str)
    to_dt = _parse_dt(to_str)
    diff = svc.compute_diff(from_dt, to_dt)
    return jsonify({"ok": True, "diff": diff})


@bp.route("/api/dates")
def api_dates():
    return jsonify({"ok": True, "dates": svc.get_available_dates()})


@bp.route("/download")
def download():
    from_str = request.args.get("from", "")
    to_str = request.args.get("to", "")
    from_dt = _parse_dt(from_str)
    to_dt = _parse_dt(to_str)
    diff = svc.compute_diff(from_dt, to_dt)
    html = svc.render_diff_html(diff)
    import io
    return send_file(
        io.BytesIO(html.encode("utf-8")),
        mimetype="text/html",
        as_attachment=True,
        download_name=f"manuscript_diff_{from_str[:10]}_to_{to_str[:10]}.html",
    )
