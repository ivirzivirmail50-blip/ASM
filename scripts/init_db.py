"""Initialize the database: create tables + seed defaults."""
from __future__ import annotations

import sys

from core.db import init_db
from core.logging import configure_logging


def main() -> int:
    configure_logging()
    print("Initializing database…")
    init_db(seed_defaults=True)
    print("Database ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
