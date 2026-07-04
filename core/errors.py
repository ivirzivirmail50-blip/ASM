"""Typed exceptions with HTTP status mapping.

Each exception carries a user-facing message and an HTTP status code that
the global error handlers in app.py translate into responses.
"""
from __future__ import annotations


class AsmError(Exception):
    """Base class for all ASM typed errors."""

    status_code: int = 500
    code: str = "asm_error"
    user_message: str = "Something went wrong."

    def __init__(self, user_message: str | None = None, *,
                 code: str | None = None, status_code: int | None = None,
                 details: dict | None = None):
        self.user_message = user_message or self.user_message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details or {}
        super().__init__(self.user_message)


class NotFoundError(AsmError):
    status_code = 404
    code = "not_found"
    user_message = "Resource not found."


class ValidationError(AsmError):
    status_code = 400
    code = "validation_error"
    user_message = "Invalid input."


class UploadError(AsmError):
    status_code = 400
    code = "upload_error"
    user_message = "Upload failed."


class ConflictError(AsmError):
    status_code = 409
    code = "conflict"
    user_message = "Conflict."


class AiDisabledError(AsmError):
    status_code = 404
    code = "ai_disabled"
    user_message = "AI is disabled."


class AiProviderError(AsmError):
    status_code = 502
    code = "ai_provider_error"
    user_message = "AI provider error."
