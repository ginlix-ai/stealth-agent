"""
Skill context utilities for chat endpoint.

This module provides functions to parse skill contexts from requests,
load SKILL.md content from the skill registry, and build skill prefix
messages for the LLM.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional

from src.server.models.additional_context import SkillContext
from ptc_agent.agent.middleware.skills import get_skill, SkillMode
from ptc_agent.agent.middleware.skills.content import (
    load_skill_content,  # noqa: F401 — re-exported for backwards compatibility
)

logger = logging.getLogger(__name__)


@dataclass
class SkillPrefixResult:
    """Result of building skill content for inline injection."""

    content: str  # Formatted skill text wrapped in <loaded-skill> tags
    loaded_skill_names: list[str] = field(default_factory=list)  # Skills that successfully loaded


def build_tool_descriptions(skill_name: str, mode: SkillMode | None = None) -> Optional[str]:
    """Build formatted tool descriptions for a skill.

    Mirrors the format from SkillsMiddleware._build_skill_result.

    Args:
        skill_name: Name of the skill
        mode: Optional agent mode filter

    Returns:
        Formatted tool description string, or None if skill has no tools
    """
    skill = get_skill(skill_name, mode=mode)
    if not skill or not skill.tools:
        return None

    return skill.format_tool_descriptions()


def parse_skill_contexts(
    additional_context: Optional[List[Any]]
) -> List[SkillContext]:
    """Extract skill contexts from additional_context list.

    Filters the additional_context list to return only SkillContext items.

    Args:
        additional_context: List of context items from ChatRequest

    Returns:
        List of SkillContext objects

    Example:
        >>> contexts = parse_skill_contexts([
        ...     {"type": "skills", "name": "user-profile", "instruction": "Help onboard"},
        ... ])
        >>> len(contexts)
        1
        >>> contexts[0].name
        'user-profile'
    """
    if not additional_context:
        return []

    skill_contexts = []

    for ctx in additional_context:
        # Handle both dict and Pydantic model
        if isinstance(ctx, dict):
            ctx_type = ctx.get("type")
            if ctx_type == "skills":
                skill_contexts.append(SkillContext(
                    type="skills",
                    name=ctx.get("name", ""),
                    instruction=ctx.get("instruction"),
                ))
        elif isinstance(ctx, SkillContext):
            skill_contexts.append(ctx)
        elif hasattr(ctx, "type") and ctx.type == "skills":
            skill_contexts.append(SkillContext(
                type="skills",
                name=getattr(ctx, "name", ""),
                instruction=getattr(ctx, "instruction", None),
            ))

    if skill_contexts:
        logger.info(
            f"Parsed {len(skill_contexts)} skill contexts: "
            f"{[s.name for s in skill_contexts]}"
        )

    return skill_contexts


def build_skill_content(
    skills: List[SkillContext],
    skill_dirs: Optional[List[str]] = None,
    mode: SkillMode | None = None,
) -> Optional[SkillPrefixResult]:
    """Build skill content for inline injection into user messages.

    Creates formatted skill content wrapped in <loaded-skill> XML tags,
    suitable for appending inline to the last user message. Also returns
    the list of successfully loaded skill names so callers can set
    loaded_skills in the graph state for immediate tool availability.

    Args:
        skills: List of SkillContext objects to load
        skill_dirs: Optional list of local skill directories to search
        mode: Optional agent mode filter. Skills whose exposure doesn't match
              the mode will be skipped.

    Returns:
        SkillPrefixResult with content string and loaded skill names, or None if no skills loaded

    Example:
        >>> skills = [SkillContext(type="skills", name="user-profile", instruction="Help onboard")]
        >>> result = build_skill_content(skills)
        >>> '<loaded-skill' in result.content
        True
        >>> result.loaded_skill_names
        ['user-profile']
    """
    if not skills:
        return None

    loaded_skills = []
    skill_blocks = []
    instructions = []

    for skill_ctx in skills:
        content = load_skill_content(skill_ctx.name, skill_dirs, mode=mode)

        if content:
            loaded_skills.append(skill_ctx.name)

            # Build per-skill block with tool descriptions
            block_parts = [content]
            tool_desc = build_tool_descriptions(skill_ctx.name, mode=mode)
            if tool_desc:
                block_parts.append(f"\n**Available tools:**\n{tool_desc}")
                block_parts.append("You can call these tools directly without needing to call LoadSkill.")

            block_content = "\n".join(block_parts)
            skill_blocks.append(
                f'<loaded-skill name="{skill_ctx.name}">\n{block_content}\n</loaded-skill>'
            )

            if skill_ctx.instruction:
                instructions.append(f"- {skill_ctx.name}: {skill_ctx.instruction}")
        else:
            logger.warning(
                f"Skipping skill '{skill_ctx.name}': SKILL.md not found"
            )

    if not loaded_skills:
        return None

    # Combine all skill blocks
    parts = skill_blocks

    # Add instructions if any
    if instructions:
        if len(instructions) == 1 and len(skills) == 1:
            parts.append(f"\n[Instruction: {skills[0].instruction}]")
        else:
            parts.append("\n[Instructions]")
            parts.extend(instructions)

    combined_content = "\n\n".join(parts)

    logger.info(
        f"Built skill content with {len(loaded_skills)} skills: "
        f"{loaded_skills}"
    )

    return SkillPrefixResult(
        content=combined_content,
        loaded_skill_names=loaded_skills,
    )
