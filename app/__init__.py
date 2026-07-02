import os
from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

db = SQLAlchemy()

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    
    app.config['SECRET_KEY'] = 'dev-key-change-in-production'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///story_manager.db'
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'connect_args': {'timeout': 30},
        'pool_pre_ping': True
    }
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    db.init_app(app)
    
    from app.routes.main import main_bp
    from app.routes.api import api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    
    @app.route('/static/<path:filename>')
    def serve_static(filename):
        return send_from_directory('app/static', filename)
    
    with app.app_context():
        from app.models.story import Story, Chapter, Character, Scene, TimelineEvent, WorldElement, KanbanCard
        db.create_all()
        
        # Enable FTS5 for full-text search
        db.session.execute(text('''
            CREATE VIRTUAL TABLE IF NOT EXISTS story_fts USING fts5(
                title, content, summary,
                content='story',
                content_rowid='id'
            )
        '''))
        db.session.commit()
    
    return app