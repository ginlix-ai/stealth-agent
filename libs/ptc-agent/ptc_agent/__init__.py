"""PTC Agent - Programmatic Tool Calling for AI agents with MCP.

This package provides:
- Core infrastructure (sandbox, MCP, sessions)
- Agent implementations (PTCAgent, tools, middleware)
- Configuration system
- Utility functions

Quick start:
    from ptc_agent import AgentConfig, PTCAgent
    from ptc_agent.core import SessionManager

    config = AgentConfig.create(llm=your_llm)
    session = SessionManager.get_session("my_session", config.to_core_config())
    await session.initialize()

    agent = PTCAgent(config)
    executor = agent.create_agent(session.sandbox, session.mcp_registry)
"""

__version__ = "0.1.0"

# Re-export commonly used classes for convenience
from ptc_agent.agent import (
    DaytonaBackend,
    PTCAgent,
    PTCExecutor,
    create_ptc_agent,
)
from ptc_agent.config import (
    AgentConfig,
    CoreConfig,
    LLMConfig,
    LLMDefinition,
    load_core_from_files,
    load_from_files,
)
from ptc_agent.core import (
    MCPRegistry,
    MCPToolInfo,
    PTCSandbox,
    Session,
    SessionManager,
)

__all__ = [
    # Config
    "AgentConfig",
    "CoreConfig",
    "DaytonaBackend",
    "LLMConfig",
    "LLMDefinition",
    "MCPRegistry",
    "MCPToolInfo",
    # Agent
    "PTCAgent",
    "PTCExecutor",
    # Core
    "PTCSandbox",
    "Session",
    "SessionManager",
    # Version
    "__version__",
    "create_ptc_agent",
    "load_core_from_files",
    "load_from_files",
]
