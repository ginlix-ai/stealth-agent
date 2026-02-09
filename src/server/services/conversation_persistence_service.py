"""
Conversation Persistence Service - Workflow-driven DB persistence

Decouples database persistence from SSE connection lifecycle.
DB operations follow LangGraph workflow stages, not HTTP request/response cycles.

Architecture:
- Stage-level transactions (atomic operations per workflow stage)
- Simple logging: [conversation] prefix for all operations
- Thread-scoped service instances (one per workflow execution)
- Works independently of SSE streaming
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import uuid4
from contextlib import asynccontextmanager

from src.server.database import conversation as qr_db
from ptc_agent.utils.file_operations import _file_data_to_string

logger = logging.getLogger(__name__)

# Module-level instance cache: thread_id -> service instance
_service_instances: Dict[str, "ConversationPersistenceService"] = {}


class ConversationPersistenceService:
    """
    Manages database persistence for a single workflow execution thread.

    Lifecycle:
    1. get_instance(thread_id) - Get or create service for thread
    2. persist_query_start() - Create query at workflow start
    3. persist_interrupt() - Update thread + create response (atomic)
    4. persist_resume_feedback() - Create feedback query
    5. persist_completion() - Update thread + create response (atomic)
    6. cleanup() - Remove service instance from cache

    Usage:
        service = ConversationPersistenceService.get_instance(thread_id)
        await service.persist_query_start(content="Analyze Tesla", query_type="initial")
        # ... workflow executes ...
        await service.persist_completion(agent_messages={...})
        await service.cleanup()
    """

    def __init__(
        self,
        thread_id: str,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """
        Initialize persistence service for a workflow thread.

        Args:
            thread_id: LangGraph thread ID
            workspace_id: Workspace ID
            user_id: User ID
        """
        self.thread_id = thread_id
        self.workspace_id = workspace_id
        self.user_id = user_id

        # Post-persist callback (set by BackgroundTaskManager to clear event buffer, etc.)
        self._on_pair_persisted: Optional[callable] = None

        # Track persistence state per pair_index (Set-based for multi-iteration support)
        self._persisted_queries: set[int] = set()        # Track which pair_index queries created
        self._persisted_interrupts: set[int] = set()     # Track which pair_index interrupts saved
        self._persisted_completions: set[int] = set()    # Track which pair_index completions saved

        # Cache pair_index to avoid repeated DB queries
        self._pair_index_cache: Optional[int] = None
        self._current_query_id: Optional[str] = None
        self._current_response_id: Optional[str] = None

        logger.debug(
            f"[ConversationPersistence] Initialized service "
            f"thread_id={thread_id} workspace_id={workspace_id} user_id={user_id}"
        )

    @classmethod
    def get_instance(
        cls,
        thread_id: str,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> "ConversationPersistenceService":
        """
        Get or create service instance for a thread.

        Uses module-level cache to ensure single instance per thread.
        """
        if thread_id not in _service_instances:
            _service_instances[thread_id] = cls(thread_id, workspace_id, user_id)
            logger.debug(f"[ConversationPersistence] Created new service instance for thread_id={thread_id}")

        # Update workspace_id and user_id if provided (may not be available at creation)
        instance = _service_instances[thread_id]
        if workspace_id and not instance.workspace_id:
            instance.workspace_id = workspace_id
        if user_id and not instance.user_id:
            instance.user_id = user_id

        return instance

    async def cleanup(self):
        """Clean up service state and remove from instance cache."""
        logger.info(f"[ConversationPersistence] Cleaning up service for thread_id={self.thread_id}")

        # Clear tracking sets
        self._persisted_queries.clear()
        self._persisted_interrupts.clear()
        self._persisted_completions.clear()

        # Clear cached state
        self._pair_index_cache = None
        self._current_query_id = None
        self._current_response_id = None

        # Remove from instance cache
        if self.thread_id in _service_instances:
            del _service_instances[self.thread_id]
            logger.debug(f"[ConversationPersistence] Removed service from cache for thread_id={self.thread_id}")

    async def get_or_calculate_pair_index(self, conn=None) -> int:
        """
        Get cached pair_index or calculate from database.

        Caches result to avoid repeated COUNT queries within same workflow.
        """
        if self._pair_index_cache is None:
            self._pair_index_cache = await qr_db.get_next_pair_index(self.thread_id, conn=conn)
            logger.debug(
                f"[ConversationPersistence] Calculated pair_index={self._pair_index_cache} "
                f"for thread_id={self.thread_id}"
            )
        return self._pair_index_cache

    def increment_pair_index(self):
        """Increment cached pair_index after creating a query-response pair."""
        if self._pair_index_cache is not None:
            self._pair_index_cache += 1
            logger.debug(
                f"[ConversationPersistence] Incremented pair_index to {self._pair_index_cache} "
                f"for thread_id={self.thread_id}"
            )

    async def _finalize_pair(self):
        """Increment pair index and run post-persist hook (clear event buffer, etc.)."""
        self.increment_pair_index()
        if self._on_pair_persisted:
            try:
                await self._on_pair_persisted()
            except Exception as e:
                logger.warning(
                    f"[ConversationPersistence] _on_pair_persisted callback failed "
                    f"for thread_id={self.thread_id}: {e}"
                )

    async def persist_query_start(
        self,
        content: str,
        query_type: str,
        feedback_action: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ) -> str:
        """
        Persist query at workflow start.

        Should be called when workflow begins processing a user query.

        Args:
            content: User query content
            query_type: Query type (initial, follow_up, resume_feedback)
            feedback_action: Feedback action for HITL (ACCEPTED, EDIT_PLAN, etc.)
            metadata: Additional metadata
            timestamp: Query timestamp (defaults to now)

        Returns:
            query_id: Created query ID
        """
        pair_index = await self.get_or_calculate_pair_index()

        if pair_index in self._persisted_queries:
            logger.warning(
                f"[ConversationPersistence] Query already created for thread_id={self.thread_id} "
                f"pair_index={pair_index}, skipping"
            )
            return self._current_query_id

        try:
            query_id = str(uuid4())

            await qr_db.create_query(
                query_id=query_id,
                thread_id=self.thread_id,
                pair_index=pair_index,
                content=content,
                query_type=query_type,
                feedback_action=feedback_action,
                metadata=metadata,
                timestamp=timestamp
            )

            self._persisted_queries.add(pair_index)
            self._current_query_id = query_id

            logger.debug(
                f"[ConversationPersistence] Created query for thread_id={self.thread_id} "
                f"pair_index={pair_index} query_id={query_id}"
            )

            return query_id

        except Exception as e:
            logger.error(
                f"[ConversationPersistence] Failed to persist query start "
                f"thread_id={self.thread_id}: {e}",
                exc_info=True
            )
            raise

    async def persist_interrupt(
        self,
        interrupt_reason: str,
        state_snapshot: Optional[Dict[str, Any]] = None,
        agent_messages: Optional[Dict[str, Any]] = None,
        execution_time: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
        per_call_records: Optional[list] = None,
        tool_usage: Optional[Dict[str, int]] = None,
        streaming_chunks: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Persist interrupt state (atomic transaction).

        Groups operations:
        1. Update thread status to "interrupted"
        2. Create response with status="interrupted"
        3. Create usage record (token + infrastructure credits)

        Args:
            interrupt_reason: Reason for interrupt (e.g., "plan_review_required")
            state_snapshot: LangGraph state snapshot
            agent_messages: Agent messages so far
            execution_time: Execution time up to interrupt
            metadata: Additional metadata (msg_type, stock_code, etc.)
            timestamp: Response timestamp (defaults to now)
            per_call_records: Per-call token records for accurate cost calculation
            tool_usage: Tool usage counts for infrastructure cost tracking

        Returns:
            response_id: Created response ID
        """
        pair_index = await self.get_or_calculate_pair_index()

        if pair_index in self._persisted_interrupts:
            logger.warning(
                f"[ConversationPersistence] Interrupt already persisted for thread_id={self.thread_id} "
                f"pair_index={pair_index}, skipping"
            )
            return self._current_response_id

        try:
            response_id = str(uuid4())

            # Stage-level transaction: group update + create + usage tracking
            async with qr_db.get_db_connection() as conn:
                async with conn.transaction():
                    await qr_db.update_thread_status(self.thread_id, "interrupted", conn=conn)

                    await qr_db.create_response(
                        response_id=response_id,
                        thread_id=self.thread_id,
                        pair_index=pair_index,
                        status="interrupted",
                        interrupt_reason=interrupt_reason,
                        state_snapshot=state_snapshot,
                        agent_messages=agent_messages,
                        metadata=metadata,
                        execution_time=execution_time,
                        timestamp=timestamp,
                        streaming_chunks=streaming_chunks,
                        conn=conn
                    )

                    # NEW: Create usage record (token + infrastructure credits)
                    # Track credits even for interrupted workflows to enable proper billing
                    if per_call_records or tool_usage:
                        from src.server.services.usage_persistence_service import UsagePersistenceService

                        usage_service = UsagePersistenceService(
                            thread_id=self.thread_id,
                            workspace_id=self.workspace_id,
                            user_id=self.user_id
                        )

                        # Track token usage if available
                        if per_call_records:
                            await usage_service.track_llm_usage(per_call_records)

                        # Track tool usage if available
                        if tool_usage:
                            usage_service.record_tool_usage_batch(tool_usage)

                        # Extract deepthinking from metadata
                        # Note: msg_type is overridden to 'interrupted' for interrupted workflows
                        # to enable clear separation in analytics/billing
                        deepthinking = metadata.get("deepthinking", False) if metadata else False

                        # Persist to conversation_usage table (status='interrupted')
                        # Override msg_type to 'interrupted' for interrupted workflows
                        usage_persisted = await usage_service.persist_usage(
                            response_id=response_id,
                            timestamp=timestamp,
                            msg_type="interrupted",  # Always use 'interrupted' for interrupted workflows
                            deepthinking=deepthinking,
                            status="interrupted",
                            conn=conn
                        )

                        if usage_persisted:
                            logger.info(
                                f"Persisted interrupted workflow: thread_id={self.thread_id} response_id={response_id}"
                            )
                        else:
                            logger.warning(
                                f"[ConversationPersistence] Failed to persist usage for interrupted workflow "
                                f"thread_id={self.thread_id} response_id={response_id}"
                            )
                    else:
                        logger.debug(
                            f"[ConversationPersistence] No usage data to persist for interrupted workflow "
                            f"thread_id={self.thread_id} response_id={response_id}"
                        )

            self._persisted_interrupts.add(pair_index)
            self._current_response_id = response_id

            logger.info(
                f"[ConversationPersistence] Persisted interrupt for thread_id={self.thread_id} "
                f"pair_index={pair_index} response_id={response_id}"
            )

            # Increment pair_index and run post-persist hook (e.g. clear event buffer)
            await self._finalize_pair()

            return response_id

        except Exception as e:
            logger.error(
                f"[ConversationPersistence] Failed to persist interrupt "
                f"thread_id={self.thread_id}: {e}",
                exc_info=True
            )
            raise

    async def persist_resume_feedback(
        self,
        feedback_action: str,
        content: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ) -> str:
        """
        Persist resume feedback query.

        Called when user provides feedback after interrupt (e.g., accepts plan).

        Args:
            feedback_action: Feedback action (ACCEPTED, EDIT_PLAN, etc.)
            content: User's additional input (if any)
            metadata: Additional metadata
            timestamp: Query timestamp (defaults to now)

        Returns:
            query_id: Created query ID
        """
        try:
            query_id = str(uuid4())
            pair_index = await self.get_or_calculate_pair_index()

            await qr_db.create_query(
                query_id=query_id,
                thread_id=self.thread_id,
                pair_index=pair_index,
                content=content,
                query_type="resume_feedback",
                feedback_action=feedback_action,
                metadata=metadata,
                timestamp=timestamp
            )

            self.query_created = True
            self._current_query_id = query_id

            return query_id

        except Exception as e:
            logger.error(
                f"[ConversationPersistence] Failed to persist resume feedback "
                f"thread_id={self.thread_id}: {e}",
                exc_info=True
            )
            raise

    async def persist_completion(
        self,
        agent_messages: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        state_snapshot: Optional[Dict[str, Any]] = None,
        warnings: Optional[list] = None,
        errors: Optional[list] = None,
        execution_time: Optional[float] = None,
        timestamp: Optional[datetime] = None,
        per_call_records: Optional[list] = None,
        tool_usage: Optional[Dict[str, int]] = None,
        streaming_chunks: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Persist workflow completion (atomic transaction).

        Groups operations:
        1. Update thread status to "completed"
        2. Create response with status="completed"
        3. Create usage record (token + infrastructure credits)

        Args:
            agent_messages: All agent messages
            metadata: Additional metadata
            state_snapshot: Final LangGraph state
            warnings: Warning messages
            errors: Error messages
            execution_time: Total execution time
            timestamp: Response timestamp (defaults to now)
            per_call_records: Per-call token records for accurate cost calculation
            tool_usage: Tool usage counts for infrastructure cost tracking

        Returns:
            response_id: Created response ID
        """
        pair_index = await self.get_or_calculate_pair_index()

        if pair_index in self._persisted_completions:
            logger.warning(
                f"[ConversationPersistence] Completion already persisted for thread_id={self.thread_id} "
                f"pair_index={pair_index}, skipping"
            )
            return self._current_response_id

        try:
            response_id = str(uuid4())

            # Stage-level transaction: group update + create + usage tracking
            async with qr_db.get_db_connection() as conn:
                async with conn.transaction():
                    await qr_db.update_thread_status(self.thread_id, "completed", conn=conn)

                    await qr_db.create_response(
                        response_id=response_id,
                        thread_id=self.thread_id,
                        pair_index=pair_index,
                        status="completed",
                        agent_messages=agent_messages,
                        metadata=metadata,
                        state_snapshot=state_snapshot,
                        warnings=warnings,
                        errors=errors,
                        execution_time=execution_time,
                        timestamp=timestamp,
                        streaming_chunks=streaming_chunks,
                        conn=conn
                    )

                    # NEW: Create usage record (token + infrastructure credits)
                    if per_call_records or tool_usage:
                        from src.server.services.usage_persistence_service import UsagePersistenceService

                        usage_service = UsagePersistenceService(
                            thread_id=self.thread_id,
                            workspace_id=self.workspace_id,
                            user_id=self.user_id
                        )

                        # Track token usage if available
                        if per_call_records:
                            await usage_service.track_llm_usage(per_call_records)

                        # Track tool usage if available
                        if tool_usage:
                            usage_service.record_tool_usage_batch(tool_usage)

                        # Extract msg_type and deepthinking from metadata
                        msg_type = metadata.get("msg_type") if metadata else None
                        deepthinking = metadata.get("deepthinking", False) if metadata else False

                        # Persist to conversation_usage table (status='completed')
                        await usage_service.persist_usage(
                            response_id=response_id,
                            timestamp=timestamp,
                            msg_type=msg_type,
                            deepthinking=deepthinking,
                            status="completed",
                            conn=conn
                        )

            self._persisted_completions.add(pair_index)
            self._current_response_id = response_id

            logger.info(
                f"[ConversationPersistence] Persisted completion for thread_id={self.thread_id} "
                f"pair_index={pair_index} response_id={response_id}"
            )

            # Increment pair_index and run post-persist hook (e.g. clear event buffer)
            await self._finalize_pair()

            return response_id


        except Exception as e:
            logger.error(
                f"[ConversationPersistence] Failed to persist completion "
                f"thread_id={self.thread_id}: {e}",
                exc_info=True
            )
            raise

    async def persist_error(
        self,
        error_message: str,
        errors: Optional[list] = None,
        state_snapshot: Optional[Dict[str, Any]] = None,
        agent_messages: Optional[Dict[str, Any]] = None,
        execution_time: Optional[float] = None,
        timestamp: Optional[datetime] = None,
        per_call_records: Optional[list] = None,
        tool_usage: Optional[Dict[str, int]] = None,
        streaming_chunks: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Persist error state (atomic transaction).

        Groups operations:
        1. Update thread status to "error"
        2. Create response with status="error"
        3. Create usage record (token + infrastructure credits)

        Args:
            error_message: Error message
            errors: Error list
            state_snapshot: LangGraph state at error
            agent_messages: Agent messages before error
            execution_time: Execution time until error
            timestamp: Response timestamp (defaults to now)
            per_call_records: Per-call token records for accurate cost calculation
            tool_usage: Tool usage counts for infrastructure cost tracking
            metadata: Additional metadata (msg_type, deepthinking, etc.)

        Returns:
            response_id: Created response ID
        """
        try:
            response_id = str(uuid4())
            pair_index = await self.get_or_calculate_pair_index()

            if errors is None:
                errors = [error_message]

            # Stage-level transaction: group update + create + usage tracking
            async with qr_db.get_db_connection() as conn:
                async with conn.transaction():
                    await qr_db.update_thread_status(self.thread_id, "error", conn=conn)

                    await qr_db.create_response(
                        response_id=response_id,
                        thread_id=self.thread_id,
                        pair_index=pair_index,
                        status="cancelled",
                        interrupt_reason=None,
                        state_snapshot=state_snapshot,
                        agent_messages=agent_messages,
                        metadata=metadata,
                        warnings=None,
                        errors=None,
                        execution_time=execution_time,
                        timestamp=timestamp,
                        streaming_chunks=streaming_chunks,
                        conn=conn
                    )


                    # NEW: Create usage record (token + infrastructure credits)
                    # Track credits even for failed workflows for accurate billing
                    if per_call_records or tool_usage:
                        from src.server.services.usage_persistence_service import UsagePersistenceService

                        usage_service = UsagePersistenceService(
                            thread_id=self.thread_id,
                            workspace_id=self.workspace_id,
                            user_id=self.user_id
                        )

                        # Track token usage if available
                        if per_call_records:
                            await usage_service.track_llm_usage(per_call_records)

                        # Track tool usage if available
                        if tool_usage:
                            usage_service.record_tool_usage_batch(tool_usage)

                        # Extract msg_type and deepthinking from metadata
                        msg_type = metadata.get("msg_type") if metadata else None
                        deepthinking = metadata.get("deepthinking", False) if metadata else False

                        # Persist to conversation_usage table (status='error')
                        usage_persisted = await usage_service.persist_usage(
                            response_id=response_id,
                            timestamp=timestamp,
                            msg_type=msg_type,
                            deepthinking=deepthinking,
                            status="error",
                            conn=conn
                        )

                        if usage_persisted:
                            logger.info(
                                f"Persisted failed workflow: thread_id={self.thread_id} response_id={response_id}"
                            )
                        else:
                            logger.warning(
                                f"[ConversationPersistence] Failed to persist usage for failed workflow "
                                f"thread_id={self.thread_id} response_id={response_id}"
                            )
                    else:
                        logger.debug(
                            f"[ConversationPersistence] No usage data to persist for failed workflow "
                            f"thread_id={self.thread_id} response_id={response_id}"
                        )

            self._current_response_id = response_id

            logger.info(
                f"[ConversationPersistence] Persisted error for thread_id={self.thread_id} "
                f"pair_index={pair_index} response_id={response_id}"
            )

            # Increment pair_index and run post-persist hook (e.g. clear event buffer)
            await self._finalize_pair()

            return response_id

        except Exception as e:
            logger.error(
                f"[ConversationPersistence] Failed to persist error "
                f"thread_id={self.thread_id}: {e}",
                exc_info=True
            )
            raise

    async def persist_cancelled(
        self,
        state_snapshot: Optional[Dict[str, Any]] = None,
        agent_messages: Optional[Dict[str, Any]] = None,
        execution_time: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
        per_call_records: Optional[list] = None,
        tool_usage: Optional[Dict[str, int]] = None,
        streaming_chunks: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Persist cancelled state (atomic transaction).

        Groups operations:
        1. Update thread status to "cancelled"
        2. Create response with status="cancelled"
        3. Create usage record (token + infrastructure credits)

        Args:
            state_snapshot: LangGraph state at cancellation
            agent_messages: Agent messages before cancellation
            execution_time: Execution time until cancellation
            metadata: Additional metadata
            timestamp: Response timestamp (defaults to now)
            per_call_records: Per-call token records for accurate cost calculation
            tool_usage: Tool usage counts for infrastructure cost tracking

        Returns:
            response_id: Created response ID
        """
        try:
            response_id = str(uuid4())
            pair_index = await self.get_or_calculate_pair_index()

            # Stage-level transaction: group update + create + usage tracking
            async with qr_db.get_db_connection() as conn:
                async with conn.transaction():
                    await qr_db.update_thread_status(self.thread_id, "cancelled", conn=conn)

                    await qr_db.create_response(
                        response_id=response_id,
                        thread_id=self.thread_id,
                        pair_index=pair_index,
                        status="interrupted",
                        interrupt_reason=None,
                        agent_messages=agent_messages,
                        metadata=metadata,
                        state_snapshot=state_snapshot,
                        warnings=None,
                        errors=None,
                        execution_time=execution_time,
                        timestamp=timestamp,
                        streaming_chunks=streaming_chunks,
                        conn=conn
                    )


                    # NEW: Create usage record (token + infrastructure credits)
                    # Track credits even for cancelled workflows for accurate billing
                    if per_call_records or tool_usage:
                        from src.server.services.usage_persistence_service import UsagePersistenceService

                        usage_service = UsagePersistenceService(
                            thread_id=self.thread_id,
                            workspace_id=self.workspace_id,
                            user_id=self.user_id
                        )

                        # Track token usage if available
                        if per_call_records:
                            await usage_service.track_llm_usage(per_call_records)

                        # Track tool usage if available
                        if tool_usage:
                            usage_service.record_tool_usage_batch(tool_usage)

                        # Extract msg_type and deepthinking from metadata
                        msg_type = metadata.get("msg_type") if metadata else None
                        deepthinking = metadata.get("deepthinking", False) if metadata else False

                        # Persist to conversation_usage table (status='cancelled')
                        usage_persisted = await usage_service.persist_usage(
                            response_id=response_id,
                            timestamp=timestamp,
                            msg_type=msg_type,
                            deepthinking=deepthinking,
                            status="cancelled",
                            conn=conn
                        )

                        if usage_persisted:
                            logger.info(
                                f"Persisted cancelled workflow: thread_id={self.thread_id} response_id={response_id}"
                            )
                        else:
                            logger.warning(
                                f"[ConversationPersistence] Failed to persist usage for cancelled workflow "
                                f"thread_id={self.thread_id} response_id={response_id}"
                            )
                    else:
                        logger.debug(
                            f"[ConversationPersistence] No usage data to persist for cancelled workflow "
                            f"thread_id={self.thread_id} response_id={response_id}"
                        )

            self._current_response_id = response_id

            logger.info(
                f"[ConversationPersistence] Persisted cancellation for thread_id={self.thread_id} "
                f"pair_index={pair_index} response_id={response_id}"
            )

            # Increment pair_index and run post-persist hook (e.g. clear event buffer)
            await self._finalize_pair()

            return response_id

        except Exception as e:
            logger.error(
                f"[ConversationPersistence] Failed to persist cancellation "
                f"thread_id={self.thread_id}: {e}",
                exc_info=True
            )
            raise

    async def update_streaming_chunks(
        self,
        response_id: str,
        streaming_chunks: List[Dict[str, Any]],
    ) -> bool:
        """Update streaming_chunks for an already-persisted response.

        Used by the post-interrupt subagent result collector to replace
        incomplete subagent events with the full set captured by middleware.

        Args:
            response_id: The response ID to update
            streaming_chunks: Updated streaming chunks list

        Returns:
            True if the row was updated, False if not found
        """
        try:
            result = await qr_db.update_streaming_chunks(
                response_id=response_id,
                streaming_chunks=streaming_chunks,
            )
            if result:
                logger.info(
                    f"[ConversationPersistence] Updated streaming_chunks for "
                    f"response_id={response_id} ({len(streaming_chunks)} chunks)"
                )
            return result
        except Exception as e:
            logger.error(
                f"[ConversationPersistence] Failed to update streaming_chunks "
                f"response_id={response_id}: {e}",
                exc_info=True,
            )
            return False

    async def persist_filesystem_snapshot(
        self,
        files: Dict[str, Any],
        pending_events: Optional[list] = None
    ) -> None:
        """
        Persist filesystem state and operations to database.

        Args:
            files: state["files"] dictionary mapping file_path to FileData
            pending_events: state["pending_file_events"] list of operation dicts
        """
        if not files:
            logger.debug(f"[ConversationPersistence] No files to persist for thread_id={self.thread_id}")
            return

        if not self.workspace_id:
            logger.warning(
                f"[ConversationPersistence] Cannot persist filesystem: "
                f"workspace_id not set for thread_id={self.thread_id}"
            )
            return

        try:
            pair_index = await self.get_or_calculate_pair_index()
            pending_events = pending_events or []

            # Ensure filesystem exists
            filesystem_id = await qr_db.ensure_filesystem(self.workspace_id)

            # Persist each file
            file_count = 0
            operation_count = 0

            for file_path, file_data in files.items():
                # Validate file_data structure
                if not file_data or (isinstance(file_data, dict) and 'content' not in file_data):
                    logger.debug(f"[ConversationPersistence] Skipping file with no content: {file_path}")
                    continue

                # Convert FileData (list[str]) to string for database storage
                # FileData.content is list[str], need to join to string for DB
                content = _file_data_to_string(file_data)

                # Get line count from list length (before string conversion)
                if isinstance(file_data, dict):
                    line_count = len(file_data.get('content', []))
                else:
                    line_count = len(getattr(file_data, 'content', []))

                # Upsert file (content is now a proper string)
                file_id = await qr_db.upsert_file(
                    filesystem_id=filesystem_id,
                    file_path=file_path,
                    content=content,
                    line_count=line_count,
                    updated_in_thread_id=self.thread_id,
                    updated_in_pair_index=pair_index
                )
                file_count += 1

                # Find matching operations for this file
                # Events use artifact structure: payload.file_path contains the path
                matching_events = [
                    e for e in pending_events
                    if e.get('payload', {}).get('file_path') == file_path
                ]

                # Query database for current max operation_index for this file
                # This ensures operation_index increments correctly across threads
                max_op_index = await qr_db.get_max_operation_index_for_file(file_id)

                # Log each operation with corrected operation_index
                for i, event in enumerate(matching_events):
                    # Extract from artifact structure
                    payload = event.get('payload', {})
                    operation = payload.get('operation', 'write_file')

                    # For write_file: store full content in new_string
                    # For edit_file: store diffs in old_string/new_string
                    if operation == 'write_file':
                        old_str = None
                        new_str = payload.get('content')  # Full file content
                    else:  # edit_file
                        old_str = payload.get('old_string')  # Diff: replaced text
                        new_str = payload.get('new_string')  # Diff: replacement text

                    # Recalculate operation_index based on database state, not reducer state
                    # This fixes the bug where operation_index resets to 0 per thread
                    corrected_operation_index = max_op_index + 1 + i

                    await qr_db.log_file_operation(
                        file_id=file_id,
                        operation=operation,
                        thread_id=self.thread_id,
                        pair_index=pair_index,
                        agent=event.get('agent'),
                        tool_call_id=event.get('artifact_id'),  # artifact_id replaces tool_call_id
                        operation_index=corrected_operation_index,
                        old_string=old_str,
                        new_string=new_str,
                        timestamp=event.get('timestamp')
                    )
                    operation_count += 1

            logger.info(
                f"[ConversationPersistence] Persisted filesystem: "
                f"{file_count} files, {operation_count} operations for thread_id={self.thread_id}"
            )

        except Exception as e:
            logger.error(
                f"[ConversationPersistence] Failed to persist filesystem "
                f"thread_id={self.thread_id}: {e}",
                exc_info=True
            )
            # Don't raise - filesystem persistence is not critical for workflow completion
            # Just log the error and continue
