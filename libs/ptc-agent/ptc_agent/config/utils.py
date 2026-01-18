"""Shared configuration loading utilities.

This module provides common functions for loading and validating YAML configuration
files
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiofiles
import structlog
import yaml
from dotenv import load_dotenv

if TYPE_CHECKING:
    from ptc_agent.config.core import (
        DaytonaConfig,
        FilesystemConfig,
        LoggingConfig,
        MCPConfig,
        SecurityConfig,
    )


async def load_yaml_file(file_path: Path) -> dict[str, Any]:
    """Load and parse a YAML file asynchronously.

    Args:
        file_path: Path to the YAML file

    Returns:
        Parsed YAML content as dictionary

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If YAML parsing fails or file is empty
    """
    if not file_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {file_path}\n"
            f"Please create config.yaml with all required settings."
        )

    try:
        async with aiofiles.open(file_path) as f:
            content = await f.read()
        # yaml.safe_load is CPU-bound but fast for config files
        config_data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        msg = f"Failed to parse config.yaml: {e}"
        raise ValueError(msg) from e

    if not config_data:
        raise ValueError(
            "config.yaml is empty. Please add required configuration sections."
        )

    return config_data


async def load_dotenv_async(env_file: Path | None = None) -> None:
    """Load environment variables from .env file asynchronously.

    Args:
        env_file: Optional path to .env file. If None, searches default locations.
    """
    if env_file:
        await asyncio.to_thread(load_dotenv, env_file)
    else:
        await asyncio.to_thread(load_dotenv)


def validate_required_sections(
    config_data: dict[str, Any],
    required_sections: list[str],
    config_name: str = "config.yaml"
) -> None:
    """Validate that all required sections exist in config data.

    Args:
        config_data: Parsed config dictionary
        required_sections: List of required section names
        config_name: Name of config file for error messages

    Raises:
        ValueError: If any required sections are missing
    """
    missing = [s for s in required_sections if s not in config_data]
    if missing:
        raise ValueError(
            f"Missing required sections in {config_name}: {', '.join(missing)}\n"
            f"Please add these sections to your config.yaml file."
        )


def validate_section_fields(
    section_data: dict[str, Any],
    required_fields: list[str],
    section_name: str
) -> None:
    """Validate that all required fields exist in a config section.

    Args:
        section_data: Section dictionary
        required_fields: List of required field names
        section_name: Name of section for error messages

    Raises:
        ValueError: If any required fields are missing
    """
    missing = [f for f in required_fields if f not in section_data]
    if missing:
        raise ValueError(
            f"Missing required fields in {section_name} section: {', '.join(missing)}"
        )


# Common field requirements for shared config sections
DAYTONA_REQUIRED_FIELDS = [
    "base_url",
    "auto_stop_interval",
    "auto_archive_interval",
    "auto_delete_interval",
    "python_version",
]

SECURITY_REQUIRED_FIELDS = [
    "max_execution_time",
    "max_code_length",
    "max_file_size",
    "enable_code_validation",
    "allowed_imports",
    "blocked_patterns",
]

MCP_REQUIRED_FIELDS = ["servers", "tool_discovery_enabled"]

LOGGING_REQUIRED_FIELDS = ["level", "file"]

FILESYSTEM_REQUIRED_FIELDS = ["allowed_directories"]


# Factory functions for creating config objects from dictionaries


def create_daytona_config(data: dict[str, Any]) -> DaytonaConfig:
    """Create DaytonaConfig from config data dictionary.

    Args:
        data: Daytona section from config.yaml

    Returns:
        Configured DaytonaConfig object
    """
    import os

    from ptc_agent.config.core import DaytonaConfig

    validate_section_fields(data, DAYTONA_REQUIRED_FIELDS, "daytona")
    return DaytonaConfig(
        api_key=os.getenv("DAYTONA_API_KEY", ""),
        base_url=data["base_url"],
        auto_stop_interval=data["auto_stop_interval"],
        auto_archive_interval=data["auto_archive_interval"],
        auto_delete_interval=data["auto_delete_interval"],
        python_version=data["python_version"],
        snapshot_enabled=data.get("snapshot_enabled", True),
        snapshot_name=data.get("snapshot_name"),
        snapshot_auto_create=data.get("snapshot_auto_create", True),
    )


def create_security_config(data: dict[str, Any]) -> SecurityConfig:
    """Create SecurityConfig from config data dictionary.

    Args:
        data: Security section from config.yaml

    Returns:
        Configured SecurityConfig object
    """
    from ptc_agent.config.core import SecurityConfig

    validate_section_fields(data, SECURITY_REQUIRED_FIELDS, "security")
    return SecurityConfig(
        max_execution_time=data["max_execution_time"],
        max_code_length=data["max_code_length"],
        max_file_size=data["max_file_size"],
        enable_code_validation=data["enable_code_validation"],
        allowed_imports=data["allowed_imports"],
        blocked_patterns=data["blocked_patterns"],
    )


def create_mcp_config(data: dict[str, Any]) -> MCPConfig:
    """Create MCPConfig from config data dictionary.

    Args:
        data: MCP section from config.yaml

    Returns:
        Configured MCPConfig object
    """
    from ptc_agent.config.core import MCPConfig, MCPServerConfig

    validate_section_fields(data, MCP_REQUIRED_FIELDS, "mcp")
    mcp_servers = [MCPServerConfig(**server) for server in data["servers"]]
    return MCPConfig(
        servers=mcp_servers,
        tool_discovery_enabled=data["tool_discovery_enabled"],
        lazy_load=data.get("lazy_load", True),
        cache_duration=data.get("cache_duration"),
        tool_exposure_mode=data.get("tool_exposure_mode", "summary"),
    )


def create_logging_config(data: dict[str, Any]) -> LoggingConfig:
    """Create LoggingConfig from config data dictionary.

    Args:
        data: Logging section from config.yaml

    Returns:
        Configured LoggingConfig object
    """
    from ptc_agent.config.core import LoggingConfig

    validate_section_fields(data, LOGGING_REQUIRED_FIELDS, "logging")
    return LoggingConfig(
        level=data["level"],
        file=data["file"],
    )


def create_filesystem_config(data: dict[str, Any]) -> FilesystemConfig:
    """Create FilesystemConfig from config data dictionary.

    Args:
        data: Filesystem section from config.yaml

    Returns:
        Configured FilesystemConfig object
    """
    from ptc_agent.config.core import FilesystemConfig

    validate_section_fields(data, FILESYSTEM_REQUIRED_FIELDS, "filesystem")
    return FilesystemConfig(
        allowed_directories=data["allowed_directories"],
        enable_path_validation=data.get("enable_path_validation", True),
    )


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog to respect log level from config.

    This function configures log level filtering

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )
