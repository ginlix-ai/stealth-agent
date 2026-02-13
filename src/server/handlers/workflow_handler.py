"""
Workflow Handler — Business logic for workflow control operations.

Extracted from src/server/app/workflow.py to separate business logic from route definitions.
"""

import asyncio
import logging

from fastapi import HTTPException

from src.server.utils.checkpoint_helpers import (
    build_checkpoint_config,
    get_checkpointer,
)

# Import setup module to access initialized globals
from src.server.app import setup

logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions for Checkpointer Access
# ============================================================================

async def get_checkpoint_tuple(thread_id: str, checkpoint_id: str = None):
    """
    Get checkpoint tuple from checkpointer.

    Args:
        thread_id: Thread identifier
        checkpoint_id: Optional specific checkpoint ID

    Returns:
        CheckpointTuple or None if not found
    """
    checkpointer = get_checkpointer()
    config = build_checkpoint_config(thread_id, checkpoint_id)
    return await checkpointer.aget_tuple(config)


def extract_state_values(checkpoint_tuple) -> dict:
    """
    Extract state values from checkpoint tuple.

    The checkpoint contains serialized channel values that we can extract.
    """
    if not checkpoint_tuple or not checkpoint_tuple.checkpoint:
        return {}

    checkpoint = checkpoint_tuple.checkpoint
    channel_values = checkpoint.get("channel_values", {})

    # Return the channel values as state
    return channel_values


async def cancel_workflow(thread_id: str) -> dict:
    """
    Explicitly cancel a workflow execution.

    Sets cancellation flag that the streaming generator will check.

    Args:
        thread_id: Thread ID to cancel

    Returns:
        Confirmation of cancellation with thread_id
    """
    try:
        from src.server.services.workflow_tracker import WorkflowTracker

        tracker = WorkflowTracker.get_instance()

        # Set cancellation flag (checked by exception handler)
        success = await tracker.set_cancel_flag(thread_id)

        # Mark workflow as cancelled immediately (don't wait for exception handler)
        # This provides immediate feedback to frontend
        await tracker.mark_cancelled(thread_id)

        # Update thread status in database for consistency
        from src.server.database import conversation as qr_db
        await qr_db.update_thread_status(thread_id, "cancelled")

        from src.config.settings import is_background_execution_enabled
        if is_background_execution_enabled():
            from src.server.services.background_task_manager import BackgroundTaskManager
            manager = BackgroundTaskManager.get_instance()
            cancel_success = await manager.cancel_workflow(thread_id)

            if not cancel_success:
                logger.warning(
                    f"Could not cancel background task for {thread_id} "
                    "(may be already completed or not found)"
                )

        if not success:
            logger.warning(
                f"Failed to set cancel flag for {thread_id} (Redis may be unavailable)"
            )

        from src.server.services.background_registry_store import BackgroundRegistryStore
        registry_store = BackgroundRegistryStore.get_instance()
        await registry_store.cancel_and_clear(thread_id, force=True)

        logger.info(f"Workflow cancelled: {thread_id}")

        return {
            "cancelled": True,
            "thread_id": thread_id,
            "message": "Cancellation signal sent. Workflow will stop shortly."
        }

    except Exception as e:
        logger.exception(f"Error cancelling workflow {thread_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel workflow: {str(e)}"
        )


async def soft_interrupt_workflow(thread_id: str) -> dict:
    """
    Soft interrupt a workflow - pause main agent, keep subagents running.

    Args:
        thread_id: Thread ID to soft interrupt

    Returns:
        Status including whether workflow can be resumed and active subagents
    """
    try:
        from src.config.settings import is_background_execution_enabled

        if not is_background_execution_enabled():
            # Without background execution, soft interrupt is same as cancel
            return {
                "status": "not_supported",
                "thread_id": thread_id,
                "can_resume": False,
                "background_tasks": [],
                "message": "Soft interrupt requires background execution mode"
            }

        from src.server.services.background_task_manager import BackgroundTaskManager
        manager = BackgroundTaskManager.get_instance()

        result = await manager.soft_interrupt_workflow(thread_id)

        logger.info(
            f"Workflow soft interrupted: {thread_id}, "
            f"background_tasks={result.get('background_tasks', [])}"
        )

        return result

    except Exception as e:
        logger.exception(f"Error soft interrupting workflow {thread_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to soft interrupt workflow: {str(e)}"
        )


