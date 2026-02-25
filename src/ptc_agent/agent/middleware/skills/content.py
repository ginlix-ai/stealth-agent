"""Skill content loading — reads SKILL.md from local filesystem.

Moved here from ``src.server.utils.skill_context`` to avoid a circular import
(middleware → server → middleware).  This module only depends on the skills
registry, not on the server layer.
"""

import logging
from pathlib import Path
from typing import Optional

from ptc_agent.agent.middleware.skills.registry import SkillMode, get_skill

logger = logging.getLogger(__name__)


def load_skill_content(
    skill_name: str,
    skill_dirs: Optional[list[str]] = None,
    mode: SkillMode | None = None,
) -> Optional[str]:
    """Load SKILL.md content for a skill from local file system.

    Searches through skill directories to find and load the SKILL.md file
    for the specified skill.

    Args:
        skill_name: Name of the skill (e.g. 'user-profile')
        skill_dirs: Optional list of local skill directories to search.
                   If not provided, uses project_root/skills.
        mode: Optional agent mode filter. If provided, only loads skills
              whose exposure matches the mode.

    Returns:
        Content of SKILL.md as string, or None if not found
    """
    # Verify skill exists in registry (and matches mode if specified)
    skill = get_skill(skill_name, mode=mode)
    if not skill:
        logger.warning(f"Skill '{skill_name}' not found in registry")
        return None

    # Default skill directory: project_root/skills
    if skill_dirs is None:
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
