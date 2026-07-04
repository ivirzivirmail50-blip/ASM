"""FTS5 full-text search tables + sync triggers.

External-content FTS5 tables mirroring searchable text, kept in sync via
triggers: AFTER INSERT/UPDATE/DELETE on the source table update FTS.

If FTS5 is unavailable on the SQLite build, falls back to no-op (the
search_service will use LIKE instead).
"""
from __future__ import annotations

import logging
from sqlalchemy import text
from sqlalchemy.engine import Engine

log = logging.getLogger("asm.search")


_FTS_DDL = """
-- Chapters FTS (title, synopsis, content)
CREATE VIRTUAL TABLE IF NOT EXISTS chapters_fts USING fts5(
    title, synopsis, content,
    content='chapters', content_rowid='rowid',
    tokenize='porter unicode61'
);

-- Characters FTS (name, aliases, physical, psychology, background, philosophy, voice, notes)
CREATE VIRTUAL TABLE IF NOT EXISTS characters_fts USING fts5(
    name, aliases, physical, psychology, background, philosophy, voice, notes,
    content='characters', content_rowid='rowid',
    tokenize='porter unicode61'
);

-- World FTS (name, description, content, notes)
CREATE VIRTUAL TABLE IF NOT EXISTS world_fts USING fts5(
    name, description, content, notes,
    content='world_entries', content_rowid='rowid',
    tokenize='porter unicode61'
);
"""

_TRIGGERS_DDL = """
-- Chapter triggers
CREATE TRIGGER IF NOT EXISTS chapters_ai AFTER INSERT ON chapters BEGIN
    INSERT INTO chapters_fts(rowid, title, synopsis, content)
    VALUES (new.rowid, new.title, new.synopsis, new.content);
END;
CREATE TRIGGER IF NOT EXISTS chapters_ad AFTER DELETE ON chapters BEGIN
    INSERT INTO chapters_fts(chapters_fts, rowid, title, synopsis, content)
    VALUES ('delete', old.rowid, old.title, old.synopsis, old.content);
END;
CREATE TRIGGER IF NOT EXISTS chapters_au AFTER UPDATE ON chapters BEGIN
    INSERT INTO chapters_fts(chapters_fts, rowid, title, synopsis, content)
    VALUES ('delete', old.rowid, old.title, old.synopsis, old.content);
    INSERT INTO chapters_fts(rowid, title, synopsis, content)
    VALUES (new.rowid, new.title, new.synopsis, new.content);
END;

-- Character triggers
CREATE TRIGGER IF NOT EXISTS characters_ai AFTER INSERT ON characters BEGIN
    INSERT INTO characters_fts(rowid, name, aliases, physical, psychology, background, philosophy, voice, notes)
    VALUES (new.rowid, new.name, new.aliases, new.physical, new.psychology, new.background, new.philosophy, new.voice, new.notes);
END;
CREATE TRIGGER IF NOT EXISTS characters_ad AFTER DELETE ON characters BEGIN
    INSERT INTO characters_fts(characters_fts, rowid, name, aliases, physical, psychology, background, philosophy, voice, notes)
    VALUES ('delete', old.rowid, old.name, old.aliases, old.physical, old.psychology, old.background, old.philosophy, old.voice, old.notes);
END;
CREATE TRIGGER IF NOT EXISTS characters_au AFTER UPDATE ON characters BEGIN
    INSERT INTO characters_fts(characters_fts, rowid, name, aliases, physical, psychology, background, philosophy, voice, notes)
    VALUES ('delete', old.rowid, old.name, old.aliases, old.physical, old.psychology, old.background, old.philosophy, old.voice, old.notes);
    INSERT INTO characters_fts(rowid, name, aliases, physical, psychology, background, philosophy, voice, notes)
    VALUES (new.rowid, new.name, new.aliases, new.physical, new.psychology, new.background, new.philosophy, new.voice, new.notes);
END;

-- World triggers
CREATE TRIGGER IF NOT EXISTS world_ai AFTER INSERT ON world_entries BEGIN
    INSERT INTO world_fts(rowid, name, description, content, notes)
    VALUES (new.rowid, new.name, new.description, new.content, new.notes);
END;
CREATE TRIGGER IF NOT EXISTS world_ad AFTER DELETE ON world_entries BEGIN
    INSERT INTO world_fts(world_fts, rowid, name, description, content, notes)
    VALUES ('delete', old.rowid, old.name, old.description, old.content, old.notes);
END;
CREATE TRIGGER IF NOT EXISTS world_au AFTER UPDATE ON world_entries BEGIN
    INSERT INTO world_fts(world_fts, rowid, name, description, content, notes)
    VALUES ('delete', old.rowid, old.name, old.description, old.content, old.notes);
    INSERT INTO world_fts(rowid, name, description, content, notes)
    VALUES (new.rowid, new.name, new.description, new.content, new.notes);
END;
"""


def install_fts(engine: Engine) -> bool:
    """Create FTS5 virtual tables + triggers. Returns True on success.

    Uses executescript-style logic: each statement is executed separately,
    but trigger bodies (BEGIN ... END) are kept intact by splitting on
    'END;' as the trigger terminator.
    """
    import re
    try:
        with engine.begin() as conn:
            # 1. FTS5 virtual tables — split on ';' but skip comment-only lines.
            for raw in _FTS_DDL.split(";"):
                stmt = "\n".join(
                    line for line in raw.splitlines()
                    if not line.strip().startswith("--")
                ).strip()
                if stmt:
                    conn.execute(text(stmt))

            # 2. Triggers — each trigger ends with 'END;'.
            # Split on 'END;' to keep trigger bodies intact.
            trigger_blocks = _TRIGGERS_DDL.split("END;")
            for raw in trigger_blocks:
                stmt = "\n".join(
                    line for line in raw.splitlines()
                    if not line.strip().startswith("--")
                ).strip()
                if stmt:
                    conn.execute(text(stmt + " END;"))
        log.info("FTS5 tables + triggers installed.")
        return True
    except Exception as exc:
        log.warning("FTS5 unavailable; search will fall back to LIKE. (%s)", exc)
        return False
