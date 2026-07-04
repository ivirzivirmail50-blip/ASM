"""Centralized input limits and validation helpers.

Single source of truth imported by services and forms.
"""
from __future__ import annotations

# Field length limits (chars unless noted).
TITLE_MAX = 500
NAME_MAX = 200
DESCRIPTION_MAX = 2000
SYNOPSIS_MAX = 4000
FREEFORM_MAX = 20000

# Array limits.
TAGS_MAX = 100
CHARACTER_IDS_MAX = 200

# Search.
QUERY_MAX = 200

# Upload.
UPLOAD_MAX_BYTES = 25 * 1024 * 1024       # 25 MB per file
REQUEST_BODY_MAX_BYTES = 30 * 1024 * 1024  # 30 MB per request body

# Activity log cap.
ACTIVITY_LOG_CAP = 2000

# Pagination defaults.
CHAPTERS_PER_PAGE = 30
WORLD_PER_PAGE = 40
SEARCH_RESULTS_PER_MODULE = 50

# Allowed upload extensions.
ALLOWED_UPLOAD_EXTS = frozenset({
    "txt", "md", "markdown", "docx", "pdf", "rtf", "odt", "html", "htm", "csv",
})

# Allowed MIME prefixes for upload sniffing (informational only; magic bytes
# are the authoritative check in security/upload.py).
ALLOWED_UPLOAD_MIMES = frozenset({
    "text/plain", "text/markdown", "text/html", "text/csv",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/pdf", "application/rtf", "application/vnd.oasis.opendocument.text",
})


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def truncate(value: str, limit: int) -> str:
    """Truncate freeform display text to limit (used only for display fields)."""
    if value is None:
        return ""
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"
