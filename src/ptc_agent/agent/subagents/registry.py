"""Subagent registry — merges built-in and user-defined definitions."""

from __future__ import annotations

import structlog

from ptc_agent.agent.subagents.builtins import BUILTIN_SUBAGENTS
from ptc_agent.agent.subagents.definition import SubagentDefinition
from ptc_agent.config.agent import SubagentConfig

logger = structlog.get_logger(__name__)


class SubagentRegistry:
    """Registry that merges built-in and user-defined subagent definitions.

    Resolution order: built-ins first, then user YAML definitions.
    User definitions override built-ins if the same name is used.
    """

    def __init__(
        self,
        builtins: dict[str, SubagentDefinition] | None = None,
        user_definitions: dict[str, SubagentConfig] | None = None,
    ) -> None:
        self._definitions: dict[str, SubagentDefinition] = {}

        # 1. Load built-ins
        for name, defn in (builtins or BUILTIN_SUBAGENTS).items():
            self._definitions[name] = defn

        # 2. Load user definitions (override built-ins if same name)
        for name, cfg in (user_definitions or {}).items():
            if name in self._definitions:
                logger.info("user subagent overrides builtin", name=name)

            self._definitions[name] = SubagentDefinition(
                name=name,
                description=cfg.description,
                mode=cfg.mode,
                role_prompt=cfg.role_prompt,
                role_prompt_template=cfg.role_prompt_template,
                custom_prompt_template=cfg.custom_prompt_template,
                custom_prompt=cfg.custom_prompt,
                tools=cfg.tools,
                skills=cfg.skills,
                preload_skills=cfg.preload_skills,
                model=cfg.model,
                max_iterations=cfg.max_iterations,
                sections=cfg.sections,
                stateful=(cfg.mode == "ptc"),
                source="user",
            )

    def get(self, name: str) -> SubagentDefinition | None:
        """Get a definition by name."""
        return self._definitions.get(name)

    def get_enabled(self, enabled_names: list[str]) -> list[SubagentDefinition]:
        """Return definitions for enabled subagents, in order.

        Raises:
            ValueError: If an enabled name is not found in the registry.
        """
        result: list[SubagentDefinition] = []
        for name in enabled_names:
            defn = self._definitions.get(name)
            if defn is None:
                available = ", ".join(sorted(self._definitions))
                msg = (
                    f"Subagent '{name}' is in 'enabled' list but not defined. "
                    f"Available: [{available}]"
                )
                raise ValueError(msg)
            result.append(defn)
        return result

    def list_all(self) -> dict[str, SubagentDefinition]:
        """Return a copy of all registered definitions."""
        return dict(self._definitions)
