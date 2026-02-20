"""
AutomationScheduler — Background polling loop for time-based triggers.

Polls the database every POLL_INTERVAL seconds for automations whose
next_run_at has passed, claims them atomically, and dispatches execution
tasks via AutomationExecutor.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set
from uuid import uuid4

from croniter import croniter
from zoneinfo import ZoneInfo

from src.server.database import automation as auto_db
from src.server.services.automation_executor import AutomationExecutor

logger = logging.getLogger(__name__)

POLL_INTERVAL = 30  # seconds
SHUTDOWN_TIMEOUT = 60  # seconds to wait for running tasks on shutdown


class AutomationScheduler:
    """Singleton background service that polls for due automations."""

    _instance: Optional["AutomationScheduler"] = None

    @classmethod
    def get_instance(cls) -> "AutomationScheduler":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._server_id = str(uuid4())
        self._poll_task: Optional[asyncio.Task] = None
        self._running_tasks: Set[asyncio.Task] = set()
        self._shutdown_event = asyncio.Event()
        self._executor = AutomationExecutor.get_instance()

    @property
    def server_id(self) -> str:
        return self._server_id

    # ─── Lifecycle ─────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the polling loop and recover stale executions."""
        logger.info(
            f"[SCHEDULER] Starting AutomationScheduler "
            f"(server_id={self._server_id}, poll_interval={POLL_INTERVAL}s)"
        )
        # Recover stale executions from previous server instances
        await auto_db.mark_stale_executions_failed(self._server_id)

        self._shutdown_event.clear()
        self._poll_task = asyncio.create_task(
            self._poll_loop(), name="automation_scheduler_poll"
        )

    async def shutdown(self) -> None:
        """Gracefully stop the scheduler and wait for running executions."""
        logger.info("[SCHEDULER] Shutting down AutomationScheduler...")
        self._shutdown_event.set()

        # Cancel polling task
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        # Wait for running execution tasks
        if self._running_tasks:
            logger.info(
                f"[SCHEDULER] Waiting for {len(self._running_tasks)} "
                f"running executions (timeout={SHUTDOWN_TIMEOUT}s)..."
            )
            done, pending = await asyncio.wait(
                self._running_tasks, timeout=SHUTDOWN_TIMEOUT
            )
            if pending:
                logger.warning(
                    f"[SCHEDULER] {len(pending)} executions still running "
                    f"after timeout, cancelling..."
                )
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)

        logger.info("[SCHEDULER] AutomationScheduler shutdown complete")

    # ─── Polling Loop ──────────────────────────────────────────────

    async def _poll_loop(self) -> None:
        """Main polling loop that runs every POLL_INTERVAL seconds."""
        while not self._shutdown_event.is_set():
            try:
                await self._poll_once()
            except Exception as e:
                logger.error(f"[SCHEDULER] Poll error: {e}", exc_info=True)

            # Sleep in small increments to respond quickly to shutdown
            for _ in range(POLL_INTERVAL * 2):
                if self._shutdown_event.is_set():
                    return
                await asyncio.sleep(0.5)

    async def _poll_once(self) -> None:
        """Single polling iteration: claim due automations and dispatch."""
        now = datetime.now(timezone.utc)
        claimed = await auto_db.claim_due_automations(
            now=now,
            server_id=self._server_id,
        )

        if not claimed:
            return

        logger.info(f"[SCHEDULER] Claimed {len(claimed)} due automations")

        for automation in claimed:
            automation_id = str(automation["automation_id"])
            execution_id = automation["_execution_id"]

            # Calculate and set next_run_at for cron automations
            if automation["trigger_type"] == "cron" and automation.get("cron_expression"):
                next_run = self._calculate_next_run(
                    automation["cron_expression"],
                    automation.get("timezone", "UTC"),
                )
                await auto_db.update_automation_next_run(automation_id, next_run)
            # One-time automations: next_run_at already set to NULL by claim

            # Dispatch execution as a background task
            task = asyncio.create_task(
                self._run_execution(automation, execution_id),
                name=f"automation_exec_{automation_id[:8]}",
            )
            self._running_tasks.add(task)
            task.add_done_callback(self._running_tasks.discard)

    async def _run_execution(
        self,
        automation: Dict[str, Any],
        execution_id: str,
    ) -> None:
        """Wrapper that catches exceptions from executor."""
        try:
            await self._executor.execute(automation, execution_id)
        except Exception as e:
            logger.error(
                f"[SCHEDULER] Execution task failed: "
                f"automation_id={automation['automation_id']} "
                f"execution_id={execution_id} error={e}",
                exc_info=True,
            )

    # ─── Cron Helpers ──────────────────────────────────────────────

    @staticmethod
    def _calculate_next_run(
        cron_expression: str,
        tz_name: str = "UTC",
    ) -> datetime:
        """Calculate the next run time from a cron expression in the given timezone.

        Returns a UTC datetime.
        """
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            logger.warning(
                f"[SCHEDULER] Invalid timezone '{tz_name}', falling back to UTC"
            )
            tz = ZoneInfo("UTC")

        now_local = datetime.now(tz)
        cron = croniter(cron_expression, now_local)
        next_local = cron.get_next(datetime)

        # Ensure timezone-aware and convert to UTC
        if next_local.tzinfo is None:
            next_local = next_local.replace(tzinfo=tz)

        return next_local.astimezone(ZoneInfo("UTC"))

    @staticmethod
    def calculate_first_run(
        cron_expression: str,
        tz_name: str = "UTC",
    ) -> datetime:
        """Public helper: calculate the first next_run_at for a new cron automation."""
        return AutomationScheduler._calculate_next_run(cron_expression, tz_name)
