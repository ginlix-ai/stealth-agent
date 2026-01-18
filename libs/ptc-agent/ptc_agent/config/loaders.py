"""Configuration loaders for file-based config.

This module provides functions to load AgentConfig and CoreConfig from files.

Usage:
    # File-based loading (CLI, LangGraph)
    from ptc_agent.config import load_from_files
    config = await load_from_files()

Config Search Paths:
    When no explicit path is provided, files are searched in order:
    1. Current working directory
    2. Project root (git repository root)
    3. ~/.ptc-agent/ (user config directory)

    Environment variable overrides:
    - PTC_CONFIG_FILE: explicit path to config.yaml
    - PTC_LLMS_FILE: explicit path to llms.json
"""

import asyncio
import json
import os
from enum import Enum
from pathlib import Path
from typing import Any

import aiofiles

from ptc_agent.config.agent import AgentConfig, LLMConfig, LLMDefinition, SkillsConfig
from ptc_agent.config.core import CoreConfig
from ptc_agent.config.utils import (
    configure_logging,
    create_daytona_config,
    create_filesystem_config,
    create_logging_config,
    create_mcp_config,
    create_security_config,
    load_dotenv_async,
    load_yaml_file,
    validate_required_sections,
)


class ConfigContext(str, Enum):
    """Context for configuration loading behavior."""

    SDK = "sdk"  # CWD → git root → ~/.ptc-agent/
    CLI = "cli"  # ~/.ptc-agent/ → CWD (home first)

# =============================================================================
# Config Path Utilities
# =============================================================================


def get_default_config_dir() -> Path:
    """Get the default config directory (~/.ptc-agent/).

    Returns:
        Path to the user's config directory
    """
    return Path.home() / ".ptc-agent"


def find_project_root(start_path: Path | None = None) -> Path | None:
    """Find git repository root by walking up from start_path.

    Args:
        start_path: Starting directory (default: current working directory)

    Returns:
        Path to project root if found, None otherwise
    """
    current = start_path or Path.cwd()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return None


def get_config_search_paths(
    start_path: Path | None = None,
    context: ConfigContext = ConfigContext.SDK,
) -> list[Path]:
    """Get ordered list of config search paths.

    Search order depends on context:
    - SDK: CWD → git root → ~/.ptc-agent/
    - CLI: ~/.ptc-agent/ → CWD (home first)

    Args:
        start_path: Starting directory (default: current working directory)
        context: Loading context (SDK or CLI)

    Returns:
        List of paths to search for config files
    """
    cwd = start_path or Path.cwd()
    home = get_default_config_dir()

    if context == ConfigContext.CLI:
        return [home, cwd]

    # SDK: existing behavior
    paths = [cwd]
    project_root = find_project_root(cwd)
    if project_root and project_root != cwd:
        paths.append(project_root)
    paths.append(home)
    return paths


def find_config_file(
    filename: str,
    search_paths: list[Path] | None = None,
    env_var: str | None = None,
    context: ConfigContext = ConfigContext.SDK,
) -> Path | None:
    """Find first existing config file in search paths.

    Args:
        filename: Name of the file to find (e.g., "config.yaml")
        search_paths: Paths to search (default: get_config_search_paths())
        env_var: Environment variable to check for override
        context: Loading context (SDK or CLI)

    Returns:
        Path to the first existing file, or None if not found
    """
    # Check env var override first
    if env_var:
        env_path = os.getenv(env_var)
        if env_path:
            path = Path(env_path)
            if path.exists():
                return path

    # Search paths in order
    if search_paths is None:
        search_paths = get_config_search_paths(context=context)

    for search_path in search_paths:
        candidate = search_path / filename
        if candidate.exists():
            return candidate

    return None


def ensure_config_dir() -> Path:
    """Ensure ~/.ptc-agent/ exists and return path.

    Returns:
        Path to the config directory
    """
    config_dir = get_default_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


