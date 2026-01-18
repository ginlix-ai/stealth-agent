"""
API Client Module for ptc-cli
==============================

This module provides HTTP/SSE client for communicating with the PTC Agent server.

Components:
- client: SSEStreamClient for handling SSE streams from server API
- models: Message class for accumulating streaming chunks
- constants: Event colors, timeouts, and other configuration
"""

from ptc_cli.api.client import SSEStreamClient
from ptc_cli.api.models import Message
from ptc_cli.api.constants import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    EVENT_COLORS,
    SPINNER_FRAMES,
    STATUS_COLORS,
    STATUS_ICONS,
)

__all__ = [
    # Client
    "SSEStreamClient",
    # Models
    "Message",
    # Constants
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT",
    "EVENT_COLORS",
    "SPINNER_FRAMES",
    "STATUS_COLORS",
    "STATUS_ICONS",
]
