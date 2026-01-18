import asyncio

import pytest

pytest.importorskip("redis.asyncio")

from src.server.services.background_task_manager import BackgroundTaskManager, TaskStatus


@pytest.mark.asyncio
async def test_soft_interrupt_stops_workflow_and_allows_restart() -> None:
    # Isolate singleton for test
    BackgroundTaskManager._instance = None
    manager = BackgroundTaskManager.get_instance()

    # Avoid Redis/event-buffer dependencies in this unit test
    manager.enable_storage = False

    async def workflow_gen():
        i = 0
        while True:
            i += 1
            yield f"id: {i}\nevent: message_chunk\ndata: {{\"n\": {i}}}\n\n"
            await asyncio.sleep(0)

    thread_id = "thread-soft-interrupt"

    class _Snapshot:
        def __init__(self, values):
            self.values = values

    class _Graph:
        def __init__(self):
            self.flushes = 0

        async def aget_state(self, config):
            return _Snapshot({"messages": ["hello"], "foo": "bar"})

        async def aupdate_state(self, config, values, as_node=None, task_id=None):
            self.flushes += 1
            return config

    graph = _Graph()

    task_info = await manager.start_workflow(
        thread_id=thread_id,
        workflow_generator=workflow_gen(),
        metadata={},
        graph=graph,
    )

    # Let the task start
    await asyncio.sleep(0)

    result = await manager.soft_interrupt_workflow(thread_id)
    assert result["status"] == "soft_interrupted"

    # Soft-interrupt should end the workflow task quickly (so a follow-up can start)
    assert task_info.task is not None
    await asyncio.wait_for(task_info.task, timeout=1.0)

    # Flush happens on ESC
    assert graph.flushes >= 1

    assert await manager.get_task_status(thread_id) == TaskStatus.SOFT_INTERRUPTED

    # Starting a new workflow on same thread_id should now be allowed
    task_info2 = await manager.start_workflow(
        thread_id=thread_id,
        workflow_generator=workflow_gen(),
        metadata={},
        graph=None,
    )
    assert task_info2.status == TaskStatus.RUNNING

    # Cleanup
    await manager.cancel_workflow(thread_id)
    assert task_info2.task is not None
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task_info2.task, timeout=1.0)
