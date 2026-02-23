"""Flash Agent graph builder."""

import logging
from typing import Any

from ptc_agent.agent.flash.agent import FlashAgent
from ptc_agent.config import AgentConfig

logger = logging.getLogger(__name__)


def build_flash_graph(
    config: AgentConfig,
    checkpointer: Any | None = None,
    user_profile: dict | None = None,
) -> Any:
    """Build flash agent graph without sandbox.

    Unlike build_ptc_graph_with_session, this does not require
    workspace, session, or MCP registry - it's stateless and fast.

    Args:
        config: AgentConfig with LLM and flash settings
        checkpointer: Optional LangGraph checkpointer for state persistence
        user_profile: Optional user profile dict with name, timezone, locale

    Returns:
        Compiled LangGraph agent
    """
    logger.info("Building Flash agent graph (no sandbox)")

    flash_agent = FlashAgent(config)
    return flash_agent.create_agent(
        checkpointer=checkpointer,
        user_profile=user_profile,
    )