async def load_from_files(
    config_file: Path | None = None,
    llms_file: Path | None = None,
    env_file: Path | None = None,
    *,
    search_paths: bool = True,
    context: ConfigContext = ConfigContext.SDK,
    auto_generate: bool = False,
) -> AgentConfig:
    """Load AgentConfig from config files (config.yaml, llms.json, .env).

    Search order depends on context:
    - SDK: CWD → git root → ~/.ptc-agent/
    - CLI: ~/.ptc-agent/ → CWD (home first)

    Environment variable overrides:
    - PTC_CONFIG_FILE: explicit path to config.yaml
    - PTC_LLMS_FILE: explicit path to llms.json

    Args:
        config_file: Optional path to config.yaml file
        llms_file: Optional path to llms.json file (can be None to skip)
        env_file: Optional path to .env file
        search_paths: If True, search multiple paths for config files
        context: Loading context (SDK or CLI)
        auto_generate: If True, generate config at ~/.ptc-agent/ when not found

    Returns:
        Configured AgentConfig instance

    Raises:
        FileNotFoundError: If config.yaml is not found
        ValueError: If required configuration is missing or invalid
        KeyError: If required fields are missing from config files
    """
    cwd = await asyncio.to_thread(Path.cwd)

    # Find config.yaml
    if config_file is None:
        if search_paths:
            config_file = await asyncio.to_thread(
                find_config_file, "config.yaml", None, "PTC_CONFIG_FILE", context
            )
        else:
            config_file = cwd / "config.yaml"

    # Auto-generate if missing and requested
    if (config_file is None or not config_file.exists()) and auto_generate:
        generated = generate_config_template(get_default_config_dir(), include_llms=False)
        config_file = generated["config.yaml"]

    if config_file is None or not config_file.exists():
        searched = (
            await asyncio.to_thread(get_config_search_paths, None, context)
            if search_paths
            else [cwd]
        )
        raise FileNotFoundError(
            f"config.yaml not found in search paths:\n"
            f"  {chr(10).join(str(p) for p in searched)}\n"
            f"Create one or set PTC_CONFIG_FILE environment variable."
        )

    # Find llms.json (optional - can be None if using inline LLM definition)
    llm_catalog = None
    if llms_file is None:
        if search_paths:
            llms_file = await asyncio.to_thread(
                find_config_file, "llms.json", None, "PTC_LLMS_FILE", context
            )
        else:
            candidate = cwd / "llms.json"
            if candidate.exists():
                llms_file = candidate

    # Load llms.json if found
    if llms_file is not None and llms_file.exists():
        llm_catalog = await _load_llm_catalog(llms_file)

    # Load environment variables for credentials
    await load_dotenv_async(env_file)

    # Load config.yaml asynchronously
    config_data = await load_yaml_file(config_file)

    # Create config from dict
    config = load_from_dict(config_data, llm_catalog)

    # Store config file directory for path resolution
    config.config_file_dir = config_file.parent if config_file else None

    return config


