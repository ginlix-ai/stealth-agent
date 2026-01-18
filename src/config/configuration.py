import logging
import os
from dataclasses import dataclass, field, fields
from typing import Any, Optional, TYPE_CHECKING

from langchain_core.runnables import RunnableConfig

from src.config.settings import get_agent_recursion_limit as _get_agent_recursion_limit


logger = logging.getLogger(__name__)


def get_recursion_limit(default: int = 50) -> int:
    """Get the recursion limit from configuration or use default.

    Configuration is loaded from conf.yaml.

    Args:
        default: Default recursion limit if not configured (aligns with agent default)

    Returns:
        int: The recursion limit to use
    """
    limit = _get_agent_recursion_limit(default)
    logger.debug(f"Recursion limit set to: {limit}")
    return limit


@dataclass(kw_only=True)
class Configuration:
    """The configurable fields."""

    max_plan_iterations: int = 1  # Maximum number of plan iterations
    enable_deep_thinking: bool = False  # Whether to enable deep thinking

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "Configuration":
        """Create a Configuration instance from a RunnableConfig."""
        configurable = (
            config["configurable"] if config and "configurable" in config else {}
        )
        values: dict[str, Any] = {
            f.name: os.environ.get(f.name.upper(), configurable.get(f.name))
            for f in fields(cls)
            if f.init
        }
        return cls(**{k: v for k, v in values.items() if v})
