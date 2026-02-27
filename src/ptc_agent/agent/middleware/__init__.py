"""Agent middleware components.

This module provides middleware for LangChain/LangGraph agents:

- background/: Background subagent orchestration
- plan_mode: Human-in-the-loop plan review
- tool/: Tool argument parsing, error handling, result normalization
- caching/: Tool result caching with SSE events
- file_operations/: File operation SSE event emission and vision middleware
- summarization/: SSE-enabled summarization
"""

# Background subagent middleware
from ptc_agent.agent.middleware.background_subagent import (
    BackgroundSubagentMiddleware,
    BackgroundSubagentOrchestrator,
    ToolCallCounterMiddleware,
)

# Plan mode middleware
from ptc_agent.agent.middleware.plan_mode import (
    PlanModeMiddleware,
    create_plan_mode_interrupt_config,
)

# Ask user middleware
from ptc_agent.agent.middleware.ask_user import AskUserMiddleware

# Tool middleware (argument parsing, error handling, result normalization)
from ptc_agent.agent.middleware.tool import (
    ToolArgumentParsingMiddleware,
    ToolErrorHandlingMiddleware,
    ToolResultNormalizationMiddleware,
    simplify_tool_error,
)

# Caching middleware
from ptc_agent.agent.middleware.caching import (
    ToolResultCacheMiddleware,
    ToolResultCacheState,
)

# File operations middleware (includes MultimodalMiddleware for images/PDFs)
from ptc_agent.agent.middleware.file_operations import (
    FileOperationMiddleware,
    FileOperationState,
    MultimodalMiddleware,
)

# Todo operations middleware
from ptc_agent.agent.middleware.todo_operations import (
    TodoWriteMiddleware,
)

# Summarization middleware
from ptc_agent.agent.middleware.summarization import (
    SummarizationMiddleware,
    DEFAULT_SUMMARY_PROMPT,
    count_tokens_tiktoken,
)

# Skills middleware (registry + dynamic loader)
from ptc_agent.agent.middleware.skills import (
    SkillsMiddleware,
)

# Large result eviction middleware
from ptc_agent.agent.middleware.large_result_eviction import (
    LargeResultEvictionMiddleware,
)

# Message queue middleware
from ptc_agent.agent.middleware.message_queue import (
    MessageQueueMiddleware,
)

# Workspace context middleware (agent.md injection)
from ptc_agent.agent.middleware.workspace_context import (
    WorkspaceContextMiddleware,
)

# Subagent message queue middleware
from ptc_agent.agent.middleware.background_subagent.queue import (
    SubagentMessageQueueMiddleware,
)

# Subagent middleware
from ptc_agent.agent.middleware.background_subagent.subagent import (
    CompiledSubAgent,
    SubAgent,
    SubAgentMiddleware,
)

__all__ = [
    # Background subagent
    "BackgroundSubagentMiddleware",
    "BackgroundSubagentOrchestrator",
    "ToolCallCounterMiddleware",
    # Plan mode
    "PlanModeMiddleware",
    "create_plan_mode_interrupt_config",
    # Ask user
    "AskUserMiddleware",
    # Multimodal middleware (for read_file image/PDF support)
    "MultimodalMiddleware",
    # Tool middleware
    "ToolArgumentParsingMiddleware",
    "ToolErrorHandlingMiddleware",
    "ToolResultNormalizationMiddleware",
    "simplify_tool_error",
    # Caching
    "ToolResultCacheMiddleware",
    "ToolResultCacheState",
    # File operations
    "FileOperationMiddleware",
    "FileOperationState",
    # Todo operations
    "TodoWriteMiddleware",
    # Summarization
    "SummarizationMiddleware",
    "DEFAULT_SUMMARY_PROMPT",
    "count_tokens_tiktoken",
    # Skills
    "SkillsMiddleware",
    # Large result eviction
    "LargeResultEvictionMiddleware",
    # Message queue
    "MessageQueueMiddleware",
    # Subagent message queue
    "SubagentMessageQueueMiddleware",
    # Workspace context
    "WorkspaceContextMiddleware",
    # Subagent middleware
    "CompiledSubAgent",
    "SubAgent",
    "SubAgentMiddleware",
]
