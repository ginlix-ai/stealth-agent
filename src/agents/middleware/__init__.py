"""Custom middleware implementations for LangChain agents."""

from src.agents.middleware.summarization import (
    CustomSummarizationMiddleware,
    SummarizationMiddleware,
    DEFAULT_SUMMARY_PROMPT,
)
from src.agents.middleware.tool import (
    ToolArgumentParsingMiddleware,
    ToolErrorHandlingMiddleware,
    ToolResultNormalizationMiddleware,
    simplify_tool_error,
)
from src.agents.middleware.prompt import (
    PromptMiddlewareState,
    DynamicPromptMiddleware,
    map_prompt_language_context,
)
from src.agents.middleware.tool_result_cache import (
    ToolResultCacheMiddleware,
    ToolResultCacheState,
)

__all__ = [
    # Summarization
    "CustomSummarizationMiddleware",
    "SummarizationMiddleware",
    "DEFAULT_SUMMARY_PROMPT",
    # Tool
    "ToolArgumentParsingMiddleware",
    "ToolErrorHandlingMiddleware",
    "ToolResultNormalizationMiddleware",
    "simplify_tool_error",
    # Prompt
    "PromptMiddlewareState",
    "DynamicPromptMiddleware",
    "map_prompt_language_context",
    # Tool Result Cache
    "ToolResultCacheMiddleware",
    "ToolResultCacheState",
]
