import pathlib
import sys

import pytest

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

# Ensure repo root is on sys.path so `import src.*` works under pytest.
# Also add `src/` so `import ptc_agent.*` works (ptc_agent lives under src/).
ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from src.server.services.conversation_persistence_service import ConversationPersistenceService


class FakeConn:
    @asynccontextmanager
    async def transaction(self):
        yield


@asynccontextmanager
async def fake_get_db_connection():
    yield FakeConn()


@pytest.mark.asyncio
async def test_persist_interrupt_forwards_streaming_chunks(monkeypatch):
    thread_id = "thread-test"

    monkeypatch.setattr(
        "src.server.services.conversation_persistence_service.qr_db.get_next_pair_index",
        AsyncMock(return_value=0),
    )

    create_response = AsyncMock(return_value={})
    monkeypatch.setattr(
        "src.server.services.conversation_persistence_service.qr_db.create_response",
        create_response,
    )
    monkeypatch.setattr(
        "src.server.services.conversation_persistence_service.qr_db.update_thread_status",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "src.server.services.conversation_persistence_service.qr_db.get_db_connection",
        fake_get_db_connection,
    )

    service = ConversationPersistenceService.get_instance(
        thread_id=thread_id,
        workspace_id="workspace-test",
        user_id="user-test",
    )

    chunks = [
        {"event": "message_chunk", "data": {"content": "hello", "thread_id": thread_id}},
        {"event": "interrupt", "data": {"thread_id": thread_id, "finish_reason": "interrupt"}},
    ]

    try:
        await service.persist_interrupt(
            interrupt_reason="plan_review_required",
            streaming_chunks=chunks,
        )
    finally:
        await service.cleanup()

    assert create_response.await_count == 1
    assert create_response.await_args is not None
    assert create_response.await_args.kwargs.get("streaming_chunks") == chunks
