"""Sub-agent definitions for deepagent delegation."""

from collections.abc import Callable
from typing import Any

from .general import create_general_subagent, get_general_subagent_config
from .research import create_research_subagent, get_research_subagent_config

# Registry mapping subagent names to their creation functions
SUBAGENT_REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {
    "research": create_research_subagent,
    "general-purpose": create_general_subagent,
}

# Subagents that require sandbox and mcp_registry
STATEFUL_SUBAGENTS = {"general-purpose"}

# Parameter mapping for each subagent type
# Maps generic parameter names to subagent-specific parameter names
SUBAGENT_PARAMS = {
    "research": {
        "accepted": ["max_researcher_iterations", "mcp_tools", "current_time"],
    },
    "general-purpose": {
        "accepted": ["max_iterations", "additional_tools", "include_mcp_docs", "tool_exposure_mode", "filesystem_tools", "current_time"],
    },
}


def create_subagent_by_name(
    name: str,
    sandbox: Any | None = None,
    mcp_registry: Any | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Create a subagent by name using the registry.

    Args:
        name: Name of the subagent (e.g., "research", "general-purpose")
        sandbox: PTCSandbox instance (required for stateful subagents)
        mcp_registry: MCPRegistry instance (required for stateful subagents)
        **kwargs: Additional arguments passed to the subagent creation function

    Returns:
        Configured subagent dictionary

    Raises:
        ValueError: If subagent name is not found in registry
        ValueError: If stateful subagent is missing required dependencies
    """
    if name not in SUBAGENT_REGISTRY:
        available = ", ".join(SUBAGENT_REGISTRY.keys())
        msg = f"Unknown subagent: '{name}'. Available: {available}"
        raise ValueError(msg)

    create_fn = SUBAGENT_REGISTRY[name]

    # Filter kwargs to only include parameters accepted by this subagent
    accepted_params = SUBAGENT_PARAMS.get(name, {}).get("accepted", [])
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in accepted_params}

    # Check if this is a stateful subagent requiring sandbox/mcp_registry
    if name in STATEFUL_SUBAGENTS:
        if sandbox is None or mcp_registry is None:
            raise ValueError(
                f"Subagent '{name}' requires sandbox and mcp_registry"
            )
        return create_fn(sandbox=sandbox, mcp_registry=mcp_registry, **filtered_kwargs)

    # Stateless subagent (e.g., research)
    return create_fn(**filtered_kwargs)


def create_subagents_from_names(
    names: list[str],
    sandbox: Any | None = None,
    mcp_registry: Any | None = None,
    counter_middleware: Any | None = None,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Create multiple subagents from a list of names.

    Args:
        names: List of subagent names to create
        sandbox: PTCSandbox instance (required for stateful subagents)
        mcp_registry: MCPRegistry instance (required for stateful subagents)
        counter_middleware: Optional ToolCallCounterMiddleware to inject into
            subagents for tracking tool calls. Used for background execution
            progress monitoring.
        **kwargs: Additional arguments passed to all subagent creation functions

    Returns:
        List of configured subagent dictionaries
    """
    subagents = []
    for name in names:
        spec = create_subagent_by_name(name, sandbox, mcp_registry, **kwargs)

        # Inject counter middleware if provided
        if counter_middleware is not None:
            existing_middleware = spec.get("middleware", [])
            spec["middleware"] = [counter_middleware, *list(existing_middleware)]

        subagents.append(spec)

    return subagents


__all__ = [
    "SUBAGENT_REGISTRY",
    "create_general_subagent",
    "create_research_subagent",
    "create_subagent_by_name",
    "create_subagents_from_names",
    "get_general_subagent_config",
    "get_research_subagent_config",
]
