"""Pytest fixtures for ASM."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Each test gets a fresh in-memory-ish DB via tmp_path.

    Patches core.db's engine + SessionLocal to use a fresh SQLite file
    for the duration of the test.
    """
    db_path = tmp_path / "test.db"
    db_uri = f"sqlite:///{db_path}"

    # Patch the engine + session factory in core.db
    import core.db
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import scoped_session, sessionmaker

    test_engine = create_engine(db_uri, future=True)

    @event.listens_for(test_engine, "connect")
    def _set_pragmas(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    test_session_factory = sessionmaker(bind=test_engine, expire_on_commit=False, future=True)
    test_SessionLocal = scoped_session(test_session_factory)

    # Replace module-level globals
    monkeypatch.setattr(core.db, "engine", test_engine)
    monkeypatch.setattr(core.db, "SessionLocal", test_SessionLocal)
    monkeypatch.setattr(core.db, "session_factory", test_session_factory)

    # Create all tables + FTS5 + default settings
    from models import Base, ALL_MODELS  # noqa: F401
    Base.metadata.create_all(test_engine)
    from models.search import install_fts
    install_fts(test_engine)

    # Seed default settings + default project
    from core.db import write_transaction
    from models.project import Project
    from models.settings import Setting, DEFAULT_SETTINGS
    with write_transaction() as s:
        s.add(Project(id="default", name="Test Story"))
        for k, v in DEFAULT_SETTINGS.items():
            s.add(Setting(key=k, value=v))

    yield

    test_SessionLocal.remove()
    Base.metadata.drop_all(test_engine)
    test_engine.dispose()
    # Cleanup WAL/SHM files
    for suffix in ("-wal", "-shm"):
        try:
            (Path(str(db_path) + suffix)).unlink(missing_ok=True)
        except Exception:
            pass


@pytest.fixture
def app(fresh_db):
    """Flask app — primarily for client-based tests."""
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seeded_app(fresh_db):
    """App with seed data loaded."""
    from scripts.seed_data import seed
    from app import create_app
    seed()
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    yield app


@pytest.fixture
def seeded_client(seeded_app):
    return seeded_app.test_client()
