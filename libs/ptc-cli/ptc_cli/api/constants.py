"""
Constants for API Client Module
================================

Contains color schemes, spinner frames, and other configuration constants
used throughout the API client components.
"""

# Default configuration
DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT = 600.0
DEFAULT_MAX_ITERATIONS = 5

# Event type colors for visual distinction
EVENT_COLORS = {
    "message_chunk": "blue",
    "tool_calls": "green",
    "tool_call_chunks": "cyan",
    "tool_call_result": "yellow",
    "interrupt": "red",
    "error": "red",
    "thinking_status": "magenta",
}

# Spinner animation frames for tool call streaming
SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

# Status icons for todo list display
STATUS_ICONS = {
    "pending": "[ ]",
    "in_progress": "[→]",
    "completed": "[✓]",
}

# Status colors for todo list display
STATUS_COLORS = {
    "pending": "white",
    "in_progress": "yellow",
    "completed": "green",
}
