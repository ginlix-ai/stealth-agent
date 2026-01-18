# Base agent-model mapping (default configuration)
BASE_AGENT_LLM_MAP: dict[str, str] = {
    #"coordinator": "qwen-flash-non-think",
    "coordinator": "doubao-seed-1.6-flash",
    "deep_research/direct_response": "glm-4-7",
    "deep_research/planner": "glm-4-7",
    "deep_research/researcher": "glm-4-7",
    "deep_research/coder": "glm-4-7",
    "deep_research/data_agent": "glm-4-7",
    "reporter": "glm-4-7",
    # Middleware agents
    "summarization": "glm-4-7",  # Cost-effective model for conversation summarization
    # Tool agents
    "web_fetch": "doubao-seed-1.8-non-think",  # Fast model for web content extraction
}

# Define agent LLM presets (overrides for BASE_AGENT_LLM_MAP)
# Each preset can override specific agents with different models
AGENT_LLM_PRESETS: dict[str, dict[str, str]] = {
    # Default preset - no overrides, uses BASE_AGENT_LLM_MAP as-is
    "default": {},
    # Fallback preset - reliable, cross-provider models for each agent type
    # Used for model fallback middleware when primary model fails
    "fallback": {
        "deep_research/planner": "minimax-m2.1",
        "deep_research/researcher": "minimax-m2.1",
        "deep_research/coder": "minimax-m2.1",
        "deep_research/data_agent": "minimax-m2.1",
        "deep_research/direct_response": "minimax-m2.1",
        "reporter": "minimax-m2.1",
        "coordinator": "minimax-m2.1",
        "summarization": "minimax-m2.1",
        "web_fetch": "minimax-m2.1",
    },
}


def get_agent_llm_map(preset: str = "default") -> dict[str, str]:
    """
    Get agent-to-LLM mapping with optional preset overrides.

    Args:
        preset: Name of the preset to apply. Available presets:
            - "default": Use BASE_AGENT_LLM_MAP without modifications
            - "cost-optimized": Use cheaper flash variants for key agents
            - "minimax-test": Test MiniMax models for key agents

    Returns:
        dict[str, str]: Merged agent-to-LLM mapping with preset overrides applied

    Example:
        >>> map = get_agent_llm_map("cost-optimized")
        >>> map["deep_research/planner"]
    """
    if preset not in AGENT_LLM_PRESETS:
        raise ValueError(
            f"Unknown preset: {preset}. "
            f"Available presets: {', '.join(AGENT_LLM_PRESETS.keys())}"
        )

    # Start with base map and apply preset overrides
    result = BASE_AGENT_LLM_MAP.copy()
    result.update(AGENT_LLM_PRESETS[preset])
    return result


# Default agent-to-LLM mapping (for backward compatibility)
# To use a different preset, call get_agent_llm_map(preset="preset-name")
AGENT_LLM_MAP: dict[str, str] = get_agent_llm_map("default")
