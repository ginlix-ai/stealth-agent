"""Built-in subagent definitions.

These are the default subagents shipped with the agent.  User-defined
definitions in ``agent_config.yaml`` can override any of these by name.
"""

from __future__ import annotations

from ptc_agent.agent.subagents.definition import SubagentDefinition

BUILTIN_SUBAGENTS: dict[str, SubagentDefinition] = {
    "research": SubagentDefinition(
        name="research",
        description=(
            "Delegate research to the sub-agent researcher. "
            "Give this researcher one specific topic or question at a time. "
            "The researcher will search the web and provide findings with citations."
        ),
        mode="ptc",
        role_prompt_template="roles/researcher.md.j2",
        tools=["web_search", "think"],
        max_iterations=5,
        stateful=False,
        sections={
            "workspace_paths": False,
            "tool_guide": False,
            "data_processing": False,
            "visualizations": False,
        },
    ),
    "general-purpose": SubagentDefinition(
        name="general-purpose",
        description=(
            "Delegate complex tasks to the general-purpose sub-agent. "
            "This agent has access to all filesystem tools "
            "(read, write, edit, glob, grep, bash) and can execute Python "
            "code with MCP tools. Use for multi-step operations, data "
            "processing, file manipulation, or any task requiring full tool access."
        ),
        mode="ptc",
        role_prompt_template="roles/general.md.j2",
        tools=["execute_code", "filesystem", "bash", "finance"],
        max_iterations=10,
        stateful=True,
        sections={
            "workspace_paths": True,
            "tool_guide": True,
            "data_processing": True,
            "visualizations": True,
        },
    ),
}
