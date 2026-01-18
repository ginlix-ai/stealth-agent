"""Dynamic prompt middleware for LangChain agents.

This module provides middleware for dynamically generating system prompts
based on agent state and context.
"""
from typing import Annotated, Optional, Any
from typing_extensions import NotRequired

from langchain.agents.middleware import dynamic_prompt, ModelRequest, AgentState

from src.prompts import render_system_prompt
from src.tools.core.filesystem import _file_operations_log_reducer


class PromptMiddlewareState(AgentState):
    """State schema for dynamic prompt middleware.

    Declares fields that prompt rendering needs to access from graph state.
    All fields are NotRequired since they may not be present in all workflows.

    This state schema is automatically merged with other middleware state schemas
    by LangChain's create_agent() function, making these fields accessible in
    request.state during middleware execution.

    Fields:
        prompt_context: Grouped localization and time-awareness fields
            - inquiry_timestamp: Timestamp when query was received
            - timezone_str: Timezone name (e.g., "America/New_York")
            - locale: User's locale (e.g., "en-US", "zh-CN")
            - prompt_language: Language code (e.g., "en", "zh")
            - is_follow_up: Follow-up conversation flag (True when restoring from previous thread)
        market_type: Market classification (e.g., "A_SHARE", "US_STOCK", "HK_STOCK") for data_agent
        tool_guidance: Dynamic tool guidance based on market type for data_agent
        current_plan: Current research plan (for USER_QUERY extraction in prompts)
        file_operations_log: Persistent audit trail of all file operations during workflow execution
    """
    prompt_context: NotRequired[dict] = {}
    market_type: NotRequired[Optional[str]] = None
    tool_guidance: NotRequired[Optional[str]] = None
    current_plan: NotRequired[Optional[Any]] = None
    file_operations_log: Annotated[NotRequired[list[dict[str, Any]]], _file_operations_log_reducer]


def map_prompt_language_context(state, context):
    """Map prompt language and locale from prompt_context to context."""
    ctx = dict(context or {})  # copy
    prompt_ctx = state.get("prompt_context", {})
    if "prompt_language" not in ctx and "prompt_language" in prompt_ctx:
        ctx["prompt_language"] = prompt_ctx["prompt_language"]
    if "locale" not in ctx and "locale" in prompt_ctx:
        ctx["locale"] = prompt_ctx["locale"]
    return ctx


def DynamicPromptMiddleware(prompt_template: str, context: dict, agent_type: str):
    """Factory function that creates a dynamic prompt middleware.

    Named in PascalCase for consistency with other middleware classes.

    This creates a decorated function with an attached state_schema. The state_schema
    declares fields that prompt rendering needs (inquiry_timestamp, locale, etc.).
    LangChain's create_agent() automatically merges state schemas from all middleware,
    making these fields accessible in request.state during prompt rendering.

    Args:
        prompt_template: Path to the prompt template
        context: Base context for template rendering
        agent_type: Type of agent (for special handling like data_agent)

    Returns:
        A @dynamic_prompt decorated function with state_schema attribute
    """
    @dynamic_prompt
    def prompt_middleware(request: ModelRequest) -> str:
        """Generate system prompt based on current state."""
        state = request.state

        # Start with the base context
        dynamic_context = dict(context or {})
        dynamic_context = map_prompt_language_context(state, dynamic_context)

        # Special handling for data_agent that needs extra state fields
        if agent_type == "deep_research/data_agent":
            # Also check if these are in the state (from agent_input)
            if "tool_guidance" in state and "tool_guidance" not in dynamic_context:
                dynamic_context["tool_guidance"] = state["tool_guidance"]
            if "market_type" in state and "market_type" not in dynamic_context:
                dynamic_context["market_type"] = state["market_type"]

        # Extract is_follow_up from prompt_context (needed for conditional prompt includes)
        prompt_ctx = state.get("prompt_context", {})
        if "is_follow_up" in prompt_ctx and "is_follow_up" not in dynamic_context:
            dynamic_context["is_follow_up"] = prompt_ctx["is_follow_up"]

        # Directly return rendered system prompt string (v1 pattern)
        return render_system_prompt(prompt_template, state, extra_context=dynamic_context)

    # Attach state_schema to the function so LangChain can merge it with other middleware schemas
    # This follows the pattern used by FilesystemMiddleware and FileOperationMiddleware
    prompt_middleware.state_schema = PromptMiddlewareState

    return prompt_middleware
