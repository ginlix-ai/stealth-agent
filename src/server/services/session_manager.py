"""
PTC Session Manager Service.

Manages ptc-agent session lifecycle for the server:
- Caches sessions by conversation_id
- Handles sandbox initialization/cleanup
- Implements idle timeout cleanup
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ptc_agent.config import AgentConfig
from ptc_agent.core.session import Session, SessionManager

logger = logging.getLogger(__name__)


@dataclass
class SessionMetadata:
    """Metadata for tracking session lifecycle."""

    conversation_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_active: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sandbox_id: Optional[str] = None
    request_count: int = 0

    def touch(self) -> None:
        """Update last_active timestamp."""
        self.last_active = datetime.now(timezone.utc)
        self.request_count += 1


class SessionService:
    """
    Service for managing PTC agent sessions with idle timeout cleanup.

    Sessions are cached by conversation_id and reused across requests.
    Idle sessions are cleaned up periodically based on idle_timeout.
    """

    _instance: Optional["SessionService"] = None
    _lock = asyncio.Lock()

    def __init__(
        self,
        config: AgentConfig,
        idle_timeout: int = 1800,  # 30 minutes default
        cleanup_interval: int = 300,  # 5 minutes
    ):
        """
        Initialize PTC Session Service.

        Args:
            config: AgentConfig for creating sessions
            idle_timeout: Seconds before idle sessions are cleaned up
            cleanup_interval: Seconds between cleanup runs
        """
        self.config = config
        self.idle_timeout = idle_timeout
        self.cleanup_interval = cleanup_interval

        # Session metadata tracking (separate from ptc-agent's SessionManager)
        self._metadata: dict[str, SessionMetadata] = {}

        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._shutdown = False

        logger.info(
            "SessionService initialized",
            extra={
                "idle_timeout": idle_timeout,
                "cleanup_interval": cleanup_interval,
            }
        )

    @classmethod
    def get_instance(
        cls,
        config: Optional[AgentConfig] = None,
        **kwargs,
    ) -> "SessionService":
        """
        Get or create singleton instance.

        Args:
            config: AgentConfig (required on first call)
            **kwargs: Additional arguments for __init__

        Returns:
            SessionService instance
        """
        if cls._instance is None:
            if config is None:
                raise ValueError("config is required on first call to get_instance")
            cls._instance = cls(config, **kwargs)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (for testing)."""
        cls._instance = None

    async def get_or_create_session(
        self,
        conversation_id: str,
        sandbox_id: Optional[str] = None,
    ) -> Session:
        """
        Get existing session or create new one for conversation.

        Args:
            conversation_id: Unique conversation identifier
            sandbox_id: Optional existing sandbox ID to reconnect to

        Returns:
            Initialized Session instance
        """
        async with self._lock:
            # Get or create session via ptc-agent's SessionManager
            core_config = self.config.to_core_config()
            session = SessionManager.get_session(conversation_id, core_config)

            # Track metadata
            if conversation_id not in self._metadata:
                self._metadata[conversation_id] = SessionMetadata(
                    conversation_id=conversation_id
                )
                logger.info(f"Created new session for conversation: {conversation_id}")

            metadata = self._metadata[conversation_id]
            metadata.touch()

            # Initialize session if needed
            if not session._initialized:
                logger.info(
                    f"Initializing session for {conversation_id}",
                    extra={"sandbox_id": sandbox_id}
                )
                await session.initialize(sandbox_id=sandbox_id)

                # Store sandbox_id for reconnection
                if session.sandbox:
                    metadata.sandbox_id = getattr(
                        session.sandbox, 'sandbox_id', None
                    )

                # Sync skills to sandbox if enabled
                if self.config.skills.enabled and session.sandbox:
                    skill_dirs = self.config.skills.local_skill_dirs_with_sandbox()
                    reusing_sandbox = sandbox_id is not None
                    try:
                        did_upload = await session.sandbox.sync_skills(
                            skill_dirs,
                            reusing_sandbox=reusing_sandbox,
                        )
                        if did_upload:
                            logger.info(f"Skills synced for conversation: {conversation_id}")
                        else:
                            logger.debug(f"Skills unchanged for conversation: {conversation_id}")
                    except Exception as e:
                        # Skills are helpful but should not prevent session startup
                        logger.warning(
                            f"Skills sync failed for {conversation_id}: {e}",
                            exc_info=True
                        )

            return session

    async def get_session(self, conversation_id: str) -> Optional[Session]:
        """
        Get existing session without creating new one.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            Session if exists and initialized, None otherwise
        """
        if conversation_id not in self._metadata:
            return None

        core_config = self.config.to_core_config()
        session = SessionManager.get_session(conversation_id, core_config)

        if session._initialized:
            self._metadata[conversation_id].touch()
            return session

        return None

    def get_session_metadata(self, conversation_id: str) -> Optional[SessionMetadata]:
        """Get metadata for a session."""
        return self._metadata.get(conversation_id)

    async def cleanup_session(self, conversation_id: str) -> None:
        """
        Clean up a specific session.

        Args:
            conversation_id: Conversation identifier
        """
        logger.info(f"Cleaning up session: {conversation_id}")

        # Remove metadata
        if conversation_id in self._metadata:
            del self._metadata[conversation_id]

        # Cleanup via ptc-agent's SessionManager
        await SessionManager.cleanup_session(conversation_id)

    async def cleanup_idle_sessions(self) -> int:
        """
        Clean up sessions that have been idle for too long.

        Returns:
            Number of sessions cleaned up
        """
        now = datetime.now(timezone.utc)
        idle_conversations = []

        for conv_id, metadata in self._metadata.items():
            idle_seconds = (now - metadata.last_active).total_seconds()
            if idle_seconds > self.idle_timeout:
                idle_conversations.append(conv_id)
                logger.info(
                    f"Session {conv_id} idle for {idle_seconds:.0f}s, marking for cleanup"
                )

        # Cleanup idle sessions
        for conv_id in idle_conversations:
            try:
                await self.cleanup_session(conv_id)
            except Exception as e:
                logger.error(f"Error cleaning up session {conv_id}: {e}")

        if idle_conversations:
            logger.info(f"Cleaned up {len(idle_conversations)} idle sessions")

        return len(idle_conversations)

    async def start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task is not None:
            return

        self._shutdown = False

        async def cleanup_loop():
            while not self._shutdown:
                try:
                    await asyncio.sleep(self.cleanup_interval)
                    if not self._shutdown:
                        await self.cleanup_idle_sessions()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in cleanup loop: {e}")

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info("PTC session cleanup task started")

    async def shutdown(self) -> None:
        """Shutdown service and stop all sessions."""
        logger.info("Shutting down SessionService...")

        self._shutdown = True

        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        # Stop all sessions (preserve sandboxes for reconnect)
        await SessionManager.stop_all()
        self._metadata.clear()

        logger.info("SessionService shutdown complete")

    def get_active_sessions(self) -> list[str]:
        """Get list of active conversation IDs."""
        return list(self._metadata.keys())

    def get_session_count(self) -> int:
        """Get count of active sessions."""
        return len(self._metadata)

    def get_stats(self) -> dict:
        """Get service statistics."""
        return {
            "active_sessions": self.get_session_count(),
            "idle_timeout": self.idle_timeout,
            "cleanup_interval": self.cleanup_interval,
            "conversations": [
                {
                    "conversation_id": m.conversation_id,
                    "created_at": m.created_at.isoformat(),
                    "last_active": m.last_active.isoformat(),
                    "request_count": m.request_count,
                    "sandbox_id": m.sandbox_id,
                }
                for m in self._metadata.values()
            ],
        }
