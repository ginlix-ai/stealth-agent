"""Tests for background subagent middleware and tools."""

import asyncio
from contextlib import suppress

from ptc_agent.agent.middleware.background.middleware import BackgroundSubagentMiddleware
from ptc_agent.agent.middleware.background.tools import create_task_output_tool


async def test_aafter_agent_returns_none_immediately():
    """aafter_agent should return None immediately without waiting."""
    middleware = BackgroundSubagentMiddleware(timeout=1.0, enabled=True)

    async def _slow_task():
        await asyncio.sleep(10)  # Would timeout if we were waiting
        return {"success": True, "result": "ok"}

    asyncio_task = asyncio.create_task(_slow_task())

    await middleware.registry.register(
        task_id="tool_call_id_1",
        description="test task",
        subagent_type="general-purpose",
        asyncio_task=asyncio_task,
    )

    # aafter_agent should return immediately without waiting
    update = await middleware.aafter_agent(state={"messages": []}, runtime={})

    assert update is None

    # Clean up
    asyncio_task.cancel()
    with suppress(asyncio.CancelledError):
        await asyncio_task


async def test_task_output_returns_progress_for_running_task():
    """task_output should return progress info for running tasks."""
    middleware = BackgroundSubagentMiddleware(timeout=1.0, enabled=True)

    async def _slow_task():
        await asyncio.sleep(10)
        return {"success": True, "result": "ok"}

    asyncio_task = asyncio.create_task(_slow_task())

    await middleware.registry.register(
        task_id="tool_call_id_1",
        description="test task description",
        subagent_type="general-purpose",
        asyncio_task=asyncio_task,
    )

    # Create task_output tool and call it
    task_output_tool = create_task_output_tool(middleware.registry)
    result = await task_output_tool.ainvoke({"task_number": 1})

    # Should show progress for running task
    assert "Task-1" in result
    assert "[RUNNING]" in result

    # Clean up
    asyncio_task.cancel()
    with suppress(asyncio.CancelledError):
        await asyncio_task


async def test_task_output_returns_result_for_completed_task():
    """task_output should return cached result for completed tasks."""
    middleware = BackgroundSubagentMiddleware(timeout=1.0, enabled=True)

    async def _done_task():
        return {"success": True, "result": "the actual result"}

    asyncio_task = asyncio.create_task(_done_task())
    await asyncio_task  # Ensure done

    task = await middleware.registry.register(
        task_id="tool_call_id_1",
        description="test task",
        subagent_type="general-purpose",
        asyncio_task=asyncio_task,
    )

    # Mark as completed and store result
    task.completed = True
    task.result = {"success": True, "result": "the actual result"}

    # Create task_output tool and call it
    task_output_tool = create_task_output_tool(middleware.registry)
    result = await task_output_tool.ainvoke({"task_number": 1})

    # Should return the result for completed task
    assert "Task-1" in result
    assert "completed" in result
    assert "the actual result" in result


async def test_clear_registry_clears_all_tasks():
    """clear_registry should remove all tasks from the registry."""
    middleware = BackgroundSubagentMiddleware(timeout=1.0, enabled=True)

    async def _done_task():
        return {"success": True, "result": "ok"}

    asyncio_task = asyncio.create_task(_done_task())
    await asyncio_task

    await middleware.registry.register(
        task_id="tool_call_id_1",
        description="test task",
        subagent_type="general-purpose",
        asyncio_task=asyncio_task,
    )

    assert middleware.registry.task_count == 1

    middleware.clear_registry()

    assert middleware.registry.task_count == 0
