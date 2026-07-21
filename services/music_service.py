"""Writing Music Player — serve local audio files for focus music.

The writer uploads audio files (mp3, ogg, wav) to data/media/music/.
This service lists available tracks and serves them. The frontend
HTML5 audio player handles playback.

No new model needed — files are stored on disk.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from config import Config

log = logging.getLogger("asm.music")

MUSIC_DIR = Path(Config.MEDIA_DIR) / "music"
ALLOWED_EXTENSIONS = {".mp3", ".ogg", ".wav", ".m4a", ".flac"}


def ensure_music_dir() -> Path:
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    return MUSIC_DIR


def list_tracks() -> list[dict[str, Any]]:
    """List all audio files in the music directory."""
    ensure_music_dir()
    tracks: list[dict[str, Any]] = []
    for f in sorted(MUSIC_DIR.iterdir()):
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS:
            stat = f.stat()
            tracks.append({
                "filename": f.name,
                "size": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "url": f"/media/music/{f.name}",
            })
    return tracks


def save_track(filename: str, content: bytes) -> dict[str, Any]:
    """Save an uploaded audio file."""
    ensure_music_dir()
    # Sanitize filename
    safe_name = os.path.basename(filename)
    if not safe_name or safe_name.startswith("."):
        raise ValueError("Invalid filename")
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Extension '{ext}' not allowed. Use: {', '.join(ALLOWED_EXTENSIONS)}")
    filepath = MUSIC_DIR / safe_name
    filepath.write_bytes(content)
    stat = filepath.stat()
    return {
        "filename": safe_name,
        "size": stat.st_size,
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
        "url": f"/media/music/{safe_name}",
    }


def delete_track(filename: str) -> bool:
    """Delete an audio file."""
    ensure_music_dir()
    safe_name = os.path.basename(filename)
    filepath = MUSIC_DIR / safe_name
    if filepath.exists() and filepath.is_file():
        filepath.unlink()
        return True
    return False
