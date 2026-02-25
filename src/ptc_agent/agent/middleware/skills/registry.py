"""
Skill registry for dynamic tool loading.

This module defines the registry of available skills that can be dynamically
loaded by the agent via the load_skill mechanism. Each skill contains a set
of tools that are pre-registered but hidden until the skill is loaded.
"""

from dataclasses import dataclass
from typing import Any, Literal

from src.tools.automation import AUTOMATION_TOOLS
from src.tools.onboarding import ONBOARDING_TOOLS
from src.tools.user_profile import USER_PROFILE_TOOLS

# Type alias for agent modes that can use skills
SkillMode = Literal["ptc", "flash"]


@dataclass
class SkillDefinition:
    """Definition of a loadable skill.

    Attributes:
        name: Unique skill identifier
        description: Human-readable description of what the skill does
        tools: List of LangChain tools included in this skill
        skill_md_path: Optional path to SKILL.md with detailed instructions
        exposure: Which agent mode(s) can use this skill ("ptc", "flash", or "both")
    """

    name: str
    description: str
    tools: list[Any]
    skill_md_path: str | None = None
    exposure: Literal["ptc", "flash", "both", "hidden"] = "ptc"

    def get_tool_names(self) -> list[str]:
        """Get list of tool names in this skill."""
        return [getattr(t, "name", str(t)) for t in self.tools]

    def format_tool_descriptions(self, max_desc_len: int = 200) -> str:
        """Format tool descriptions for display.

        Args:
            max_desc_len: Maximum length for each tool's description text.

        Returns:
            Formatted string with one line per tool.
        """
        lines = []
        for t in self.tools:
            name = getattr(t, "name", str(t))
            desc = getattr(t, "description", "No description")
            if len(desc) > max_desc_len:
                desc = desc[:max_desc_len] + "..."
            lines.append(f"  - **{name}**: {desc}")
        return "\n".join(lines)


def _matches_mode(skill: SkillDefinition, mode: SkillMode | None) -> bool:
    """Check if a skill matches the given agent mode.

    Returns True if mode is None (no filter), skill.exposure matches,
    or skill is hidden (hidden skills match any mode for explicit lookup
    but are excluded from listings by callers).
    """
    if mode is None:
        return True
    if skill.exposure == "hidden":
        return True  # Available in all modes, excluded from listings separately
    return skill.exposure == mode or skill.exposure == "both"


# Registry of all available skills
# Skills are pre-registered at agent creation but tools are hidden until loaded
SKILL_REGISTRY: dict[str, SkillDefinition] = {
    "user-profile": SkillDefinition(
        name="user-profile",
        description="Manage user profile: watchlists, portfolio, and preferences",
        tools=USER_PROFILE_TOOLS,
        skill_md_path="skills/user-profile/SKILL.md",
        exposure="both",
    ),
    "onboarding": SkillDefinition(
        name="onboarding",
        description="First-time user onboarding: collect stocks, risk tolerance, and preferences",
        tools=ONBOARDING_TOOLS,
        skill_md_path="skills/onboarding/SKILL.md",
        exposure="hidden",
    ),
    "automation": SkillDefinition(
        name="automation",
        description="Create and manage scheduled automations (cron jobs, one-time tasks)",
        tools=AUTOMATION_TOOLS,
        skill_md_path="skills/automation/SKILL.md",
        exposure="both",
    ),
    "pdf": SkillDefinition(
        name="pdf",
        description="PDF manipulation: extract text/tables, create, merge/split documents, and fill forms",
        tools=[],
        skill_md_path="skills/pdf/SKILL.md",
        exposure="ptc",
    ),
    "docx": SkillDefinition(
        name="docx",
        description="Word document creation, editing, tracked changes, comments, and text extraction",
        tools=[],
        skill_md_path="skills/docx/SKILL.md",
        exposure="ptc",
    ),
    "pptx": SkillDefinition(
        name="pptx",
        description="Presentation creation, editing, layouts, speaker notes, and slide manipulation",
        tools=[],
        skill_md_path="skills/pptx/SKILL.md",
        exposure="ptc",
    ),
    "xlsx": SkillDefinition(
        name="xlsx",
        description="Spreadsheet creation, editing, formulas, data analysis, and visualization",
        tools=[],
        skill_md_path="skills/xlsx/SKILL.md",
        exposure="ptc",
    ),
    "creating-financial-models": SkillDefinition(
        name="creating-financial-models",
        description="Financial modeling: DCF analysis, sensitivity testing, Monte Carlo simulations",
        tools=[],
        skill_md_path="skills/creating-financial-models/SKILL.md",
        exposure="ptc",
    ),
}