async def get_workflow_status(thread_id: str) -> dict:
    """
    Get current workflow execution status.

    Args:
        thread_id: Thread ID to check status for

    Returns:
        Dict with current status, reconnectability, and progress info
    """
    try:
        from src.server.services.workflow_tracker import WorkflowTracker, WorkflowStatus

        tracker = WorkflowTracker.get_instance()

        # Get status from Redis
        redis_status = await tracker.get_status(thread_id)

        # Check checkpoint for additional info
        checkpoint_info = None
        try:
            checkpoint_tuple = await get_checkpoint_tuple(thread_id)
            if checkpoint_tuple:
                state_values = extract_state_values(checkpoint_tuple)
                checkpoint_data = checkpoint_tuple.checkpoint or {}
                pending_sends = checkpoint_data.get("pending_sends", [])

                checkpoint_info = {
                    "has_plan": False,  # PTC doesn't use plans
                    "has_final_report": bool(state_values.get("final_report")),
                    "message_count": len(state_values.get("messages", [])),
                    "completed": len(pending_sends) == 0,
                    "checkpoint_id": checkpoint_tuple.config.get("configurable", {}).get("checkpoint_id")
                }
        except Exception as e:
            logger.debug(f"Could not fetch checkpoint info for {thread_id}: {e}")

        # Determine overall status
        if redis_status:
            status = redis_status.get("status", WorkflowStatus.UNKNOWN)
            last_update = redis_status.get("last_update")
            workspace_id = redis_status.get("workspace_id")
            user_id = redis_status.get("user_id")
        elif checkpoint_info and checkpoint_info.get("completed"):
            # Found in checkpoint but not in Redis = old completed workflow
            status = WorkflowStatus.COMPLETED
            last_update = None
            workspace_id = None
            user_id = None
        else:
            # Not in Redis, not in checkpoint = unknown
            status = WorkflowStatus.UNKNOWN
            last_update = None
            workspace_id = None
            user_id = None

        # Determine if reconnection is possible
        can_reconnect = status in [WorkflowStatus.ACTIVE, WorkflowStatus.DISCONNECTED]

        # Get subagent info from background task manager
        active_subagents = []
        completed_subagents = []
        soft_interrupted = False

        from src.config.settings import is_background_execution_enabled
        if is_background_execution_enabled():
            try:
                from src.server.services.background_task_manager import BackgroundTaskManager
                manager = BackgroundTaskManager.get_instance()
                bg_status = await manager.get_workflow_status(thread_id)
                if bg_status.get("status") != "not_found":
                    active_subagents = bg_status.get("active_subagents", [])
                    completed_subagents = bg_status.get("completed_subagents", [])
                    soft_interrupted = bg_status.get("soft_interrupted", False)
            except Exception as e:
                logger.debug(f"Could not get background task status for {thread_id}: {e}")

        response = {
            "thread_id": thread_id,
            "status": status,
            "can_reconnect": can_reconnect,
            "last_update": last_update,
            "workspace_id": workspace_id,
            "user_id": user_id,
            "progress": checkpoint_info,
            "active_subagents": active_subagents,
            "completed_subagents": completed_subagents,
            "soft_interrupted": soft_interrupted,
        }

        logger.debug(f"Status check for {thread_id}: {status}")

        return response

    except Exception as e:
        logger.exception(f"Error checking workflow status for {thread_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check workflow status: {str(e)}"
        )


async def trigger_summarization(thread_id: str, keep_messages: int = 5) -> dict:
    """
    Manually trigger conversation summarization for a thread.

    Args:
        thread_id: The thread/conversation ID to summarize
        keep_messages: Number of recent messages to preserve (1-20, default 5)

    Returns:
        Dict with success, original_message_count, new_message_count, summary_length
    """
    try:
        # Import dependencies
        from src.server.database import conversation as qr_db
        from src.server.services.workspace_manager import WorkspaceManager
        from ptc_agent.agent.graph import build_ptc_graph_with_session
        from ptc_agent.agent.middleware.summarization import summarize_messages
        from src.config.settings import get_summarization_config

        # 1. Validate thread exists and get workspace_id
        thread_info = await qr_db.get_thread_with_summary(thread_id)
        if not thread_info:
            raise HTTPException(
                status_code=404,
                detail=f"Thread not found: {thread_id}"
            )

        workspace_id = thread_info.get("workspace_id")
        if not workspace_id:
            raise HTTPException(
                status_code=400,
                detail=f"Thread {thread_id} has no associated workspace"
            )

        # 2. Get session for the workspace
        workspace_manager = WorkspaceManager.get_instance()
        try:
            session = await workspace_manager.get_session_for_workspace(workspace_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # 3. Verify checkpointer is available
        checkpointer = get_checkpointer()

        # 4. Build graph to access state (use global config from setup)
        if not setup.agent_config:
            raise HTTPException(
                status_code=500,
                detail="Agent configuration not initialized"
            )

        graph = await build_ptc_graph_with_session(
            session=session,
            config=setup.agent_config,
            checkpointer=checkpointer,
        )

        # 5. Get current state
        config = build_checkpoint_config(thread_id)
        try:
            state = await asyncio.wait_for(
                graph.aget_state(config), timeout=10.0
            )
        except asyncio.TimeoutError:
            logger.error(f"aget_state timed out for thread {thread_id} during summarization")
            raise HTTPException(
                status_code=504,
                detail=f"Timed out retrieving state for thread: {thread_id}"
            )

        if not state or not state.values:
            raise HTTPException(
                status_code=404,
                detail=f"No state found for thread: {thread_id}"
            )

        messages = state.values.get("messages", [])
        if not messages:
            raise HTTPException(
                status_code=400,
                detail="No messages to summarize"
            )

        original_count = len(messages)

        # 6. Call summarize_messages
        summarization_config = get_summarization_config()
        model_name = summarization_config.get("llm", "gpt-5-nano")

        try:
            result = await summarize_messages(
                messages=messages,
                keep_messages=keep_messages,
                model_name=model_name,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # 7. Update state with summarized messages
        try:
            await asyncio.wait_for(
                graph.aupdate_state(
                    config,
                    {"messages": result["messages"]},
                ),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            logger.error(f"aupdate_state timed out for thread {thread_id} during summarization")
            raise HTTPException(
                status_code=504,
                detail=f"Timed out updating state for thread: {thread_id}"
            )

        logger.info(
            f"Manual summarization completed for thread {thread_id}: "
            f"{original_count} -> {result['preserved_count']} messages"
        )

        return {
            "success": True,
            "thread_id": thread_id,
            "original_message_count": original_count,
            "new_message_count": result["preserved_count"],
            "summary_length": len(result.get("summary_text", "")),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error triggering summarization for thread {thread_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger summarization: {str(e)}"
        )
