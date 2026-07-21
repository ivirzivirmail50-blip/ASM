"""Flask app factory for Absolute Story Manager."""
from __future__ import annotations

import logging
import traceback
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request

from config import Config, ensure_dirs
from core.csrf import init_csrf
from core.db import init_db
from core.errors import AsmError
from core.logging import configure_logging, set_request_id


def _verify_vendor_manifest(log) -> None:
    """Verify all vendor assets listed in MANIFEST.txt exist on disk.

    Warns (does NOT crash) if any asset is missing, pointing the user to
    `python scripts/fetch_vendor.py`.
    """
    manifest = Path(__file__).parent / "static" / "vendor" / "MANIFEST.txt"
    if not manifest.exists():
        log.warning(
            "Vendor manifest not found at %s. "
            "Run: python scripts/fetch_vendor.py", manifest
        )
        return
    base = manifest.parent.parent  # static/
    missing: list[str] = []
    checked = 0
    try:
        for line in manifest.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Format: name | version | source_url | local_path | sha256
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 4:
                continue
            local_path = parts[3]
            full = base / local_path.replace("static/", "", 1)
            checked += 1
            if not full.exists():
                missing.append(local_path)
    except Exception as exc:
        log.warning("Failed to read vendor manifest: %s", exc)
        return
    if missing:
        log.warning(
            "Vendor manifest check: %d/%d assets OK, %d missing. "
            "Run: python scripts/fetch_vendor.py. Missing: %s",
            checked - len(missing), checked, len(missing),
            ", ".join(missing[:5]),
        )
    else:
        log.info("Vendor manifest OK: %d assets verified.", checked)


