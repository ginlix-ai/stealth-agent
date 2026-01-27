"""
Token tracking initialization and management.

Provides utilities for initializing token tracking with PerCallTokenTracker
and managing execution tracking lifecycle.
"""

import logging
from typing import Optional

from .per_call_token_tracker import PerCallTokenTracker
from .core import ExecutionTracker

logger = logging.getLogger(__name__)


class TokenTrackingManager:
    """
    Manages token tracking initialization and lifecycle.

    Encapsulates setup of token callback and execution tracker for workflow runs.
    """

    @staticmethod
    def initialize_tracking(
        thread_id: str,
        track_tokens: bool = True
    ) -> PerCallTokenTracker:
        """
        Initialize token and execution tracking for a workflow run.

        Args:
            thread_id: Thread identifier for logging
            track_tokens: Whether to enable token tracking (always True, kept for compatibility)

        Returns:
            PerCallTokenTracker instance
        """
        # Initialize per-call token tracking callback for accurate tiered pricing
        token_callback = PerCallTokenTracker()

        # Start execution tracking to capture agent messages and tool calls
        ExecutionTracker.start_tracking()

        logger.debug(f"Token tracking and execution tracking started for thread_id={thread_id}")

        return token_callback

    @staticmethod
    def stop_tracking(thread_id: str) -> None:
        """
        Stop execution tracking and cleanup.

        Args:
            thread_id: Thread identifier for logging
        """
        ExecutionTracker.stop_tracking()
        logger.debug(f"Execution tracking stopped for thread_id={thread_id}")


# Public API
__all__ = [
    'TokenTrackingManager',
]
