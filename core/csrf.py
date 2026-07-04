"""CSRF setup via Flask-WTF."""
from __future__ import annotations

from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()


def init_csrf(app) -> None:  # noqa: ANN001
    """Attach CSRFProtect to the app."""
    csrf.init_app(app)
