"""Project (multi-book) management routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request, redirect, url_for

from core.db import read_session, write_transaction
from core.errors import AsmError
from models.project import Project
from models.settings import Setting

log = logging.getLogger("asm.routes.projects")
bp = Blueprint("projects", __name__)


@bp.route("/projects")
def list_projects():
    """List all projects with stats."""
    with read_session() as s:
        projects = list(s.query(Project).order_by(Project.created_at.asc()).all())
        active_id = Setting.get(s, "active_project_id", "default")
        # Count entities per project
        from models.chapter import Chapter
        from models.character import Character
        from models.world import WorldEntry
        project_stats = []
        for p in projects:
            ch_count = s.query(Chapter).filter_by(project_id=p.id).count()
            char_count = s.query(Character).filter_by(project_id=p.id).count()
            world_count = s.query(WorldEntry).filter_by(project_id=p.id).count()
            total_words = s.query(Chapter.word_count).filter_by(project_id=p.id).all()
            total_words = sum(w[0] or 0 for w in total_words)
            project_stats.append({
                "id": p.id, "name": p.name, "subtitle": p.subtitle,
                "is_active": p.id == active_id,
                "chapters": ch_count, "characters": char_count,
                "world_entries": world_count, "total_words": total_words,
            })
    return render_template("projects.html", projects=project_stats,
                           active_id=active_id, active_nav="projects")


@bp.route("/projects/new", methods=["POST"])
def create_project():
    """Create a new project/book."""
    data = request.get_json(silent=True) or request.form
    name = (data.get("name") or "").strip()
    subtitle = (data.get("subtitle") or "").strip() or None
    if not name:
        return jsonify({"ok": False, "error": "Name required"}), 400
    import uuid
    pid = uuid.uuid4().hex
    with write_transaction() as s:
        s.add(Project(id=pid, name=name, subtitle=subtitle))
        Setting.set(s, "active_project_id", pid)
    return jsonify({"ok": True, "id": pid, "url": url_for("projects.list_projects")})


@bp.route("/projects/<project_id>/switch", methods=["POST"])
def switch_project(project_id: str):
    """Switch active project."""
    with write_transaction() as s:
        if not s.get(Project, project_id):
            return jsonify({"ok": False, "error": "Project not found"}), 404
        Setting.set(s, "active_project_id", project_id)
    return jsonify({"ok": True, "url": url_for("dashboard.index")})


@bp.route("/projects/<project_id>/edit", methods=["POST"])
def edit_project(project_id: str):
    """Edit project name/subtitle."""
    data = request.get_json(silent=True) or request.form
    name = (data.get("name") or "").strip()
    subtitle = (data.get("subtitle") or "").strip() or None
    if not name:
        return jsonify({"ok": False, "error": "Name required"}), 400
    with write_transaction() as s:
        p = s.get(Project, project_id)
        if not p:
            return jsonify({"ok": False, "error": "Project not found"}), 404
        p.name = name
        p.subtitle = subtitle
    return jsonify({"ok": True})


@bp.route("/projects/<project_id>/delete", methods=["POST"])
def delete_project(project_id: str):
    """Delete a project and all its data."""
    if project_id == "default":
        return jsonify({"ok": False, "error": "Cannot delete the default project"}), 400
    from models.chapter import Chapter, ChapterVersion
    from models.character import (Character, CharacterGroup, CharacterGroupMember,
                                   CharacterRelationship, CharacterArc)
    from models.plan import Plan, PlanSubtask
    from models.world import WorldEntry, WorldEntryVersion, WorldEntryRelation
    with write_transaction() as s:
        # Delete all entities belonging to this project
        for model in [Chapter, Character, CharacterGroup, Plan, WorldEntry]:
            s.query(model).filter_by(project_id=project_id).delete()
        # Delete orphaned sub-versions/sub-items
        s.query(ChapterVersion).filter(
            ChapterVersion.chapter_id.in_(
                s.query(Chapter.id).filter(Chapter.project_id == project_id).subquery()
            )
        ).delete(synchronize_session=False)
        # Switch back to default
        Setting.set(s, "active_project_id", "default")
        p = s.get(Project, project_id)
        if p:
            s.delete(p)
    return jsonify({"ok": True, "url": url_for("dashboard.index")})