async def load_core_from_files(
    config_file: Path | None = None,
    env_file: Path | None = None,
    *,
    search_paths: bool = True,
    context: ConfigContext = ConfigContext.SDK,
) -> CoreConfig:
    """Load CoreConfig from config files (config.yaml, .env).

    Search order depends on context:
    - SDK: CWD → git root → ~/.ptc-agent/
    - CLI: ~/.ptc-agent/ → CWD (home first)

    Args:
        config_file: Optional path to config.yaml file
        env_file: Optional path to .env file
        search_paths: If True, search multiple paths for config files
        context: Loading context (SDK or CLI)

    Returns:
        Configured CoreConfig instance

    Raises:
        FileNotFoundError: If config.yaml is not found
        ValueError: If required configuration is missing or invalid
        KeyError: If required fields are missing from config files
    """
    cwd = await asyncio.to_thread(Path.cwd)

    # Find config.yaml
    if config_file is None:
        if search_paths:
            config_file = await asyncio.to_thread(
                find_config_file, "config.yaml", None, "PTC_CONFIG_FILE", context
            )
        else:
            config_file = cwd / "config.yaml"

    if config_file is None or not config_file.exists():
        searched = (
            await asyncio.to_thread(get_config_search_paths, None, context)
            if search_paths
            else [cwd]
        )
        raise FileNotFoundError(
            f"config.yaml not found in search paths:\n"
            f"  {chr(10).join(str(p) for p in searched)}\n"
            f"Create one or set PTC_CONFIG_FILE environment variable."
        )

    # Load environment variables for credentials
    await load_dotenv_async(env_file)

    # Load config.yaml asynchronously
    config_data = await load_yaml_file(config_file)

    # Validate that all required sections exist in config.yaml
    required_sections = ["daytona", "security", "mcp", "logging", "filesystem"]
    validate_required_sections(config_data, required_sections)

    # Load configurations using shared factory functions
    daytona_config = create_daytona_config(config_data["daytona"])
    security_config = create_security_config(config_data["security"])
    mcp_config = create_mcp_config(config_data["mcp"])
    logging_config = create_logging_config(config_data["logging"])
    filesystem_config = create_filesystem_config(config_data["filesystem"])

    # Create config object
    core_config = CoreConfig(
        daytona=daytona_config,
        security=security_config,
        mcp=mcp_config,
        logging=logging_config,
        filesystem=filesystem_config,
    )

    # Store config file directory for path resolution
    core_config.config_file_dir = config_file.parent if config_file else None

    return core_config


def load_from_dict(
    config_data: dict[str, Any],
    llm_catalog: dict[str, LLMDefinition] | None = None,
) -> AgentConfig:
    """Create AgentConfig from a dictionary (e.g., parsed YAML).

    This allows creating config from any dict source, not just files.

    LLM can be specified in two ways:
    1. Reference to llms.json: {"name": "claude-sonnet-4-5"}
    2. Inline definition: {"name": "custom", "model_id": "...", "sdk": "...", ...}

    When model_id is present in the llm section, it's treated as an inline
    definition and llms.json is not required.

    Args:
        config_data: Configuration dictionary (same structure as config.yaml)
        llm_catalog: Optional LLM catalog dict. If provided, LLM name is looked up
                     from this catalog. Ignored if llm section has inline definition.

    Returns:
        Configured AgentConfig instance

    Raises:
        ValueError: If required configuration is missing or invalid
    """
    # Validate that all required sections exist
    required_sections = ["llm", "daytona", "security", "mcp", "logging", "filesystem"]
    validate_required_sections(config_data, required_sections)

    # Load LLM configuration
    llm_data = config_data["llm"]
    llm_definition = None
    llm_name = "custom"

    # Handle different formats
    if isinstance(llm_data, str):
        # Simple string format: "claude-sonnet-4-5"
        llm_name = llm_data
    elif isinstance(llm_data, dict):
        llm_name = llm_data.get("name", "custom")

        # Check if this is an inline definition (has model_id)
        if "model_id" in llm_data:
            # Inline LLM definition - no catalog lookup needed
            llm_definition = LLMDefinition(
                model_id=llm_data["model_id"],
                provider=llm_data.get("provider", "anthropic"),
                sdk=llm_data.get("sdk", "langchain_anthropic.ChatAnthropic"),
                api_key_env=llm_data.get("api_key_env", "LLM_API_KEY"),
                base_url=llm_data.get("base_url"),
                output_version=llm_data.get("output_version"),
                use_previous_response_id=llm_data.get("use_previous_response_id", False),
                parameters=llm_data.get("parameters", {}),
            )
    else:
        raise ValueError(
            "llm section must be either a string (LLM name) or dict"
        )

    # Look up LLM definition from catalog if not inline and catalog provided
    if llm_definition is None and llm_catalog is not None:
        if llm_name not in llm_catalog:
            available = ", ".join(llm_catalog.keys())
            raise ValueError(
                f"LLM '{llm_name}' not found in llm_catalog.\n"
                f"Available LLMs: {available}\n"
                f"Or define inline: llm.model_id, llm.sdk, llm.api_key_env"
            )
        llm_definition = llm_catalog[llm_name]
    elif llm_definition is None and llm_catalog is None:
        raise ValueError(
            f"LLM '{llm_name}' cannot be resolved: no llms.json found and "
            f"no inline definition provided.\n"
            f"Either provide llms.json or define inline with model_id, sdk, api_key_env."
        )

    # Create LLM config
    llm_config = LLMConfig(name=llm_name)

    # Load configurations using shared factory functions
    daytona_config = create_daytona_config(config_data["daytona"])
    security_config = create_security_config(config_data["security"])
    mcp_config = create_mcp_config(config_data["mcp"])
    logging_config = create_logging_config(config_data["logging"])
    filesystem_config = create_filesystem_config(config_data["filesystem"])

    # Configure structlog to respect the log level from config
    configure_logging(logging_config.level)

    # Load Agent configuration (optional section)
    agent_data = config_data.get("agent", {})
    use_custom_filesystem_tools = agent_data.get("use_custom_filesystem_tools", True)
    enable_view_image = agent_data.get("enable_view_image", True)
    background_auto_wait = agent_data.get("background_auto_wait", False)

    # Load Subagent configuration (optional section)
    subagents_data = config_data.get("subagents", {})
    subagents_enabled = subagents_data.get("enabled", ["general-purpose"])

    # Load Skills configuration (optional section)
    skills_data = config_data.get("skills", {})
    skills_config = SkillsConfig(
        enabled=skills_data.get("enabled", True),
        user_skills_dir=skills_data.get("user_skills_dir", "~/.ptc-agent/skills"),
        project_skills_dir=skills_data.get("project_skills_dir", ".ptc-agent/skills"),
        sandbox_skills_base=skills_data.get("sandbox_skills_base", "/home/daytona/skills"),
    )

    # Create config object
    config = AgentConfig(
        llm=llm_config,
        security=security_config,
        logging=logging_config,
        daytona=daytona_config,
        mcp=mcp_config,
        filesystem=filesystem_config,
        skills=skills_config,
        use_custom_filesystem_tools=use_custom_filesystem_tools,
        enable_view_image=enable_view_image,
        subagents_enabled=subagents_enabled,
        background_auto_wait=background_auto_wait,
    )

    # Store runtime data if available
    if llm_definition is not None:
        config.llm_definition = llm_definition

    return config


