"""
Custom exception classes for the application.
"""


class AppError(Exception):
    """Base exception for the application."""
    def __init__(self, message: str, code: str = "UNKNOWN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class NotFoundError(AppError):
    """Resource not found."""
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, "NOT_FOUND")


class ValidationError(AppError):
    """Validation failed."""
    def __init__(self, message: str, field: str = None):
        self.field = field
        super().__init__(message, "VALIDATION_ERROR")


class UploadError(AppError):
    """File upload failed."""
    def __init__(self, message: str):
        super().__init__(message, "UPLOAD_ERROR")


class ConflictError(AppError):
    """Resource conflict."""
    def __init__(self, message: str):
        super().__init__(message, "CONFLICT_ERROR")


class AiDisabledError(AppError):
    """AI is disabled."""
    def __init__(self, message: str = "AI functionality is disabled"):
        super().__init__(message, "AI_DISABLED")


class AiProviderError(AppError):
    """AI provider error."""
    def __init__(self, message: str):
        super().__init__(message, "AI_PROVIDER_ERROR")
