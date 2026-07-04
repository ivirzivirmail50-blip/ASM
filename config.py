"""Absolute Story Manager — configuration."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = DATA_DIR / "logs"
RAW_DIR = DATA_DIR / "raw"
MEDIA_DIR = DATA_DIR / "media"
BACKUP_DIR = DATA_DIR / "backups"
EXPORT_DIR = DATA_DIR / "exports"
DB_PATH = DATA_DIR / "asm.db"


class Config:
    """Base configuration loaded from env vars with sane defaults."""

    SECRET_KEY = os.environ.get("ASM_SECRET_KEY", "asm-dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "ASM_DB_URI", f"sqlite:///{DB_PATH}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    MAX_CONTENT_LENGTH = 30 * 1024 * 1024  # 30 MB total request body
    TESTING = False
    DEBUG = False

    # Derived paths (used by services)
    DATA_DIR = DATA_DIR
    LOG_DIR = LOG_DIR
    RAW_DIR = RAW_DIR
    MEDIA_DIR = MEDIA_DIR
    BACKUP_DIR = BACKUP_DIR
    EXPORT_DIR = EXPORT_DIR
    DB_PATH = DB_PATH


def ensure_dirs() -> None:
    """Create runtime data directories if missing."""
    for d in (DATA_DIR, LOG_DIR, RAW_DIR, MEDIA_DIR, BACKUP_DIR, EXPORT_DIR,
              MEDIA_DIR / "maps", MEDIA_DIR / "avatars"):
        d.mkdir(parents=True, exist_ok=True)
