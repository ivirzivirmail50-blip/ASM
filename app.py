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

    @app.before_request
    def _ensure_db():  # noqa: ANN202
        if not _db_initialized["done"]:
            try:
                init_db(seed_defaults=True)
            except Exception:
                log.exception("DB init failed")
            _db_initialized["done"] = True
        # Per-request request_id for log correlation
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

    # Exempt all blueprint routes from CSRF.
    from core.csrf import csrf
    for bp in [dashboard_bp, chapters_bp, characters_bp, plans_bp,
               world_bp, search_bp, export_bp, settings_bp, ai_bp, undo_bp,
               quickswitch_bp, lint_bp, pacing_bp, projects_bp, beta_bp,
               ai_history_bp]:
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

    # Static file route for data/media (so map images etc. can be served)
    @app.route("/media/<path:filename>")
    def _serve_media(filename: str):  # noqa: ANN202
        from flask import send_from_directory
        from security.upload import safe_join
        from config import Config
        try:
            path = safe_join(Config.MEDIA_DIR, *filename.split("/"))
            return send_from_directory(str(Config.MEDIA_DIR), filename)
        except Exception:
            from flask import abort
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
        return {
            "settings": settings,
            "theme": settings.get("theme", "dark"),
            "story_title": settings.get("story_title", "My Story"),
            "active_project_name": settings.get("story_title", "My Story"),
        }

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

    log.info("Absolute Story Manager app created.")
    return app


# Allow `python app.py` for local dev.
if __name__ == "__main__":
    import os
    import threading
    import webbrowser

    app = create_app()

    # Only open browser in the reloader child process (not the parent)
    # This prevents the browser from opening twice when debug=True
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        def _open_browser() -> None:
            import time
            time.sleep(1.5)
            webbrowser.open("http://127.0.0.1:5555/")
        threading.Thread(target=_open_browser, daemon=True).start()

    print("=" * 50)
    print("  Absolute Story Manager v4.0")
    print("  Opening browser at http://127.0.0.1:5555/")
    print("  Press Ctrl+C to stop.")
    print("=" * 50)

    # use_reloader=False prevents double-start, but we keep it for dev convenience
    # The WERKZEUG_RUN_MAIN check above handles the double browser issue
    app.run(host="127.0.0.1", port=5555, debug=True, use_reloader=False)
