"""
Infrastructure cost calculation and credit conversion utilities.

This module provides functions to:
1. Track infrastructure usage (external paid services)
2. Calculate infrastructure costs based on usage
3. Convert costs to credits for unified billing

Pricing is loaded from llm_manifest.json at module initialization (single source of truth).
Currently tracks external paid search services defined in manifest:
- TavilySearchTool
- TavilySearchImages
- BochaSearchTool

Free tools (DuckDuckGo, Arxiv) and internal operations (cache, storage, filesystem)
are not charged and will result in 0 credits.

Usage:
    tool_usage = {"TavilySearchTool": 5}
    result = calculate_infrastructure_credits(tool_usage)
    # Returns: {"total_credits": 80.0, "services": {...}}
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def _load_pricing_from_manifest() -> Dict[str, Any]:
    """
    Load infrastructure pricing from llm_manifest.json at module initialization.

    Returns:
        Pricing configuration dict with tool class names as keys

    Raises:
        RuntimeError: If manifest file not found or pricing section missing
    """
    import json

    # Get manifest path relative to this file
    manifest_path = Path(__file__).parent.parent.parent / "llms" / "llm_manifest.json"

    if not manifest_path.exists():
        raise RuntimeError(
            f"Infrastructure pricing manifest not found at {manifest_path}. "
            f"Cannot initialize pricing configuration."
        )

    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
    except Exception as e:
        raise RuntimeError(
            f"Failed to load infrastructure pricing from {manifest_path}: {e}"
        )

    # Extract infrastructure_pricing section
    infra_pricing = manifest.get("infrastructure_pricing")

    if not infra_pricing:
        raise RuntimeError(
            f"No 'infrastructure_pricing' section found in {manifest_path}. "
            f"Pricing configuration is required."
        )

    logger.info(
        f"Loaded infrastructure pricing from manifest: "
        f"{len(infra_pricing)} services configured"
    )

    return infra_pricing


# Load pricing from manifest at module import (single source of truth)
INFRASTRUCTURE_PRICING = _load_pricing_from_manifest()

# Service name mapping (tool class names → user-friendly service names)
TOOL_TO_SERVICE_MAPPING = {
    "TavilySearchTool": "tavily_search",
    "TavilySearchImages": "tavily_images",
    "BochaSearchTool": "bocha_search"
}


def calculate_infrastructure_credits(
    tool_usage: Dict[str, int],
    pricing_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Calculate infrastructure credits from tool usage counts.

    Args:
        tool_usage: Dict mapping tool names to usage counts
            Example: {"TavilySearchTool": 5, "cache_operations": 1000}
        pricing_config: Optional custom pricing config (defaults to INFRASTRUCTURE_PRICING)

    Returns:
        Dict with structure:
        {
            "total_credits": float,
            "services": {
                "tavily_search": {
                    "usage_count": 5,
                    "credits_per_use": 2,
                    "total_credits": 10
                },
                ...
            }
        }
    """
    if pricing_config is None:
        pricing_config = INFRASTRUCTURE_PRICING

    total_credits = 0.0
    services = {}

    for tool_name, count in tool_usage.items():
        if count <= 0:
            continue

        pricing = pricing_config.get(tool_name)
        if not pricing:
            logger.warning(
                f"[InfrastructureCosts] No pricing found for tool: {tool_name}. "
                f"Skipping credit calculation."
            )
            continue

        # Calculate credits based on pricing type
        if "credits_per_use" in pricing:
            # Per-use pricing (e.g., Tavily search)
            credits_per_use = pricing["credits_per_use"]
            tool_credits = count * credits_per_use
        elif "credits_per_1k_ops" in pricing:
            # Per-1k-ops pricing (e.g., cache operations)
            credits_per_1k = pricing["credits_per_1k_ops"]
            tool_credits = (count / 1000.0) * credits_per_1k
        elif "credits_per_op" in pricing:
            # Per-op pricing (e.g., filesystem operations)
            credits_per_op = pricing["credits_per_op"]
            tool_credits = count * credits_per_op
        else:
            logger.warning(
                f"[InfrastructureCosts] Unknown pricing format for {tool_name}. "
                f"Skipping."
            )
            continue

        total_credits += tool_credits

        # Map tool name to service name
        service_name = _map_tool_to_service(tool_name)

        # Build service entry
        service_entry = {
            "usage_count": count,
            "total_credits": round(tool_credits, 6)
        }

        # Add pricing details for transparency
        if "credits_per_use" in pricing:
            service_entry["credits_per_use"] = pricing["credits_per_use"]
        elif "credits_per_1k_ops" in pricing:
            service_entry["credits_per_1k_ops"] = pricing["credits_per_1k_ops"]
        elif "credits_per_op" in pricing:
            service_entry["credits_per_op"] = pricing["credits_per_op"]

        services[service_name] = service_entry

    return {
        "total_credits": round(total_credits, 6),
        "services": services
    }


def _map_tool_to_service(tool_name: str) -> str:
    """
    Map tool class names to user-friendly service names.

    Args:
        tool_name: Tool class name (e.g., "TavilySearchTool")

    Returns:
        Service name (e.g., "tavily_search")
    """
    return TOOL_TO_SERVICE_MAPPING.get(tool_name, tool_name.lower())




def format_infrastructure_usage(tool_usage: Dict[str, int]) -> Dict[str, Any]:
    """
    Format tool usage counts into a structured JSONB format for database storage.

    Args:
        tool_usage: Dict mapping tool names to usage counts

    Returns:
        Structured dict for infrastructure_usage JSONB column:
        {
            "services": {
                "tavily_search": {"count": 5, "type": "advanced"},
                "cache": {"count": 1000},
                ...
            }
        }
    """
    services = {}

    for tool_name, count in tool_usage.items():
        if count <= 0:
            continue

        service_name = _map_tool_to_service(tool_name)
        pricing = INFRASTRUCTURE_PRICING.get(tool_name, {})

        service_entry = {"count": count}

        # Add metadata from pricing
        if "search_type" in pricing:
            service_entry["type"] = pricing["search_type"]

        services[service_name] = service_entry

    return {"services": services}


# Example usage
if __name__ == "__main__":
    # Example tool usage
    tool_usage = {
        "TavilySearchTool": 5,
        "technical_analysis": 1,
        "cache_operations": 2500,
        "filesystem_operations": 10
    }

    # Calculate credits
    result = calculate_infrastructure_credits(tool_usage)

    print("Infrastructure Credits Calculation:")
    print(f"Total Credits: {result['total_credits']}")
    print("\nBreakdown by Service:")
    for service_name, service_data in result['services'].items():
        print(f"  {service_name}: {service_data}")

    # Format for database storage
    formatted = format_infrastructure_usage(tool_usage)
    print("\nFormatted for database storage:")
    import json
    print(json.dumps(formatted, indent=2))
