"""PTC File Operation Logger.

Logs file operations from DaytonaBackend to the database for audit trail.
PTC stores file content in both Daytona sandbox AND the database for persistence.
Tracks: file paths, line counts, operations, and content diffs.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog

from src.server.database import conversation_db as db

logger = structlog.get_logger(__name__)


class FileOperationLogger:
    """Logs PTC file operations to the database.

    This class provides a callback-compatible interface for DaytonaBackend
    to persist file operations to PostgreSQL.

    For write_file: stores full content in new_string (old_string = NULL)
    For edit_file: stores old_string (text being replaced) and new_string (replacement)
    """

    def __init__(
        self,
        conversation_id: str,
        thread_id: str,
        pair_index: int = 0,
        agent: str = "ptc_agent",
    ) -> None:
        """Initialize the logger.

        Args:
            conversation_id: Conversation ID for filesystem association.
            thread_id: Current thread ID for operation tracking.
            pair_index: Query-response pair index (default 0 for initial query).
            agent: Agent name for operation attribution.
        """
        self.conversation_id = conversation_id
        self.thread_id = thread_id
        self.pair_index = pair_index
        self.agent = agent
        self._filesystem_id: str | None = None
        self._file_cache: dict[str, str] = {}  # file_path -> file_id
        self._operation_counters: dict[str, int] = {}  # file_path -> operation_index

    async def ensure_filesystem(self) -> str:
        """Ensure filesystem record exists for this conversation.

        Returns:
            filesystem_id for the conversation.
        """
        if self._filesystem_id:
            return self._filesystem_id

        self._filesystem_id = await db.ensure_filesystem(self.conversation_id)
        logger.debug(
            "Ensured filesystem for PTC conversation",
            conversation_id=self.conversation_id,
            filesystem_id=self._filesystem_id,
        )
        return self._filesystem_id

    async def ensure_file(
        self,
        file_path: str,
        line_count: int | None = None,
    ) -> str:
        """Ensure file record exists for this path.

        Args:
            file_path: Normalized file path in sandbox.
            line_count: Optional line count for the file.

        Returns:
            file_id for the file.
        """
        # Check cache first
        if file_path in self._file_cache:
            return self._file_cache[file_path]

        filesystem_id = await self.ensure_filesystem()

        # Use upsert_file to create/update file record
        # Note: file content is stored in operations, not in the file record itself
        file_id = await db.upsert_file(
            filesystem_id=filesystem_id,
            file_path=file_path,
            content=None,  # PTC doesn't store content in DB
            line_count=line_count or 0,
            updated_in_thread_id=self.thread_id,
            updated_in_pair_index=self.pair_index,
            created_in_thread_id=self.thread_id,
            created_in_pair_index=self.pair_index,
        )

        self._file_cache[file_path] = file_id
        logger.debug(
            "Ensured file record",
            file_path=file_path,
            file_id=file_id,
        )
        return file_id

    async def log_operation(self, operation_data: dict[str, Any]) -> str | None:
        """Log a file operation to the database.

        This is the callback method compatible with DaytonaBackend.operation_callback.

        Args:
            operation_data: Dict containing:
                - operation: Operation type (write_file, edit_file)
                - file_path: Normalized file path
                - timestamp: ISO timestamp
                - line_count: (optional) Line count for write operations
                - occurrences: (optional) Edit occurrences
                - replace_all: (optional) Whether replace_all was used

        Returns:
            operation_id if logged successfully, None otherwise.
        """
        try:
            operation = operation_data.get("operation")
            file_path = operation_data.get("file_path")

            if not operation or not file_path:
                logger.warning("Invalid operation data", data=operation_data)
                return None

            # Ensure file record exists
            line_count = operation_data.get("line_count")
            file_id = await self.ensure_file(file_path, line_count)

            # Get next operation index for this file
            if file_path not in self._operation_counters:
                # Load from DB to continue from existing operations
                self._operation_counters[file_path] = (
                    await db.get_max_operation_index_for_file(file_id) + 1
                )

            operation_index = self._operation_counters[file_path]
            self._operation_counters[file_path] += 1

            # Parse timestamp
            timestamp_str = operation_data.get("timestamp")
            timestamp = None
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                except ValueError:
                    timestamp = datetime.now(UTC)

            # Determine old_string/new_string based on operation type
            if operation == "write_file":
                old_str = None
                new_str = operation_data.get("content")  # Full file content
            else:  # edit_file
                old_str = operation_data.get("old_string")
                new_str = operation_data.get("new_string")

            # Log the operation
            operation_id = await db.log_file_operation(
                file_id=file_id,
                operation=operation,
                thread_id=self.thread_id,
                pair_index=self.pair_index,
                agent=self.agent,
                tool_call_id=None,  # PTC doesn't have tool_call_id
                operation_index=operation_index,
                old_string=old_str,
                new_string=new_str,
                timestamp=timestamp,
            )

            logger.debug(
                "Logged file operation",
                operation=operation,
                file_path=file_path,
                operation_id=operation_id,
                operation_index=operation_index,
            )

            return operation_id

        except Exception:
            logger.exception(
                "Failed to log file operation",
                operation_data=operation_data,
            )
            return None

    def create_sync_callback(self) -> callable:
        """Create a synchronous callback for DaytonaBackend.

        DaytonaBackend's callback is synchronous, but our logging is async.
        This method creates a callback that schedules the async operation.

        Returns:
            Synchronous callback function.
        """
        import asyncio

        def sync_callback(operation_data: dict[str, Any]) -> None:
            """Synchronous callback that schedules async logging."""
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.log_operation(operation_data))
            except RuntimeError:
                # No running loop, log warning
                logger.warning(
                    "No event loop available for file operation logging",
                    operation_data=operation_data,
                )

        return sync_callback

    def update_pair_index(self, pair_index: int) -> None:
        """Update the pair index for subsequent operations.

        Called when moving to a new query-response pair.

        Args:
            pair_index: New pair index.
        """
        self.pair_index = pair_index
