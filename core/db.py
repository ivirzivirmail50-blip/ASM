"""Database engine, scoped sessions, WAL pragmas, write lock.

Concurrency model:
- SQLite WAL mode for concurrent reader/writer throughput.
- Module-level threading.Lock guards write transactions.
- busy_timeout=5000 ensures writers wait briefly instead of erroring.
- Background threads MUST call new_bg_session() to get their own session.
"""
from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import scoped_session, sessionmaker, Session

from config import Config, ensure_dirs

log = logging.getLogger("asm.db")

ensure_dirs()

engine = create_engine(
    Config.SQLALCHEMY_DATABASE_URI,
    future=True,
    **Config.SQLALCHEMY_ENGINE_OPTIONS,
)

# Apply SQLite pragmas on every new connection.
@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _record):  # noqa: ANN001
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
SessionLocal = scoped_session(session_factory)

# Single writer lock — every write transaction acquires this.
_write_lock = threading.RLock()


def current_session() -> Session:
    """Return the request-scoped session."""
    return SessionLocal()


@contextmanager
def write_transaction() -> Iterator[Session]:
    """Context manager that yields a session inside a write transaction.

    Acquires the global write lock, begins a transaction, commits on success,
    rolls back on error. Always used for state-changing operations.
    """
    session = SessionLocal()
    try:
        with _write_lock:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
    finally:
        SessionLocal.remove()


@contextmanager
def read_session() -> Iterator[Session]:
    """Read-only session context. Auto-closes at the end."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        SessionLocal.remove()


def new_bg_session() -> Session:
    """Create a fresh session for a background thread.

    Background threads (backup, AI streaming) must NOT share the request
    session. Caller is responsible for committing/rolling back and closing.
    """
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)()


def init_db(seed_defaults: bool = True) -> None:
    """Create all tables and seed default project + settings."""
    from models import ALL_MODELS  # noqa: WPS433 - lazy import to avoid cycles
    from sqlalchemy import inspect

    Base = _get_base()
    Base.metadata.create_all(engine)

    # Create FTS5 tables + triggers (idempotent).
    from models.search import install_fts
    install_fts(engine)

    # Seed default snippets/templates
    try:
        from services.snippet_service import seed_default_templates
        seed_default_templates()
    except Exception:
        pass  # snippets table might not exist yet on first run

    if seed_defaults:
        _seed_defaults()


def _get_base():
    """Lazy import of the declarative Base to avoid circular imports."""
    from models import Base
    return Base


def _seed_defaults() -> None:
    """Seed default project + settings rows if missing."""
    from models.project import Project
    from models.settings import Setting
    from models.settings import DEFAULT_SETTINGS

    with write_transaction() as s:
        if not s.query(Project).filter_by(id="default").first():
            s.add(Project(id="default", name="My Story",
                          subtitle="Book One of the trilogy"))
        for key, value in DEFAULT_SETTINGS.items():
            if not s.query(Setting).filter_by(key=key).first():
                s.add(Setting(key=key, value=value))