def get_skill_registry(mode: SkillMode | None = None) -> dict[str, SkillDefinition]:
    """Get the skill registry filtered by agent mode.

    Args:
        mode: Optional agent mode filter. None returns all skills.

    Returns:
        Dict of skill name to SkillDefinition for matching skills
    """
    if mode is None:
        return dict(SKILL_REGISTRY)
    return {
        name: skill
        for name, skill in SKILL_REGISTRY.items()
        if _matches_mode(skill, mode)
    }


def get_sandbox_skill_names() -> set[str]:
    """Get names of skills that should be synced to sandbox.

    Returns skills with exposure "ptc" or "both" — NOT "flash" (flash-only
    skills are never accessed in sandboxes).

    Returns:
        Set of skill names for sandbox upload
    """
    return {
        name
        for name, skill in SKILL_REGISTRY.items()
        if skill.exposure in ("ptc", "both")
    }


def get_skill(skill_name: str, mode: SkillMode | None = None) -> SkillDefinition | None:
    """Get a skill definition by name, optionally validating exposure mode.

    Args:
        skill_name: Name of the skill to retrieve
        mode: Optional agent mode. If provided, only returns the skill if
              its exposure matches the mode.

    Returns:
        SkillDefinition if found and mode-compatible, None otherwise
    """
    skill = SKILL_REGISTRY.get(skill_name)
    if skill is None:
        return None
    if mode is not None and not _matches_mode(skill, mode):
        return None
    return skill


def get_all_skill_tools(mode: SkillMode | None = None) -> list[Any]:
    """Get all tools from registered skills, optionally filtered by mode.

    Used during agent creation to pre-register all tools with ToolNode.

    Args:
        mode: Optional agent mode filter. None returns tools from all skills.

    Returns:
        Flat list of all tools from matching skills
    """
    all_tools = []
    for skill in SKILL_REGISTRY.values():
        if _matches_mode(skill, mode):
            all_tools.extend(skill.tools)
    return all_tools


def get_all_skill_tool_names(mode: SkillMode | None = None) -> set[str]:
    """Get names of all tools from registered skills, optionally filtered by mode.

    Used by middleware to identify which tools belong to skills.

    Args:
        mode: Optional agent mode filter. None returns tool names from all skills.

    Returns:
        Set of tool names
    """
    names = set()
    for skill in SKILL_REGISTRY.values():
        if _matches_mode(skill, mode):
            names.update(skill.get_tool_names())
    return names


def list_skills(mode: SkillMode | None = None) -> list[dict[str, Any]]:
    """List available skills with their metadata, optionally filtered by mode.

    Hidden skills are excluded from listings (they can only be activated
    programmatically via additionalContext).

    Args:
        mode: Optional agent mode filter. None returns all non-hidden skills.

    Returns:
        List of skill info dicts with name, description, and tool count
    """
    return [
        {
            "name": skill.name,
            "description": skill.description,
            "tool_count": len(skill.tools),
            "tools": skill.get_tool_names(),
        }
        for skill in SKILL_REGISTRY.values()
        if _matches_mode(skill, mode) and skill.exposure != "hidden"
    ]
