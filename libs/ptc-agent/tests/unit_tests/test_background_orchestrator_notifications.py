"""Tests for background orchestrator notification injection."""

import asyncio
from typing import Any

import pytest
from langchain_core.messages import HumanMessage

from ptc_agent.agent.middleware.background.middleware import BackgroundSubagentMiddleware
from ptc_agent.agent.middleware.background.orchestrator import BackgroundSubagentOrchestrator


class FakeAgent:
    """Minimal fake agent for orchestrator tests."""

    def __init__(self) -> None:
        self.invocations: list[dict[str, Any]] = []

    async def ainvoke(self, state: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        self.invocations.append(state)

        if len(self.invocations) == 1:
            return {"messages": [HumanMessage(content="first")], "foo": 123}

        return {"messages": [HumanMessage(content="second")], "foo": 123, "bar": "baz"}


@pytest.mark.asyncio
async def test_orchestrator_reinvokes_when_task_completed_fast() -> None:
    """Re-invokes even when tasks complete before pending check."""
    middleware = BackgroundSubagentMiddleware(timeout=1.0, enabled=True)

    async def _done_task() -> dict[str, Any]:
        return {"success": True, "result": "ok"}

    asyncio_task = asyncio.create_task(_done_task())
    await asyncio_task  # Ensure task is done before orchestrator checks pending

    task = await middleware.registry.register(
        task_id="tool_call_id_1",
        description="test task",
        subagent_type="general-purpose",
        asyncio_task=asyncio_task,
    )

    agent = FakeAgent()
    orchestrator = BackgroundSubagentOrchestrator(agent=agent, middleware=middleware, max_iterations=3)

    result = await orchestrator.ainvoke({"messages": [HumanMessage(content="user")]})

    assert len(agent.invocations) == 2

    second_state = agent.invocations[1]
    assert second_state.get("foo") == 123  # State keys preserved across re-invocation

    messages = second_state.get("messages", [])
    assert isinstance(messages[-1], HumanMessage)
    assert "Task-1" in messages[-1].content
    assert "task_output" in messages[-1].content

    assert task.result_seen is True
    assert result.get("bar") == "baz"

    # Should not produce another notification after being marked as seen.
    assert await orchestrator.check_and_get_notification() is None