async def _load_llm_catalog(llms_file: Path) -> dict[str, LLMDefinition]:
    """Load LLM catalog from llms.json file.

    Args:
        llms_file: Path to llms.json file

    Returns:
        Dictionary mapping LLM names to LLMDefinition objects

    Raises:
        FileNotFoundError: If llms.json is not found
        ValueError: If JSON parsing fails or format is invalid
    """
    if not llms_file.exists():
        raise FileNotFoundError(
            f"LLM catalog not found: {llms_file}\n"
            f"Please create llms.json with LLM definitions."
        )

    try:
        async with aiofiles.open(llms_file) as f:
            llms_content = await f.read()
        llms_data = json.loads(llms_content)
    except json.JSONDecodeError as e:
        msg = f"Failed to parse llms.json: {e}"
        raise ValueError(msg) from e

    if "llms" not in llms_data:
        raise ValueError(
            "llms.json must have 'llms' key containing LLM definitions."
        )

    return {
        name: LLMDefinition(**definition)
        for name, definition in llms_data["llms"].items()
    }


async def load_llm_catalog(llms_file: Path | None = None) -> dict[str, LLMDefinition]:
    """Load LLM catalog from llms.json file (public API).

    Args:
        llms_file: Optional path to llms.json file (default: searches paths)

    Returns:
        Dictionary mapping LLM names to LLMDefinition objects
    """
    if llms_file is None:
        llms_file = await asyncio.to_thread(
            find_config_file, "llms.json", None, "PTC_LLMS_FILE"
        )
        if llms_file is None:
            cwd = await asyncio.to_thread(Path.cwd)
            llms_file = cwd / "llms.json"

    return await _load_llm_catalog(llms_file)


# =============================================================================
# Config Template Generation
# =============================================================================


