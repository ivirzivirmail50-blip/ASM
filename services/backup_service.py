"""Backup service: ZIP-based auto-backup + restore."""
from __future__ import annotations

import logging
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from config import Config

log = logging.getLogger("asm.backup")


def create_backup() -> Path:
    """Create a timestamped ZIP of the SQLite DB + data/raw."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = Config.BACKUP_DIR / f"asm_backup_{ts}.zip"
    with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if Config.DB_PATH.exists():
            zf.write(Config.DB_PATH, arcname="asm.db")
        # Include raw uploads
        if Config.RAW_DIR.exists():
            for f in Config.RAW_DIR.rglob("*"):
                if f.is_file():
                    zf.write(f, arcname=str(f.relative_to(Config.DATA_DIR)))
    log.info("Backup created: %s", backup_path)
    return backup_path


def list_backups() -> list[dict]:
    backups = []
    for f in sorted(Config.BACKUP_DIR.glob("asm_backup_*.zip"),
                    key=lambda p: p.stat().st_mtime, reverse=True):
        st = f.stat()
        backups.append({
            "name": f.name,
            "path": str(f),
            "size": st.st_size,
            "mtime": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
        })
    return backups


def restore_backup(backup_path: str) -> None:
    """Restore DB + raw files from a ZIP backup. App must be restarted after."""
    p = Path(backup_path)
    if not p.exists():
        raise FileNotFoundError(p)
    with zipfile.ZipFile(p, "r") as zf:
        # Extract DB
        for member in zf.namelist():
            if member == "asm.db":
                # Backup current DB before overwriting
                if Config.DB_PATH.exists():
                    bak = Config.DB_PATH.with_suffix(f".bak.{int(datetime.now().timestamp())}")
                    Config.DB_PATH.rename(bak)
                with zf.open(member) as src, open(Config.DB_PATH, "wb") as dst:
                    dst.write(src.read())
            elif member.startswith("raw/"):
                target = Config.DATA_DIR / member
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(target, "wb") as dst:
                    dst.write(src.read())
    log.info("Restored from backup: %s", p)


def maybe_auto_backup() -> bool:
    """Check if auto-backup is due; create one if so. Returns True if backed up."""
    from models.settings import Setting
    from core.db import read_session
    with read_session() as s:
        enabled = Setting.get(s, "auto_backup_enabled", True)
        if not enabled:
            return False
        interval_hours = int(Setting.get(s, "auto_backup_interval_hours", 6) or 6)
    # Find most recent backup
    backups = list_backups()
    if not backups:
        create_backup()
        return True
    last_mtime = datetime.fromisoformat(backups[0]["mtime"].replace("Z", "+00:00"))
    elapsed = datetime.now(timezone.utc) - last_mtime
    if elapsed.total_seconds() >= interval_hours * 3600:
        create_backup()
        return True
    return False
