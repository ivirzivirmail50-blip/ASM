"""Family Tree Builder — visual family tree for characters."""
from __future__ import annotations
from flask import Blueprint, render_template, jsonify, request
from services import character_service
from models.character import CharacterRelationship

bp = Blueprint("family_tree", __name__, url_prefix="/family-tree")


@bp.route("/")
def index():
    characters = character_service.list_characters()
    return render_template("family_tree/index.html", active_nav="family_tree", characters=characters)


@bp.route("/api/tree")
def api_tree():
    from core.db import read_session
    from models.character import Character, CharacterRelationship
    from services._common import current_project_id
    with read_session() as s:
        chars = list(s.scalars(__import__("sqlalchemy").select(Character).where(Character.project_id == current_project_id(s))))
        rels = list(s.scalars(__import__("sqlalchemy").select(CharacterRelationship)))
    char_map = {c.id: c.name for c in chars}
    nodes = [{"id": c.id, "label": c.name, "color": c.avatar_color or "#6366f1"} for c in chars]
    edges = []
    for r in rels:
        if r.relationship_type in ("parent_of", "married_to", "serves"):
            edges.append({
                "from": r.from_character_id, "to": r.to_character_id,
                "label": r.relationship_type.replace("_", " "),
                "color": "#ec4899" if r.relationship_type == "married_to" else "#22c55e",
            })
    return jsonify({"ok": True, "nodes": nodes, "edges": edges})


@bp.route("/api/add-relation", methods=["POST"])
def api_add_relation():
    data = request.get_json(silent=True) or request.form
    try:
        rel = character_service.create_relationship(
            from_id=data.get("from_id"),
            to_id=data.get("to_id"),
            rel_type=data.get("type", "parent_of"),
        )
        return jsonify({"ok": True, "id": rel.id})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