def create_app(testing: bool = False) -> Flask:
    """App factory: register config, blueprints, error handlers, CSRF."""
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(Config)
    if testing:
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False

    # Logging
    configure_logging()
    log = logging.getLogger("asm.app")

    # Ensure data dirs
    ensure_dirs()

    # Vendor manifest check (warn, don't crash)
    _verify_vendor_manifest(log)

    # Initialize DB on first request (lazy init avoids import-time DB creation
    # during testing).
    _db_initialized = {"done": False}
    _backup_checked = {"done": False}

    @app.before_request
    def _ensure_db():  # noqa: ANN202
        if not _db_initialized["done"]:
            try:
                init_db(seed_defaults=True)
            except Exception:
                log.exception("DB init failed")
            _db_initialized["done"] = True
        if not _backup_checked["done"]:
            _backup_checked["done"] = True
            try:
                from services.backup_service import maybe_auto_backup
                maybe_auto_backup()
            except Exception:
                pass
        set_request_id()

    # CSRF
    init_csrf(app)

    # Register blueprints
    from routes.dashboard import bp as dashboard_bp
    from routes.chapters import bp as chapters_bp
    from routes.characters import bp as characters_bp
    from routes.plans import bp as plans_bp
    from routes.world import bp as world_bp
    from routes.search import bp as search_bp
    from routes.export import bp as export_bp
    from routes.settings import bp as settings_bp
    from routes.ai import bp as ai_bp
    from routes.undo import bp as undo_bp
    from routes.quickswitch import bp as quickswitch_bp
    from routes.lint import bp as lint_bp
    from routes.pacing import bp as pacing_bp
    from routes.projects import bp as projects_bp
    from routes.beta import bp as beta_bp
    from routes.ai_history import bp as ai_history_bp
    from routes.snippets import bp as snippets_bp
    from routes.inspiration import bp as inspiration_bp
    from routes.plot_templates import bp as plot_templates_bp
    from routes.notes import bp as notes_bp
    from routes.glossary import bp as glossary_bp
    from routes.find_replace import bp as find_replace_bp
    from routes.submissions import bp as submissions_bp
    from routes.analytics import bp as analytics_bp
    from routes.reading import bp as reading_bp
    from routes.voice import bp as voice_bp
    from routes.timeline_check import bp as timeline_check_bp
    from routes.references import bp as references_bp
    from routes.scenes import bp as scenes_bp
    from routes.journal import bp as journal_bp
    from routes.compile import bp as compile_bp
    from routes.theme import bp as theme_bp
    from routes.achievements import bp as achievements_bp
    from routes.goals_calendar import bp as goals_calendar_bp
    from routes.story_bible import bp as story_bible_bp
    from routes.spellcheck import bp as spellcheck_bp
    from routes.sessions import bp as sessions_bp
    from routes.snapshot_diff import bp as snapshot_diff_bp
    from routes.quick_capture import bp as quick_capture_bp
    from routes.prompt_calendar import bp as prompt_calendar_bp
    from routes.chapter_deps import bp as chapter_deps_bp
    from routes.character_arcs import bp as character_arcs_bp
    from routes.forecast import bp as forecast_bp
    from routes.habits import bp as habits_bp
    from routes.milestones import bp as milestones_bp
    from routes.rel_timeline import bp as rel_timeline_bp
    from routes.scrivener import bp as scrivener_bp
    from routes.word_freq import bp as word_freq_bp
    from routes.char_mood import bp as char_mood_bp
    from routes.music import bp as music_bp
    from routes.i18n import bp as i18n_bp
    from routes.focus_mode import bp as focus_mode_bp
    from routes.ai_copilot import bp as ai_copilot_bp
    from routes.character_chat import bp as character_chat_bp
    from routes.character_generator import bp as character_generator_bp
    from routes.family_tree import bp as family_tree_bp
    from routes.serial_platform import bp as serial_platform_bp
    from routes.interactive_epub import bp as interactive_epub_bp

    # CSRF Exemption — Design Decision
    # ================================
    # This is a local-first, single-user application (localhost only, no auth).
    # CSRF protection is exempted on all blueprints because:
    #   1. The app runs on 127.0.0.1 — no external network access
    #   2. No user authentication = no session hijacking risk
    #   3. All forms include hidden csrf_token fields as defense-in-depth
    #   4. JSON API endpoints (asmFetch) send X-CSRFToken header
    # If deploying to a network-accessible server, REMOVE these exemptions
    # and ensure all forms include the csrf_token hidden field.
    from core.csrf import csrf
    for bp in [dashboard_bp, chapters_bp, characters_bp, plans_bp,
               world_bp, search_bp, export_bp, settings_bp, ai_bp, undo_bp,
               quickswitch_bp, lint_bp, pacing_bp, projects_bp, beta_bp,
               ai_history_bp, snippets_bp, inspiration_bp, plot_templates_bp,
               notes_bp, glossary_bp, find_replace_bp, submissions_bp,
               analytics_bp, reading_bp, voice_bp, timeline_check_bp,
               references_bp, scenes_bp, journal_bp, compile_bp, theme_bp,
               achievements_bp, goals_calendar_bp, story_bible_bp, spellcheck_bp,
               sessions_bp, snapshot_diff_bp, quick_capture_bp, prompt_calendar_bp,
               chapter_deps_bp, character_arcs_bp, forecast_bp, habits_bp,
               milestones_bp, rel_timeline_bp, scrivener_bp, word_freq_bp,
               char_mood_bp, music_bp, i18n_bp, focus_mode_bp, ai_copilot_bp,
               character_chat_bp, character_generator_bp, family_tree_bp,
               serial_platform_bp, interactive_epub_bp]:
        csrf.exempt(bp)

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(chapters_bp)
    app.register_blueprint(characters_bp)
    app.register_blueprint(plans_bp)
    app.register_blueprint(world_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(undo_bp)
    app.register_blueprint(quickswitch_bp)
    app.register_blueprint(lint_bp)
    app.register_blueprint(pacing_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(beta_bp)
    app.register_blueprint(ai_history_bp)
    app.register_blueprint(snippets_bp)
    app.register_blueprint(inspiration_bp)
    app.register_blueprint(plot_templates_bp)
    app.register_blueprint(notes_bp)
    app.register_blueprint(glossary_bp)
    app.register_blueprint(find_replace_bp)
    app.register_blueprint(submissions_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(reading_bp)
    app.register_blueprint(voice_bp)
    app.register_blueprint(timeline_check_bp)
    app.register_blueprint(references_bp)
    app.register_blueprint(scenes_bp)
    app.register_blueprint(journal_bp)
    app.register_blueprint(compile_bp)
    app.register_blueprint(theme_bp)
    app.register_blueprint(achievements_bp)
    app.register_blueprint(goals_calendar_bp)
    app.register_blueprint(story_bible_bp)
    app.register_blueprint(spellcheck_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(snapshot_diff_bp)
    app.register_blueprint(quick_capture_bp)
    app.register_blueprint(prompt_calendar_bp)
    app.register_blueprint(chapter_deps_bp)
    app.register_blueprint(character_arcs_bp)
    app.register_blueprint(forecast_bp)
    app.register_blueprint(habits_bp)
    app.register_blueprint(milestones_bp)
    app.register_blueprint(rel_timeline_bp)
    app.register_blueprint(scrivener_bp)
    app.register_blueprint(word_freq_bp)
    app.register_blueprint(char_mood_bp)
    app.register_blueprint(music_bp)
    app.register_blueprint(i18n_bp)
    app.register_blueprint(focus_mode_bp)
    app.register_blueprint(ai_copilot_bp)
    app.register_blueprint(character_chat_bp)
    app.register_blueprint(character_generator_bp)
    app.register_blueprint(family_tree_bp)
    app.register_blueprint(serial_platform_bp)
    app.register_blueprint(interactive_epub_bp)

    # Static file route for data/media (so map images etc. can be served)
    @app.route("/media/<path:filename>")
    def _serve_media(filename: str):  # noqa: ANN202
        from flask import send_file, abort
        from security.upload import safe_join
        from config import Config
        import mimetypes
        import logging as _lg
        _log = _lg.getLogger("asm.media")
        try:
            safe_path = safe_join(Config.MEDIA_DIR, *filename.split("/"))
            if not safe_path.exists():
                _log.warning("Media not found: %s -> %s", filename, safe_path)
                abort(404)
            mime = mimetypes.guess_type(str(safe_path))[0] or 'application/octet-stream'
            _log.info("Serving media: %s (mime=%s, size=%d)", safe_path, mime, safe_path.stat().st_size)
            resp = send_file(str(safe_path), mimetype=mime, conditional=False)
            resp.headers['Cache-Control'] = 'no-cache'
            return resp
        except Exception as exc:
            _log.error("Media serve error: %s -> %s", filename, exc)
            abort(404)

    # Inject settings + theme into every template
    @app.context_processor
    def _inject_globals() -> dict[str, Any]:
        from core.db import read_session
        from models.settings import Setting
        try:
            with read_session() as s:
                settings = Setting.all_settings(s)
        except Exception:
            settings = {}
        # Generate custom theme CSS if configured
        custom_theme_css = ""
        try:
            from services.theme_service import generate_css, get_config
            custom_theme_css = generate_css(get_config())
        except Exception:
            pass
        return {
            "settings": settings,
            "theme": settings.get("theme", "dark"),
            "story_title": settings.get("story_title", "My Story"),
            "active_project_name": settings.get("story_title", "My Story"),
            "custom_theme_css": custom_theme_css,
        }

    # Inject i18n (translations + language) into every template
    @app.context_processor
    def _inject_i18n() -> dict[str, Any]:
        try:
            from services.i18n_service import get_current_language, get_translation_dict, SUPPORTED_LANGUAGES
            lang = get_current_language()
            translations = get_translation_dict(lang)
            return {
                "ui_lang": lang,
                "t": lambda key: translations.get(key, key),
                "supported_languages": SUPPORTED_LANGUAGES,
            }
        except Exception:
            return {"ui_lang": "en", "t": lambda key: key, "supported_languages": {}}

    # Inject CSRF token into templates
    @app.context_processor
    def _inject_csrf() -> dict[str, Any]:
        from flask_wtf.csrf import generate_csrf
        return {"csrf_token": generate_csrf}

    # Error handlers
    @app.errorhandler(404)
    def _not_found(err):  # noqa: ANN202
        if request.path.startswith("/api/") or request.is_json:
            return jsonify({"ok": False, "error": "Not found"}), 404
        return render_template("404.html", path=request.path), 404

    @app.errorhandler(500)
    def _server_error(err):  # noqa: ANN202
        from core.logging import get_request_id
        rid = get_request_id() or "unknown"
        log.error("500 error: %s\n%s", err, traceback.format_exc())
        if request.path.startswith("/api/") or request.is_json:
            return jsonify({"ok": False, "error": "Server error",
                            "request_id": rid}), 500
        return render_template("500.html", request_id=rid), 500

    @app.errorhandler(AsmError)
    def _asm_error(err: AsmError):  # noqa: ANN202
        log.warning("ASM error: %s (%s)", err.user_message, err.code)
        if request.path.startswith("/api/") or request.is_json:
            return jsonify({"ok": False, "error": err.user_message,
                            "code": err.code}), err.status_code
        return render_template("500.html",
                                request_id="",
                                message=err.user_message), err.status_code

    @app.template_filter("from_json")
    def _from_json(value):  # noqa: ANN202
        import json
        if not value:
            return []
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []

    @app.template_filter("truncate_text")
    def _truncate_text(value, length=200):  # noqa: ANN202
        if not value:
            return ""
        if len(value) <= length:
            return value
        return value[:length].rsplit(" ", 1)[0] + "…"

    # Jinja global: build a URL for a cross-reference link from a note
    @app.template_global("link_url")
    def _link_url(link):  # noqa: ANN202
        if not link or not isinstance(link, dict):
            return "#"
        et = link.get("entity_type")
        eid = link.get("entity_id", "")
        try:
            if et == "chapter":
                return url_for("chapters.detail", chapter_id=eid)
            if et == "character":
                return url_for("characters.detail", character_id=eid)
            if et == "world_entry":
                return url_for("world.detail", entry_id=eid)
            if et == "plan":
                return url_for("plans.detail", plan_id=eid)
        except Exception:
            pass
        return "#"

    log.info("Absolute Story Manager app created.")
    return app


# Allow `python app.py` for local dev.
if __name__ == "__main__":
    import os
    import threading
    import webbrowser

    app = create_app()

    # Caddy reverse proxy expects the app on port 3000.
    # When running locally without Caddy, use 5555.
    PORT = int(os.environ.get("PORT", 3000))
    HOST = os.environ.get("HOST", "0.0.0.0")

    # Only open browser in the reloader child process (not the parent)
    # This prevents the browser from opening twice when debug=True
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        def _open_browser() -> None:
            import time
            time.sleep(1.5)
            webbrowser.open(f"http://127.0.0.1:{PORT}/")
        threading.Thread(target=_open_browser, daemon=True).start()

    print("=" * 50)
    print("  Absolute Story Manager v5.0")
    print(f"  Listening on http://{HOST}:{PORT}/")
    print("  Press Ctrl+C to stop.")
    print("=" * 50)

    # use_reloader=False prevents double-start
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)