CONFIG_TEMPLATE = """# PTC Agent Configuration
# Place this file in ~/.ptc-agent/config.yaml or your project root

# CLI Configuration (for ptc-cli)
# --------------------------------
cli:
  theme: "auto"  # auto, dark, light
  # palette: "nord"  # emerald, cyan, amber, teal, nord, gruvbox, catppuccin, tokyo_night

# LLM Configuration
# -----------------
# Option 1: Reference llms.json by name
llm:
  name: "claude-sonnet-4-5"

# Option 2: Inline definition (uncomment and modify)
# llm:
#   name: "custom"
#   model_id: "claude-sonnet-4-20250514"
#   provider: "anthropic"
#   sdk: "langchain_anthropic.ChatAnthropic"
#   api_key_env: "ANTHROPIC_API_KEY"
#   parameters:
#     max_tokens: 4096

# Daytona Sandbox
# ---------------
daytona:
  base_url: "https://app.daytona.io/api"
  # api_key: set DAYTONA_API_KEY in environment or .env file
  python_version: "3.12"
  auto_stop_interval: 3600  # 1 hour

# MCP Servers (optional)
# ----------------------
mcp:
  servers: []
  # Example:
  # - name: "tavily"
  #   description: "Web search capabilities"
  #   command: "npx"
  #   args: ["-y", "tavily-mcp@latest"]
  #   env:
  #     TAVILY_API_KEY: "${TAVILY_API_KEY}"
  tool_discovery_enabled: true
  lazy_load: true

# Security Settings
# -----------------
security:
  max_execution_time: 300  # 5 minutes
  max_code_length: 10000
  max_file_size: 10485760
  enable_code_validation: true
  allowed_imports:
    - os
    - sys
    - json
  blocked_patterns:
    - "eval("
    - "exec("

# Logging
# -------
logging:
  level: "INFO"
  file: "logs/ptc.log"

# Filesystem
# ----------
filesystem:
  working_directory: "/home/daytona"
  allowed_directories:
    - "/home/daytona"
    - "/tmp"
  enable_path_validation: true

# Agent Settings (optional)
# -------------------------
agent:
  use_custom_filesystem_tools: true
  enable_view_image: true
  background_auto_wait: false  # true to wait for background tasks before returning to CLI

# Subagents (optional)
# --------------------
subagents:
  enabled:
    - "general-purpose"
    # - "research"
"""

LLMS_TEMPLATE = """{
  "llms": {
    "claude-sonnet-4-5": {
      "model_id": "claude-sonnet-4-5-20250929",
      "provider": "anthropic",
      "sdk": "langchain_anthropic.ChatAnthropic",
      "api_key_env": "ANTHROPIC_API_KEY"
    },
    "gpt-5.1": {
      "model_id": "gpt-5.1",
      "provider": "openai",
      "sdk": "langchain_openai.ChatOpenAI",
      "api_key_env": "OPENAI_API_KEY"
    }
  }
}
"""


def generate_config_template(
    output_dir: Path,
    *,
    include_llms: bool = True,
    overwrite: bool = False,
) -> dict[str, Path]:
    """Generate config.yaml and optionally llms.json templates.

    This is useful for CLI 'config init' commands or first-run setup.

    Args:
        output_dir: Directory to write config files
        include_llms: Whether to generate llms.json template
        overwrite: Whether to overwrite existing files

    Returns:
        Dict mapping filename to path of created file

    Raises:
        FileExistsError: If file exists and overwrite is False
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    created = {}

    # Write config.yaml
    config_path = output_dir / "config.yaml"
    if config_path.exists() and not overwrite:
        msg = f"Config file already exists: {config_path}"
        raise FileExistsError(msg)
    config_path.write_text(CONFIG_TEMPLATE)
    created["config.yaml"] = config_path

    # Write llms.json if requested
    if include_llms:
        llms_path = output_dir / "llms.json"
        if llms_path.exists() and not overwrite:
            msg = f"LLMs file already exists: {llms_path}"
            raise FileExistsError(msg)
        llms_path.write_text(LLMS_TEMPLATE)
        created["llms.json"] = llms_path

    return created
