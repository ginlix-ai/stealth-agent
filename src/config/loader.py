
import os
import yaml
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


def replace_env_vars(value: str) -> str:
    """Replace environment variables in string values."""
    if not isinstance(value, str):
        return value
    if value.startswith("$"):
        env_var = value[1:]
        return os.getenv(env_var, env_var)
    return value


def process_dict(config: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively process dictionary to replace environment variables."""
    if not config:
        return {}
    result = {}
    for key, value in config.items():
        if isinstance(value, dict):
            result[key] = process_dict(value)
        elif isinstance(value, list):
            result[key] = process_list(value)
        elif isinstance(value, str):
            result[key] = replace_env_vars(value)
        else:
            result[key] = value
    return result


def process_list(config_list: List[Any]) -> List[Any]:
    """Recursively process list to replace environment variables."""
    result = []
    for item in config_list:
        if isinstance(item, dict):
            result.append(process_dict(item))
        elif isinstance(item, list):
            result.append(process_list(item))
        elif isinstance(item, str):
            result.append(replace_env_vars(item))
        else:
            result.append(item)
    return result


_config_cache: Dict[str, Dict[str, Any]] = {}


def load_yaml_config(file_path: str) -> Dict[str, Any]:
    """
    Load and process YAML configuration file.

    Args:
        file_path: Path to the YAML configuration file

    Returns:
        Processed configuration dictionary with environment variables replaced
    """
    if not os.path.exists(file_path):
        logger.warning(f"Configuration file not found: {file_path}")
        return {}

    if file_path in _config_cache:
        return _config_cache[file_path]

    with open(file_path, "r", encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)

    if not raw_config:
        logger.warning(f"Empty configuration file: {file_path}")
        return {}

    # Process environment variables in config values
    processed_config = process_dict(raw_config)

    # Log configuration summary
    logger.info(
        f"Loaded configuration from {file_path} "
        f"(settings: {len(processed_config)})"
    )

    _config_cache[file_path] = processed_config
    return processed_config


def clear_config_cache():
    """Clear the configuration cache. Useful for testing or when config files change."""
    global _config_cache
    _config_cache = {}
    logger.info("Configuration cache cleared")
