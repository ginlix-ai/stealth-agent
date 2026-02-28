"""Declarative subagent definition.

A SubagentDefinition describes *what* a subagent is — its mode, tools, skills,
prompt strategy, and section toggles.  It gets compiled into a SubAgent TypedDict
at runtime by SubagentCompiler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

SubagentMode = Literal["ptc", "flash"]


@dataclass
class SubagentDefinition:
    """Declarative definition of a subagent.

    Prompt resolution priority (compiler checks in order):
      1. ``custom_prompt`` — raw string, used directly, no rendering.
      2. ``custom_prompt_template`` — standalone Jinja2 template, bypasses base.
      3. ``role_prompt`` / ``role_prompt_template`` — rendered via
         ``subagent_base.md.j2`` with section toggles + role appended (default).
    """

    # ── Identity ──────────────────────────────────────────────────────
    name: str
    """Unique identifier (e.g. ``"research"``, ``"general-purpose"``)."""

    description: str
    """Shown to the main agent for delegation decisions."""

    # ── Mode ──────────────────────────────────────────────────────────
    mode: SubagentMode = "ptc"
    """Determines base prompt template and default section toggles."""

    # ── Prompt configuration ──────────────────────────────────────────
    role_prompt: str = ""
    """Inline role-specific instructions appended to base template."""

    role_prompt_template: str | None = None
    """Path to a ``roles/*.md.j2`` template (alternative to inline)."""

    custom_prompt_template: str | None = None
    """Standalone Jinja2 template path — bypasses base template entirely."""

    custom_prompt: str | None = None
    """Raw prompt string — bypasses all template rendering."""

    # ── Skills ────────────────────────────────────────────────────────
    skills: list[str] = field(default_factory=list)
    """Skill names from SKILL_REGISTRY, loaded at runtime via SkillsMiddleware."""

    preload_skills: list[str] = field(default_factory=list)
    """Skill names whose SKILL.md content is injected into the prompt at compile time."""

    # ── Model ─────────────────────────────────────────────────────────
    model: str | None = None
    """Model override.  ``None`` = use the parent agent's model."""

    # ── Tools ─────────────────────────────────────────────────────────
    tools: list[str] = field(default_factory=list)
    """Tool set identifiers resolved at compile time (e.g. ``["execute_code", "filesystem"]``)."""

    extra_tools: list[Any] = field(default_factory=list)
    """Additional raw tool objects injected at runtime (not serialisable to YAML)."""

    # ── Execution limits ──────────────────────────────────────────────
    max_iterations: int = 15
    """Maximum tool-call iterations before the subagent stops."""

    # ── Template section toggles ──────────────────────────────────────
    sections: dict[str, bool] = field(default_factory=dict)
    """Override per-section defaults for the base template.

    Only used when the base template path is active (i.e. not ``custom_prompt``
    or ``custom_prompt_template``).
    """

    # ── Runtime requirements ──────────────────────────────────────────
    stateful: bool = False
    """Whether this subagent needs ``sandbox`` + ``mcp_registry`` at compile time."""

    # ── Source tracking ───────────────────────────────────────────────
    source: str = "builtin"
    """``"builtin"`` or ``"user"`` — for logging / debugging."""
