"""i18n routes — translation API."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from services import i18n_service as svc

bp = Blueprint("i18n", __name__, url_prefix="/i18n")


@bp.route("/api/translations")
def api_translations():
    lang = request.args.get("lang", "en")
    return jsonify({
        "ok": True,
        "lang": lang,
        "translations": svc.get_translation_dict(lang),
    })


@bp.route("/api/set-language", methods=["POST"])
def api_set_language():
    from flask import request
    data = request.get_json(silent=True) or request.form
    lang = data.get("lang", "en")
    svc.set_language(lang)
    return jsonify({"ok": True, "lang": lang})
