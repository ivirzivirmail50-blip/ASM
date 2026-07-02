"""
Absolute Story Manager v4.0 - Flask Application Factory
Local-first creative writing tool with optional AI assistance.
"""
import os
import logging
import json
from flask import Flask, render_template, jsonify, request, g
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import text

from app.core.db import db, init_db, enable_fts5, get_write_lock, close_session, db_session
from app.core.errors import AppError, NotFoundError, ValidationError


def create_app(config=None):
    """Application factory for Absolute Story Manager."""
    app = Flask(__name__, instance_relative_config=True)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024  # 30 MB max request
    
    # Data directory
    app.config['DATA_DIR'] = os.path.join(app.instance_path, 'data')
    app.config['DB_PATH'] = os.path.join(app.config['DATA_DIR'], 'asm.db')
    
    # Set database URI after DB_PATH is defined
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{app.config["DB_PATH"]}'
    
    try:
        os.makedirs(app.instance_path)
        os.makedirs(app.config['DATA_DIR'])
        os.makedirs(os.path.join(app.config['DATA_DIR'], 'logs'))
        os.makedirs(os.path.join(app.config['DATA_DIR'], 'raw'))
        os.makedirs(os.path.join(app.config['DATA_DIR'], 'media'))
        os.makedirs(os.path.join(app.config['DATA_DIR'], 'backups'))
        os.makedirs(os.path.join(app.config['DATA_DIR'], 'exports'))
    except OSError:
        pass
    
    # Initialize database
    db.init_app(app)
    init_db(app.config['DB_PATH'])
    
    # CSRF Protection
    csrf = CSRFProtect()
    csrf.init_app(app)
    
    # Register blueprints
    from app.routes.main import main_bp
    app.register_blueprint(main_bp)
    
    # API blueprint (create if not exists)
    try:
        from app.routes.api import api_bp
        app.register_blueprint(api_bp, url_prefix='/api')
    except ImportError:
        pass  # API routes not yet implemented
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f'Internal error: {error}')
        return render_template('500.html'), 500
    
    @app.errorhandler(AppError)
    def handle_app_error(error):
        return jsonify({'error': error.message, 'code': error.code}), 400
    
    # Database session per request
    @app.before_request
    def before_request():
        g.db_session = db_session
    
    @app.teardown_request
    def teardown_request(exception=None):
        close_session()
    
    # Initialize database tables and seed data
    with app.app_context():
        db.create_all()
        
        # Create default project if not exists
        from app.models import Project, Settings
        default_project = Project.query.get('default')
        if not default_project:
            default_project = Project(id='default', name='My Story')
            db.session.add(default_project)
            
            # Create default settings
            default_settings = {
                'active_project_id': 'default',
                'story_title': 'My Story',
                'story_author': 'Author',
                'story_genre': '',
                'story_description': '',
                'daily_word_goal': 500,
                'total_word_goal': 80000,
                'manuscript_font': 'Courier',
                'manuscript_font_size': 12,
                'manuscript_line_spacing': 2.0,
                'manuscript_margins': 1.0,
                'autosave_interval_seconds': 3,
                'version_snapshot_interval_minutes': 15,
                'auto_backup_enabled': True,
                'auto_backup_interval_hours': 6,
                'theme': 'dark',
                'sidebar_collapsed': False,
                'editor_font': 'serif',
                'editor_font_size': 16,
                'chapter_viewer_font': 'serif',
                'chapter_viewer_font_size': 16,
                'chapter_sort_default': 'sort_order',
                'character_sort_default': 'name',
                'default_chapter_status': 'draft',
                'world_types': ['location', 'lore', 'faction', 'glossary', 'magic_system', 'species', 'culture', 'technology'],
                'ai.enabled': False,
                'ai.provider': 'ollama',
                'ai.api_base': 'http://localhost:11434',
                'ai.api_key': '',
                'ai.model': '',
                'ai.timeout_seconds': 60
            }
            
            for key, value in default_settings.items():
                setting = Settings(key=key, value=json.dumps(value))
                db.session.add(setting)
            
            db.session.commit()
            
            # Enable FTS5
            enable_fts5(db.session)
    
    return app
