from datetime import datetime
from typing import Optional, Any

from langchain.agents import create_agent
from langchain.agents.middleware import wrap_model_call, ModelFallbackMiddleware, ModelRetryMiddleware, AgentMiddleware
from langchain.agents.structured_output import ToolStrategy
from langchain.messages import AIMessage
from langchain_core.messages import ToolMessage

from src.llms import get_llm_by_type, LLM
from src.config.agents import AGENT_LLM_MAP, get_agent_llm_map
from src.tools.core.filesystem import FilesystemMiddleware
from src.tools.core.file_operation_middleware import FileOperationMiddleware
from src.agents.middleware import (
    SummarizationMiddleware,
    ToolArgumentParsingMiddleware,
    ToolErrorHandlingMiddleware,
    ToolResultNormalizationMiddleware,
    DynamicPromptMiddleware,
    ToolResultCacheMiddleware,
)


# Create agents using configured LLM types
def get_agent(
    agent_name: str,
    agent_type: str,
    tools: list,
    prompt_template: str,
    extra_context: dict = None,
    enable_filesystem: bool = False,
    enable_structured_output_retry: bool = False,
    enable_model_fallback: bool = True,
    fallback_models: list = None,
    agent_llm_map: dict[str, str] | None = None,
    response_format: type = None,
    custom_middleware: list = None,
):
    """Factory function to create agents with consistent configuration.

    Args:
        agent_name: Name of the agent (used for logging)
        agent_type: Type of agent for LLM selection
        tools: List of tools available to the agent
        prompt_template: Path to the prompt template
        extra_context: Optional extra context to pass to the prompt template
        enable_filesystem: Whether to enable filesystem middleware (default: False)
        enable_structured_output_retry: Whether to enable structured output retry middleware (default: False).
            Only enable this for agents that use .with_structured_output(). Most agents use tool-calling and don't need this.
        enable_model_fallback: Whether to enable model fallback middleware (default: False).
            Automatically tries backup models when primary model fails (e.g., provider outages).
        fallback_models: List of fallback model names to try in order (default: ["gpt-4o-mini", "anthropic:claude-3-5-sonnet-20241022"]).
            Used when enable_model_fallback=True.
        agent_llm_map: Optional custom agent-to-LLM mapping (defaults to global AGENT_LLM_MAP)
        response_format: Optional Pydantic model class for structured output.
            When provided, the agent will return validated structured responses using LangChain's native
            ToolStrategy with automatic error handling and retry on validation failures.
            This is the recommended approach for agents that need structured output (replaces .with_structured_output()).
        custom_middleware: Optional list of custom AgentMiddleware instances to add.
            These are inserted BEFORE tool_result_normalizer, so they can intercept raw tool results
            (e.g., lists, dicts) before they're converted to JSON strings.
            Use this for tool-specific middleware like SearchImageMiddleware.

    Returns:
        CompiledStateGraph: A LangChain agent graph ready for invocation
    """
    # Use provided map or fall back to global AGENT_LLM_MAP
    llm_map = agent_llm_map if agent_llm_map is not None else AGENT_LLM_MAP
    model_name = llm_map.get(agent_type, AGENT_LLM_MAP.get(agent_type, "basic"))
    context = dict(extra_context) if extra_context else {}

    # Create dynamic prompt middleware
    prompt_middleware = DynamicPromptMiddleware(prompt_template, context, agent_type)

    # Build middleware list
    middleware = [prompt_middleware]

    # Add tool argument parsing middleware (applies to all agents)
    # This parses JSON string arguments to proper Python types before tool execution
    # Prevents validation errors when LLMs return stringified JSON instead of objects
    tool_arg_parser = ToolArgumentParsingMiddleware()
    middleware.append(tool_arg_parser)

    # Add tool error handling middleware (applies to all agents)
    # This catches tool errors and returns them as messages instead of crashing
    tool_error_middleware = ToolErrorHandlingMiddleware()
    middleware.append(tool_error_middleware)

    # Add tool result normalization middleware (applies to all agents)
    # This ensures all tool results are strings, preventing API errors
    # when tools return lists/dicts (e.g., OpenAI BadRequestError: "Mismatch type string with value array")
    # NOTE: This is added BEFORE custom_middleware in the list, meaning custom_middleware
    # is INNERMOST (closest to tool execution), so they see raw tool results first.
    tool_result_normalizer = ToolResultNormalizationMiddleware()
    middleware.append(tool_result_normalizer)

    # Add custom middleware AFTER tool_result_normalizer (so they are innermost and see raw tool results)
    # In middleware chains, later items in the list are closer to tool execution.
    # This allows middleware like SearchImageMiddleware to intercept list/dict results
    # and return Command objects before normalization converts them to JSON strings.
    if custom_middleware:
        for m in custom_middleware:
            middleware.append(m)

    # Add tool result cache middleware for data_agent and coder (before filesystem middleware)
    # This automatically caches ALL tool results to /data/raw.md with SSE events
    # Merges data retrieval and analysis results into single chronological cache
    # Replaces manual cache file creation shown in prompts
    if enable_filesystem:
        if agent_type in ("deep_research/data_agent", "deep_research/coder"):
            tool_result_cache_middleware = ToolResultCacheMiddleware(
                monitored_tools={
                    # Data agent tools
                    "get_stock_daily_prices",
                    "get_company_overview",
                    "get_stock_realtime_quote",
                    "get_market_indices",
                    "get_sector_performance",
                    "get_sec_filing",  # Includes earnings call transcripts
                    # Coder analyze tools
                    "technical_analyze",
                    "financial_analyze",
                    "dcf_analyze"
                },
                cache_file_path="/data/raw.md",
                agent_types={"deep_research/data_agent", "deep_research/coder"},
                cache_header="# Research Data & Analysis Cache"
            )
            middleware.append(tool_result_cache_middleware)

    # Add summarization middleware (before model fallback/retry)
    # This summarizes conversation history when token count exceeds threshold
    # Runs BEFORE model calls to reduce context size for long conversations
    summarization = SummarizationMiddleware(llm_map=llm_map)
    if summarization:
        middleware.append(summarization)

    # Add model fallback middleware FIRST (outermost)
    # This catches errors AFTER retry is exhausted
    # Middleware execution: Fallback → Retry → Model
    # Error propagation: Model fails → Retry catches (3x) → Fallback catches (switch model)
    if enable_model_fallback:
        # Determine fallback model names
        if fallback_models:
            # Use explicitly provided fallback models
            fallback_names = fallback_models
        else:
            # Use fallback preset from config - get agent-specific fallback model
            fallback_map = get_agent_llm_map("fallback")
            agent_fallback = fallback_map.get(agent_type)

            # Build fallback list: agent-specific fallback + generic cross-provider fallback
            fallback_names = []
            if agent_fallback:
                fallback_names.append(agent_fallback)
            # Add a generic fallback from different provider for redundancy
            fallback_names.append("qwen3-max-preview")

        # Convert model names to BaseChatModel instances
        fallback_instances = [get_llm_by_type(name) for name in fallback_names]
        model_fallback = ModelFallbackMiddleware(*fallback_instances)
        middleware.append(model_fallback)

    # Add model retry middleware SECOND (innermost, closer to model)
    # This retries the SAME model before fallback kicks in
    # Retries on ALL exceptions, then fallback middleware handles persistent failures
    model_retry = ModelRetryMiddleware(
        max_retries=3,
        on_failure="error",  # Re-raise after retries exhausted (let fallback handle it)
        backoff_factor=2.0,
        initial_delay=1.0,
        max_delay=60.0,
        jitter=True,
    )
    middleware.append(model_retry)
    
    # Add filesystem middleware if requested
    if enable_filesystem:
        # Create filesystem middleware with long-term memory disabled
        # Long-term memory requires a store to be available in runtime (runtime.store)
        # Currently the default graph is built without a store, so disable long-term memory
        # Files will still be shared across agents within the same conversation via state
        # Note: system_prompt is None because filesystem instructions are now
        # included in agent prompts via Jinja2 includes (see filesystem_worker.md and filesystem_reporter.md)
        filesystem_middleware = FilesystemMiddleware(
            long_term_memory=False,  # Disable to avoid store requirement
            system_prompt=None,  # Use Jinja2 includes in agent prompts instead
            custom_tool_descriptions=None,  # Use defaults from middleware
            tool_token_limit_before_evict=20000  # Evict large tool results to filesystem
        )
        middleware.append(filesystem_middleware)

        # Add file operation event middleware for real-time SSE streaming
        # This emits custom events (executing/completed/failed) during write_file/edit_file operations
        # Events are streamed via get_stream_writer() and processed by StreamingHandler
        file_operation_middleware = FileOperationMiddleware()
        middleware.append(file_operation_middleware)

    # Create agent with v1 API and middleware
    # If response_format is provided, use ToolStrategy with automatic error handling
    response_format_config = None
    if response_format is not None:
        response_format_config = ToolStrategy(response_format, handle_errors=True)

    return create_agent(
        model=get_llm_by_type(model_name),
        tools=tools,
        middleware=middleware,
        response_format=response_format_config,
    )