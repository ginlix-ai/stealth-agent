"""Agent package - AI agent implementations using deepagent.

This package provides the PTC (Programmatic Tool Calling) agent pattern:
- Uses deepagent for orchestration and sub-agent delegation
- Integrates Daytona sandbox via DaytonaBackend
- MCP tools accessed through execute_code tool

Structure:
- agent.py: Main PTCAgent using deepagent
- backends/: Custom backends (DaytonaBackend)
- prompts/: Prompt templates (base, research)
- tools/: Custom tools (execute_code, research)
- langchain_tools/: LangChain @tool implementations (Bash, Read, Write, Edit, Glob, Grep)
- subagents/: Sub-agent definitions

Configuration:
- All config classes in ptc_agent.config package
- Programmatic (default): Create AgentConfig directly or use AgentConfig.create()
- File-based: Use load_from_files() from ptc_agent.config
"""

# Re-export from ptc_agent.config for backward compatibility
from ptc_agent.config import (
    # Config classes (pure data)
    AgentConfig,
    LLMConfig,
    LLMDefinition,
    # Utilities
    configure_logging,
    ensure_config_dir,
    find_config_file,
    find_project_root,
    # Template generation
    generate_config_template,
    get_config_search_paths,
    # Config path utilities
    get_default_config_dir,
    load_core_from_files,
    load_from_dict,
    # Config loading
    load_from_files,
)

from .agent import PTCAgent
from .backends import DaytonaBackend
from .graph import SessionProvider, build_ptc_graph, build_ptc_graph_with_session
from .subagents import SubagentCompiler, SubagentDefinition, SubagentRegistry

__all__ = [
    # Config classes (pure data)
    "AgentConfig",
    "DaytonaBackend",
    "LLMConfig",
    "LLMDefinition",
    # Agent
    "PTCAgent",
    # Graph factory
    "SessionProvider",
    "build_ptc_graph",
    "build_ptc_graph_with_session",
    # Utilities
    "configure_logging",
    "SubagentCompiler",
    "SubagentDefinition",
    "SubagentRegistry",
    "ensure_config_dir",
    "find_config_file",
    "find_project_root",
    # Template generation
    "generate_config_template",
    "get_config_search_paths",
    # Config path utilities
    "get_default_config_dir",
    "load_core_from_files",
    "load_from_dict",
    # Config loaders (optional file-based)
    "load_from_files",
]
