"""
Skill context utilities for chat endpoint.

This module provides functions to parse skill contexts from requests,
load SKILL.md content from the skill registry, and build skill prefix
messages for the LLM.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.server.models.additional_context import SkillContext
from ptc_agent.agent.skills import get_skill, SkillMode

logger = logging.getLogger(__name__)


@dataclass
class SkillPrefixResult:
    """Result of building a skill prefix message."""

    message: Dict[str, Any]  # The user message dict to inject
    loaded_skill_names: list[str] = field(default_factory=list)  # Skills that successfully loaded


def build_tool_descriptions(skill_name: str, mode: SkillMode | None = None) -> Optional[str]:
    """Build formatted tool descriptions for a skill.

    Mirrors the format from DynamicSkillLoaderMiddleware._build_skill_result.

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


def load_skill_content(
    skill_name: str,
    skill_dirs: Optional[List[str]] = None,
    mode: SkillMode | None = None,
) -> Optional[str]:
    """Load SKILL.md content for a skill from local file system.

    Searches through skill directories to find and load the SKILL.md file
    for the specified skill.

    Args:
        skill_name: Name of the skill (e.g., 'user-profile')
        skill_dirs: Optional list of local skill directories to search.
                   If not provided, uses project_root/skills.
        mode: Optional agent mode filter. If provided, only loads skills
              whose exposure matches the mode.

    Returns:
        Content of SKILL.md as string, or None if not found

    Example:
        >>> content = load_skill_content("user-profile")
        >>> if content:
        ...     print(content[:50])
    """
    # Verify skill exists in registry (and matches mode if specified)
    skill = get_skill(skill_name, mode=mode)
    if not skill:
        logger.warning(f"Skill '{skill_name}' not found in registry")
        return None

    # Default skill directory: project_root/skills
    if skill_dirs is None:
        # Find project root (where skills/ directory lives)
        # Start from current working directory
        project_root = Path.cwd()
        skill_dirs = [str(project_root / "skills")]

    # Search for SKILL.md in each directory (last wins)
    content = None

    for skill_dir in skill_dirs:
        skill_md_path = Path(skill_dir) / skill_name / "SKILL.md"

        if skill_md_path.exists():
            try:
                content = skill_md_path.read_text(encoding="utf-8")
                logger.debug(
                    f"Loaded SKILL.md for '{skill_name}' from {skill_md_path}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to read SKILL.md for '{skill_name}' "
                    f"from {skill_md_path}: {e}"
                )

    if content is None:
        logger.warning(
            f"SKILL.md not found for skill '{skill_name}' in any skill directory"
        )

    return content


def build_skill_prefix_message(
    skills: List[SkillContext],
    skill_dirs: Optional[List[str]] = None,
    mode: SkillMode | None = None,
) -> Optional[SkillPrefixResult]:
    """Build a HumanMessage dict with loaded skill content and tool descriptions.

    Creates a message containing skill instructions that should be prepended
    to the conversation before the user's actual query. Also returns the list
    of successfully loaded skill names so callers can set loaded_skills in
    the graph state for immediate tool availability.

    Args:
        skills: List of SkillContext objects to load
        skill_dirs: Optional list of local skill directories to search
        mode: Optional agent mode filter. Skills whose exposure doesn't match
              the mode will be skipped.

    Returns:
        SkillPrefixResult with message and loaded skill names, or None if no skills loaded

    Example:
        >>> skills = [SkillContext(type="skills", name="user-profile", instruction="Help onboard")]
        >>> result = build_skill_prefix_message(skills)
        >>> result.message["role"]
        'user'
        >>> result.loaded_skill_names
        ['user-profile']
    """
    if not skills:
        return None

    loaded_skills = []
    skill_contents = []
    instructions = []
    all_tool_descriptions = []

    for skill_ctx in skills:
        content = load_skill_content(skill_ctx.name, skill_dirs, mode=mode)

        if content:
            loaded_skills.append(skill_ctx.name)

            if len(skills) > 1:
                # Multiple skills: add section header
                skill_contents.append(f"## Skill: {skill_ctx.name}\n{content}")
            else:
                # Single skill: no header needed
                skill_contents.append(content)

            # Collect tool descriptions for this skill
            tool_desc = build_tool_descriptions(skill_ctx.name, mode=mode)
            if tool_desc:
                if len(skills) > 1:
                    all_tool_descriptions.append(f"### {skill_ctx.name} tools\n{tool_desc}")
                else:
                    all_tool_descriptions.append(tool_desc)

            if skill_ctx.instruction:
                instructions.append(f"- {skill_ctx.name}: {skill_ctx.instruction}")
        else:
            logger.warning(
                f"Skipping skill '{skill_ctx.name}': SKILL.md not found"
            )

    if not loaded_skills:
        return None

    # Build the message content
    parts = [f"[Loaded skills: {', '.join(loaded_skills)}]", ""]

    # Add skill contents
    parts.append("\n\n".join(skill_contents))

    # Add tool descriptions
    if all_tool_descriptions:
        parts.append("\n\n**Available tools:**")
        parts.append("\n".join(all_tool_descriptions))
        parts.append("\nYou can call these tools directly without needing to call LoadSkill.")

    # Add instructions if any
    if instructions:
        if len(instructions) == 1 and len(skills) == 1:
            # Single skill with instruction: simpler format
            parts.append(f"\n\n[Instruction: {skills[0].instruction}]")
        else:
            # Multiple skills or instructions: bulleted list
            parts.append("\n\n[Instructions]")
            parts.extend(instructions)

    message_content = "\n".join(parts)

    logger.info(
        f"Built skill prefix message with {len(loaded_skills)} skills: "
        f"{loaded_skills}"
    )

    return SkillPrefixResult(
        message={"role": "user", "content": message_content},
        loaded_skill_names=loaded_skills,
    )
