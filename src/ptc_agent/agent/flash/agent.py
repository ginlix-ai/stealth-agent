"""Flash Agent - Minimal agent without sandbox dependencies.

Optimized for fast responses using external tools only (web search, market data,
SEC filings). No code execution, no sandbox, no MCP tools.
"""

from typing import Any

import structlog
from langchain.agents import create_agent
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware

from ptc_agent.agent.middleware import (
    ToolArgumentParsingMiddleware,
    ToolErrorHandlingMiddleware,
    ToolResultNormalizationMiddleware,
    SummarizationMiddleware,
    DynamicSkillLoaderMiddleware,
    AskUserMiddleware,
)
from ptc_agent.agent.prompts import get_loader
from ptc_agent.config import AgentConfig

# External tools only (no sandbox, no MCP)
from src.tools.search import get_web_search_tool
from src.tools.fetch import web_fetch_tool
from src.tools.sec.tool import get_sec_filing
from src.tools.market_data.tool import (
    get_stock_daily_prices,
    get_company_overview,
    get_market_indices,
    get_sector_performance,
)

logger = structlog.get_logger(__name__)


class FlashAgent:
    """Lightweight agent for fast responses without sandbox.

    Features:
    - No sandbox startup latency (~0.5s vs ~8-10s)
    - Minimal system prompt (~300 tokens vs ~2000 tokens)
    - External tools only (web search, market data, SEC filings)
    - No code execution capabilities
    - No MCP tool access

    Use cases:
    - Quick market data lookups
    - News and web searches
    - SEC filing queries
    - Simple Q&A that doesn't require code execution
    """

    def __init__(self, config: AgentConfig) -> None:
        """Initialize Flash agent.

        Args:
            config: Agent configuration (uses flash settings and LLM config)
        """
        self.config = config

        # Use flash-specific LLM if configured, otherwise fall back to main LLM
        if config.llm.flash:
            # If an llm_client was pre-created (e.g. OAuth/BYOK), use it directly
            if config.llm_client is not None:
                self.llm: Any = config.llm_client
            else:
                from src.llms import create_llm
                self.llm = create_llm(config.llm.flash)
            model = config.llm.flash
            provider = "llm_config"
        else:
            self.llm = config.get_llm_client()
            # Get provider/model info for logging
            if config.llm_definition is not None:
                provider = config.llm_definition.provider
                model = config.llm_definition.model_id
            else:
                provider = getattr(self.llm, "_llm_type", "unknown")
                model = getattr(
                    self.llm, "model", getattr(self.llm, "model_name", "unknown")
                )

        logger.info(
            "Initialized FlashAgent",
            provider=provider,
            model=model,
        )

    def _build_tools(self) -> list[Any]:
        """Build the tool list for Flash agent.

        Returns:
            List of external tools (no sandbox/MCP tools)
        """
        tools: list[Any] = []

        # Web search tool (uses configured search engine)
        web_search_tool = get_web_search_tool(
            max_search_results=10,
            time_range=None,
            verbose=False,
        )
        tools.append(web_search_tool)
        tools.append(web_fetch_tool)

        # Finance tools
        tools.extend(
            [
                get_sec_filing,
                get_stock_daily_prices,
                get_company_overview,
                get_market_indices,
                get_sector_performance,
            ]
        )

        return tools

    def _build_system_prompt(self, tools: list[Any]) -> str:
        """Build minimal system prompt for Flash agent.

        Args:
            tools: List of available tools

        Returns:
            Minimal system prompt string
        """
        loader = get_loader()
        return loader.render("flash_system.md.j2", tools=tools)

    def create_agent(
        self,
        checkpointer: Any | None = None,
        llm: Any | None = None,
    ) -> Any:
        """Create a Flash agent with minimal middleware stack.

        Note: No MCP registry, no sandbox - MCP tools require sandbox.

        Args:
            checkpointer: Optional LangGraph checkpointer for state persistence
            llm: Optional LLM override

        Returns:
            Configured LangGraph agent
        """
        model = llm if llm is not None else self.llm

        # Build tools
        tools = self._build_tools()

        # Build system prompt
        system_prompt = self._build_system_prompt(tools)

        # Minimal shared middleware stack
        shared_middleware: list[Any] = [
            ToolArgumentParsingMiddleware(),
            ToolErrorHandlingMiddleware(),
            ToolResultNormalizationMiddleware(),
        ]

        # Add dynamic skill loader middleware (Flash mode: inline SKILL.md)
        skill_loader_middleware = DynamicSkillLoaderMiddleware(
            mode="flash",
        )
        shared_middleware.append(skill_loader_middleware)
        tools.extend(skill_loader_middleware.tools)  # LoadSkill tool
        tools.extend(skill_loader_middleware.get_all_skill_tools())  # Pre-register skill tools
        logger.info(
            "Flash skill loader enabled",
            skill_count=len(skill_loader_middleware.skill_registry),
            skill_tool_count=len(skill_loader_middleware.get_all_skill_tools()),
        )

        # Main middleware stack (minimal)
        main_middleware: list[Any] = []

        # AskUserQuestion middleware (needed for onboarding and preference updates)
        ask_user_middleware = AskUserMiddleware()
        main_middleware.append(ask_user_middleware)
        tools.extend(ask_user_middleware.tools)
        logger.info("AskUserQuestion tool enabled for Flash agent")

        # Optional summarization (shares config with main agent)
        from src.config.settings import get_summarization_config

        summarization_config = get_summarization_config()
        if summarization_config.get("enabled", True):
            main_middleware.append(SummarizationMiddleware())
            logger.info(
                "Summarization enabled",
                threshold=summarization_config.get("token_threshold", 120000),
            )

        # Prompt caching and tool call patching
        main_middleware.extend(
            [
                AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
                PatchToolCallsMiddleware(),
            ]
        )

        # Build final middleware stack
        middleware = [*shared_middleware, *main_middleware]

        logger.info(
            "Creating Flash agent",
            tool_count=len(tools),
            middleware_count=len(middleware),
        )

        # Create agent
        agent = create_agent(
            model,
            system_prompt=system_prompt,
            tools=tools,
            middleware=middleware,
            checkpointer=checkpointer,
        ).with_config({"recursion_limit": 100})

        return agent
