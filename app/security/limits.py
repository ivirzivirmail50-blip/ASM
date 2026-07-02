"""
Centralized field and size limits for input validation.
"""

# Field length limits
TITLE_MAX_LENGTH = 500
NAME_MAX_LENGTH = 200
TAGS_MAX_ITEMS = 100
CHARACTER_IDS_MAX_ITEMS = 200
QUERY_MAX_LENGTH = 200
WORLD_ENTRY_NAME_MAX = 300

# File upload limits (bytes)
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB
MAX_REQUEST_SIZE = 30 * 1024 * 1024  # 30 MB

# Allowed file extensions
ALLOWED_EXTENSIONS = {'txt', 'md', 'docx', 'pdf', 'rtf', 'odt', 'html', 'htm', 'csv'}

# Activity log cap
ACTIVITY_LOG_CAP = 2000

# Pagination defaults
CHAPTERS_PER_PAGE = 30
WORLD_ENTRIES_PER_PAGE = 40
SEARCH_RESULTS_PER_MODULE = 50

# Autosave interval (seconds)
AUTOSAVE_INTERVAL = 3

# Version snapshot interval (minutes)
VERSION_SNAPSHOT_INTERVAL = 15

# AI rate limit (requests per minute)
AI_RATE_LIMIT = 30
