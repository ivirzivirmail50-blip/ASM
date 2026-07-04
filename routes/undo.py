"""Undo/redo routes — DB-backed persistent undo system."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify

from core.errors import AsmError
from models import undo as undo_model

log = logging.getLogger("asm.routes.undo")
bp = Blueprint("undo", __name__)


@bp.route("/undo", methods=["POST"])
def undo():
    """Undo the most recent operation."""
    try:
        result = undo_model.undo_last()
        if result is None:
            return jsonify({"ok": False, "error": "Nothing to undo."}), 400
        return jsonify({"ok": True, "label": result.get("label", ""),
                        "action": result.get("action", "restored")})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code
    except Exception as exc:
        log.exception("Undo failed")
        return jsonify({"ok": False, "error": str(exc)}), 500


@bp.route("/undo/list")
def undo_list():
    """Return recent undo entries (for the undo toolbar tooltip)."""
    ops = undo_model.list_recent(limit=20)
    return jsonify({"ops": [
        {
            "id": op.id,
            "operation": op.operation,
            "label": op.label,
            "entity_type": op.entity_type,
            "created_at": op.created_at.isoformat() if op.created_at else None,
        }
        for op in ops
    ]})
