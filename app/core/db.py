"""
Core database configuration and session management.
SQLite with WAL mode, busy_timeout, and scoped sessions.
"""
import os
import threading
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import scoped_session, sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool
from flask_sqlalchemy import SQLAlchemy

# Flask-SQLAlchemy instance (initialized in create_app)
db = SQLAlchemy()

# Thread lock for write operations
_write_lock = threading.Lock()

_engine = None
_SessionFactory = None
db_session = None


def init_db(db_path: str):
    """Initialize database engine with WAL mode and proper settings."""
    global _engine, _SessionFactory, db_session
    
    # Ensure data directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Create engine with SQLite-specific settings
    _engine = create_engine(
        f'sqlite:///{db_path}',
        connect_args={
            'timeout': 30,
            'check_same_thread': False
        },
        poolclass=StaticPool,
        echo=False
    )
    
    # Set PRAGMAs on connection
    @event.listens_for(_engine, "connect")
    def set_sqlite_pragmas(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    
    # Create session factory
    _SessionFactory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    db_session = scoped_session(_SessionFactory)
    
    return _engine, db_session


def get_session():
    """Get a new session for background threads."""
    if _SessionFactory is None:
        raise RuntimeError("Database not initialized. Call init_db first.")
    return _SessionFactory()


def get_write_lock():
    """Get the global write lock for thread-safe writes."""
    return _write_lock


def enable_fts5(db_session):
    """Enable FTS5 full-text search tables and triggers."""
    try:
        # Chapters FTS
        db_session.execute(text('''
            CREATE VIRTUAL TABLE IF NOT EXISTS chapters_fts USING fts5(
                id, title, synopsis, content,
                content='chapters',
                content_rowid='rowid'
            )
        '''))
        
        # Characters FTS
        db_session.execute(text('''
            CREATE VIRTUAL TABLE IF NOT EXISTS characters_fts USING fts5(
                id, name, aliases, physical, psychology, background, philosophy, voice, notes,
                content='characters',
                content_rowid='rowid'
            )
        '''))
        
        # World entries FTS
        db_session.execute(text('''
            CREATE VIRTUAL TABLE IF NOT EXISTS world_fts USING fts5(
                id, name, description, content, notes,
                content='world_entries',
                content_rowid='rowid'
            )
        '''))
        
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        # FTS5 might not be available in some SQLite builds
        print(f"FTS5 setup warning: {e}")


def close_session():
    """Close the scoped session."""
    if db_session is not None:
        db_session.remove()
