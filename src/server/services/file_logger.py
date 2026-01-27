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

from src.server.database import conversation as db

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
        workspace_id: str,
        thread_id: str,
        pair_index: int = 0,
        agent: str = "ptc_agent",
    ) -> None:
        """Initialize the logger.

        Args:
            workspace_id: Workspace ID for filesystem association.
            thread_id: Current thread ID for operation tracking.
            pair_index: Query-response pair index (default 0 for initial query).
            agent: Agent name for operation attribution.
        """
        self.workspace_id = workspace_id
        self.thread_id = thread_id
        self.pair_index = pair_index
        self.agent = agent
        self._filesystem_id: str | None = None
        self._file_cache: dict[str, str] = {}  # file_path -> file_id
        self._operation_counters: dict[str, int] = {}  # file_path -> operation_index
        self._content_cache: dict[str, str] = {}  # file_path -> current content

    async def ensure_filesystem(self) -> str:
        """Ensure filesystem record exists for this workspace.

        Returns:
            filesystem_id for the workspace.
        """
        if self._filesystem_id:
            return self._filesystem_id

        self._filesystem_id = await db.ensure_filesystem(self.workspace_id)
        logger.debug(
            "Ensured filesystem for workspace",
            workspace_id=self.workspace_id,
            filesystem_id=self._filesystem_id,
        )
        return self._filesystem_id

    async def get_or_create_file(
        self,
        file_path: str,
    ) -> str:
        """Get file_id, creating file record if needed.

        This method only creates the file if it doesn't exist.
        Use update_file_metadata() to update line_count and updated_in_* fields.

        Args:
            file_path: Normalized file path in sandbox.

        Returns:
            file_id for the file.
        """
        # Return cached file_id if available
        if file_path in self._file_cache:
            return self._file_cache[file_path]

        filesystem_id = await self.ensure_filesystem()

        # Create file record if it doesn't exist (line_count=0 initially)
        file_id = await db.upsert_file(
            filesystem_id=filesystem_id,
            file_path=file_path,
            content=None,  # PTC doesn't store content in DB
            line_count=0,
            updated_in_thread_id=self.thread_id,
            updated_in_pair_index=self.pair_index,
            created_in_thread_id=self.thread_id,
            created_in_pair_index=self.pair_index,
        )

        self._file_cache[file_path] = file_id
        logger.debug(
            "Got or created file record",
            file_path=file_path,
            file_id=file_id,
        )
        return file_id

    async def update_file_metadata(
        self,
        file_id: str,
        content: str | None = None,
        line_count: int | None = None,
    ) -> None:
        """Update file metadata and content after an operation.

        Updates content, line_count and updated_in_* fields to reflect the latest operation.

        Args:
            file_id: File ID to update.
            content: Current file content (None = no change).
            line_count: New line count (if known).
        """
        await db.update_file_metadata(
            file_id=file_id,
            content=content,
            line_count=line_count,
            updated_in_thread_id=self.thread_id,
            updated_in_pair_index=self.pair_index,
        )

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

            # Get or create file record (doesn't update metadata)
            file_id = await self.get_or_create_file(file_path)

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

            # Determine old_string/new_string and current content based on operation type
            line_count = operation_data.get("line_count")
            current_content: str | None = None

            if operation == "write_file":
                old_str = None
                new_str = operation_data.get("content")  # Full file content
                # For write_file, the new content IS the full file content
                current_content = new_str or ""
                # Calculate line_count from content if not provided
                if line_count is None and current_content:
                    line_count = current_content.count('\n') + 1 if current_content else 0
            else:  # edit_file
                old_str = operation_data.get("old_string")
                new_str = operation_data.get("new_string")
                replace_all = operation_data.get("replace_all", False)
                content_override = operation_data.get("content")

                if content_override is not None:
                    current_content = content_override
                else:
                    # Get current content from cache or load from DB
                    prev_content: str | None = None
                    if file_path in self._content_cache:
                        prev_content = self._content_cache[file_path]
                    else:
                        # Try to load from DB (file may exist from previous session)
                        prev_content = await db.get_file_content(file_id)
                        if prev_content is not None:
                            self._content_cache[file_path] = prev_content

                    # Apply the string replacement if we have previous content
                    if prev_content is not None:
                        if replace_all:
                            current_content = prev_content.replace(old_str or "", new_str or "")
                        else:
                            current_content = prev_content.replace(old_str or "", new_str or "", 1)

                # Calculate line_count from new content
                if line_count is None and current_content is not None:
                    line_count = current_content.count('\n') + 1 if current_content else 0

            # Update content cache
            if current_content is not None:
                self._content_cache[file_path] = current_content

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

            # Update file metadata with content, line_count and updated_in_* fields
            await self.update_file_metadata(
                file_id=file_id,
                content=current_content,
                line_count=line_count,
            )

            logger.debug(
                "Logged file operation",
                operation=operation,
                file_path=file_path,
                operation_id=operation_id,
                operation_index=operation_index,
                line_count=line_count,
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
        This method creates a callback that:
        1. Updates content cache SYNCHRONOUSLY (to avoid race conditions)
        2. Schedules async DB operation

        Returns:
            Synchronous callback function.
        """
        import asyncio

        def sync_callback(operation_data: dict[str, Any]) -> None:
            """Synchronous callback that updates cache and schedules async logging."""
            # Update content cache SYNCHRONOUSLY before scheduling async DB operation
            # This prevents race conditions when write_file is followed by edit_file
            operation = operation_data.get("operation")
            file_path = operation_data.get("file_path")

            if file_path:
                if operation == "write_file":
                    content = operation_data.get("content")
                    self._content_cache[file_path] = content or ""
                elif operation == "edit_file":
                    content = operation_data.get("content")
                    if content is not None:
                        self._content_cache[file_path] = content
                    elif file_path in self._content_cache:
                        old_str = operation_data.get("old_string") or ""
                        new_str = operation_data.get("new_string") or ""
                        replace_all = operation_data.get("replace_all", False)
                        prev_content = self._content_cache[file_path]
                        if replace_all:
                            self._content_cache[file_path] = prev_content.replace(old_str, new_str)
                        else:
                            self._content_cache[file_path] = prev_content.replace(old_str, new_str, 1)

            # Schedule async DB operation
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
