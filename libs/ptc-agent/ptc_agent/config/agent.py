"""Agent configuration management.

This module contains pure data classes for agent-specific configuration
that builds on top of the core configuration (sandbox, MCP).

Use src.config.loaders for file-based loading.
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from ptc_agent.config.core import (
    CoreConfig,
    DaytonaConfig,
    FilesystemConfig,
    LoggingConfig,
    MCPConfig,
    MCPServerConfig,
    SecurityConfig,
)

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


class SkillsConfig(BaseModel):
    """Skills configuration for agent capabilities.

    Skills are markdown-based instruction files that extend agent capabilities.
    Each skill is a directory containing a SKILL.md file with YAML frontmatter.

    Resolution and precedence:
    - Skills are sourced from both user and project directories.
    - Project skills override user skills when names conflict.
    """

    enabled: bool = True
    user_skills_dir: str = "~/.ptc-agent/skills"
    project_skills_dir: str = ".ptc-agent/skills"
    sandbox_skills_base: str = "/home/daytona/skills"  # Where skills live in sandbox

    def local_skill_dirs_with_sandbox(self, *, cwd: Path | None = None) -> list[tuple[str, str]]:
        """Return ordered (local_dir, sandbox_dir) sources.

        Precedence is last-wins (later sources override earlier ones). We support
        both a legacy `skills/` project directory and the current `.ptc-agent/skills`
        default.
        """
        base = cwd or Path.cwd()

        user_dir = str(Path(self.user_skills_dir).expanduser())
        project_dir = str((base / self.project_skills_dir).resolve())
        legacy_project_dir = str((base / "skills").resolve())

        sources: list[tuple[str, str]] = [(user_dir, self.sandbox_skills_base)]
        if legacy_project_dir != project_dir:
            sources.append((legacy_project_dir, self.sandbox_skills_base))
        sources.append((project_dir, self.sandbox_skills_base))
        return sources


class LLMDefinition(BaseModel):
    """Definition of an LLM from llms.json catalog."""

    model_id: str
    provider: str
    sdk: str  # e.g., "langchain_anthropic.ChatAnthropic"
    api_key_env: str  # Name of environment variable containing API key
    base_url: str | None = None
    output_version: str | None = None
    use_previous_response_id: bool | None = False # Use only for OpenAI responses api endpoint
    parameters: dict[str, Any] = Field(default_factory=dict)


class LLMConfig(BaseModel):
    """LLM configuration - references an LLM from llms.json."""

    name: str  # Name/alias from llms.json


class AgentConfig(BaseModel):
    """Agent-specific configuration.

    This config contains agent-related settings (LLM, security, logging)
    while using the core config for sandbox and MCP settings.
    """

    # Agent-specific configurations
    llm: LLMConfig
    security: SecurityConfig
    logging: LoggingConfig

    # Reference to core config (sandbox, MCP, filesystem)
    daytona: DaytonaConfig
    mcp: MCPConfig
    filesystem: FilesystemConfig

    # Skills configuration
    skills: SkillsConfig = Field(default_factory=SkillsConfig)

    # Tool configuration
    # If True, use custom filesystem tools (Read, Write, Edit, Glob, Grep)
    # If False, use deepagents' native middleware tools (read_file, write_file, etc.)
    use_custom_filesystem_tools: bool = True

    # Vision tool configuration
    # If True, enable view_image tool for viewing images (requires vision-capable model)
    enable_view_image: bool = True

    # Subagent configuration
    # List of enabled subagent names (available: research, general-purpose)
    subagents_enabled: list[str] = Field(default_factory=lambda: ["general-purpose"])

    # Background task configuration
    # If True, wait for background tasks to complete before returning to CLI
    # If False (default), return immediately and show status of running tasks
    background_auto_wait: bool = False

    # Note: deep-agent automatically enables middlewares (TodoList, Summarization, etc.)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Runtime data (not from config files)
    llm_definition: LLMDefinition | None = Field(default=None, exclude=True)
    llm_client: Any | None = Field(default=None, exclude=True)  # BaseChatModel instance
    config_file_dir: Path | None = Field(default=None, exclude=True)  # For path resolution

    @classmethod
    def create(
        cls,
        llm: "BaseChatModel",
        daytona_api_key: str | None = None,
        daytona_base_url: str = "https://app.daytona.io/api",
        mcp_servers: list[MCPServerConfig] | None = None,
        allowed_directories: list[str] | None = None,
        **kwargs: Any,
    ) -> "AgentConfig":
        """Create an AgentConfig with sensible defaults.

        Required:
            llm: A LangChain chat model instance (e.g., ChatAnthropic, ChatOpenAI)

        Required Environment Variables:
            DAYTONA_API_KEY: Your Daytona API key (get from https://app.daytona.io)
                            Or pass daytona_api_key directly.

        Optional - Daytona:
            daytona_api_key: Override DAYTONA_API_KEY env var
            daytona_base_url: API URL (default: "https://app.daytona.io/api")
            python_version: Python version in sandbox (default: "3.12")
            auto_stop_interval: Seconds before auto-stop (default: 3600)

        Optional - MCP:
            mcp_servers: List[MCPServerConfig] for additional tools (default: [])

        Optional - Security:
            max_execution_time: Max execution seconds (default: 300)
            max_code_length: Max code characters (default: 10000)
            allowed_imports: List of allowed Python modules
            blocked_patterns: List of blocked code patterns

        Optional - Other:
            log_level: Logging level (default: "INFO")
            allowed_directories: Sandbox paths (default: ["/home/daytona", "/tmp"])
            subagents_enabled: Subagent names (default: ["general-purpose"])
            use_custom_filesystem_tools: Use Read/Write/Edit tools (default: True)
            enable_view_image: Enable image viewing (default: True)
            background_auto_wait: Wait for background tasks (default: False)

        Returns:
            Configured AgentConfig instance

        Example (minimal):
            from langchain_anthropic import ChatAnthropic

            llm = ChatAnthropic(model="claude-sonnet-4-20250514")
            config = AgentConfig.create(llm=llm)

        Example (with MCP servers):
            from langchain_anthropic import ChatAnthropic
            from ptc_agent.config import MCPServerConfig

            llm = ChatAnthropic(model="claude-sonnet-4-20250514")
            config = AgentConfig.create(
                llm=llm,
                mcp_servers=[
                    MCPServerConfig(
                        name="tavily",
                        command="npx",
                        args=["-y", "tavily-mcp@latest"],
                        env={"TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", "")},
                    ),
                ],
            )
        """
        # Create LLM config (placeholder for file-based loading compatibility)
        llm_config = LLMConfig(name="custom")

        # Create Daytona config with defaults
        api_key = daytona_api_key or os.getenv("DAYTONA_API_KEY", "")
        if not api_key:
            raise ValueError("DAYTONA_API_KEY must be provided or set in environment")
        daytona_config = DaytonaConfig(
            api_key=api_key,
            base_url=daytona_base_url,
            auto_stop_interval=kwargs.pop("auto_stop_interval", 3600),
            auto_archive_interval=kwargs.pop("auto_archive_interval", 86400),
            auto_delete_interval=kwargs.pop("auto_delete_interval", 604800),
            python_version=kwargs.pop("python_version", "3.12"),
            snapshot_enabled=kwargs.pop("snapshot_enabled", True),
            snapshot_name=kwargs.pop("snapshot_name", None),
            snapshot_auto_create=kwargs.pop("snapshot_auto_create", True),
        )

        # Create Security config with defaults
        security_config = SecurityConfig(
            max_execution_time=kwargs.pop("max_execution_time", 300),
            max_code_length=kwargs.pop("max_code_length", 10000),
            max_file_size=kwargs.pop("max_file_size", 10485760),
            enable_code_validation=kwargs.pop("enable_code_validation", True),
            allowed_imports=kwargs.pop("allowed_imports", [
                "os", "sys", "json", "yaml", "requests", "asyncio",
                "pathlib", "datetime", "re", "collections", "itertools",
            ]),
            blocked_patterns=kwargs.pop("blocked_patterns", [
                "eval(", "exec(", "__import__", "subprocess.call",
            ]),
        )

        # Create MCP config
        mcp_config = MCPConfig(
            servers=mcp_servers or [],
            tool_discovery_enabled=kwargs.pop("tool_discovery_enabled", True),
            lazy_load=kwargs.pop("lazy_load", True),
            tool_exposure_mode=kwargs.pop("tool_exposure_mode", "summary"),
        )

        # Create Logging config
        logging_config = LoggingConfig(
            level=kwargs.pop("log_level", "INFO"),
            file=kwargs.pop("log_file", "logs/ptc.log"),
        )

        # Create Filesystem config
        filesystem_config = FilesystemConfig(
            working_directory=kwargs.pop("working_directory", "/home/daytona"),
            allowed_directories=allowed_directories or ["/home/daytona", "/tmp"],
            enable_path_validation=kwargs.pop("enable_path_validation", True),
        )

        # Create Skills config
        skills_config = SkillsConfig(
            enabled=kwargs.pop("skills_enabled", True),
            user_skills_dir=kwargs.pop("user_skills_dir", "~/.ptc-agent/skills"),
            project_skills_dir=kwargs.pop("project_skills_dir", ".ptc-agent/skills"),
            sandbox_skills_base=kwargs.pop("sandbox_skills_base", "/home/daytona/skills"),
        )

        # Create the config
        config = cls(
            llm=llm_config,
            daytona=daytona_config,
            security=security_config,
            mcp=mcp_config,
            logging=logging_config,
            filesystem=filesystem_config,
            skills=skills_config,
            use_custom_filesystem_tools=kwargs.pop("use_custom_filesystem_tools", True),
            enable_view_image=kwargs.pop("enable_view_image", True),
            subagents_enabled=kwargs.pop("subagents_enabled", ["general-purpose"]),
            background_auto_wait=kwargs.pop("background_auto_wait", False),
        )

        # Set runtime data - store the LLM client directly
        config.llm_client = llm

        return config

    def validate_api_keys(self) -> None:
        """Validate that required API keys are present.

        For configs created via create(), only checks DAYTONA_API_KEY since
        the LLM client is passed directly with its own API key.

        For configs created via load_from_files(), also checks the LLM API key.

        Raises:
            ValueError: If required API keys are missing
        """
        missing_keys = []

        if not self.daytona.api_key:
            missing_keys.append("DAYTONA_API_KEY")

        # Check LLM API key only if using llm_definition (file-based loading)
        if self.llm_definition is not None:
            api_key = os.getenv(self.llm_definition.api_key_env, "")
            if not api_key:
                missing_keys.append(self.llm_definition.api_key_env)

        if missing_keys:
            raise ValueError(
                f"Missing required credentials in .env file:\n"
                f"  - {chr(10).join(missing_keys)}\n"
                f"Please add these credentials to your .env file."
            )

    def get_llm_client(self) -> "BaseChatModel":
        """Return the LLM client instance.

        For configs created via create(), returns the stored llm_client.
        For configs created via load_from_files(), builds from llm_definition.

        Returns:
            LangChain LLM client instance

        Raises:
            ValueError: If neither llm_client nor llm_definition is set
            ImportError: If SDK module cannot be imported (file-based loading)
            AttributeError: If SDK class cannot be found (file-based loading)
        """
        # If LLM client was passed directly (via create()), return it
        if self.llm_client is not None:
            return self.llm_client

        # Otherwise, build from llm_definition (file-based loading)
        if self.llm_definition is None:
            raise ValueError(
                "No LLM configured. Use AgentConfig.create(llm=...) or "
                "load_from_files() to configure an LLM."
            )

        # Parse SDK string (e.g., "langchain_anthropic.ChatAnthropic")
        sdk_parts = self.llm_definition.sdk.rsplit(".", 1)
        if len(sdk_parts) != 2:
            raise ValueError(
                f"Invalid SDK format: {self.llm_definition.sdk}. "
                f"Expected 'module.ClassName'"
            )

        module_name, class_name = sdk_parts

        # Dynamically import the SDK module
        try:
            module = __import__(module_name, fromlist=[class_name])
        except ImportError as e:
            raise ImportError(
                f"Failed to import SDK module '{module_name}': {e}\n"
                f"Make sure the required package is installed."
            ) from e

        # Get the class
        try:
            llm_class = getattr(module, class_name)
        except AttributeError as e:
            raise AttributeError(
                f"Class '{class_name}' not found in module '{module_name}'"
            ) from e

        # Get API key from environment
        api_key = os.getenv(self.llm_definition.api_key_env, "")

        # Build kwargs for LLM client
        kwargs = {
            "model": self.llm_definition.model_id,
            **self.llm_definition.parameters,  # Pass through all parameters
        }

        # Add API key with provider-specific parameter name
        if self.llm_definition.provider == "anthropic":
            kwargs["anthropic_api_key"] = api_key
        elif self.llm_definition.provider == "openai":
            kwargs["openai_api_key"] = api_key
        else:
            # Generic fallback (most use 'api_key')
            kwargs["api_key"] = api_key

        # Add base_url if specified (DeepSeek uses 'api_base' parameter name)
        if self.llm_definition.base_url:
            if "deepseek" in self.llm_definition.sdk.lower():
                kwargs["api_base"] = self.llm_definition.base_url
            else:
                kwargs["base_url"] = self.llm_definition.base_url

        # Add output_version if specified
        if self.llm_definition.output_version:
            kwargs["output_version"] = self.llm_definition.output_version

        # Add use_previous_response_id if specified
        if self.llm_definition.use_previous_response_id:
            kwargs["use_previous_response_id"] = self.llm_definition.use_previous_response_id

        # Instantiate and return client
        return llm_class(**kwargs)

    def to_core_config(self) -> CoreConfig:
        """Convert to CoreConfig for use with SessionManager.

        Returns:
            CoreConfig instance with sandbox/MCP settings
        """
        core_config = CoreConfig(
            daytona=self.daytona,
            security=self.security,
            mcp=self.mcp,
            logging=self.logging,
            filesystem=self.filesystem,
        )
        core_config.config_file_dir = self.config_file_dir
        return core_config
