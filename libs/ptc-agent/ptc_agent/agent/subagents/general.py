"""General-purpose sub-agent definition for deepagent.

This sub-agent has access to all main tools (execute_code, filesystem tools)
and MCP tools, enabling complex task delegation from the main agent.
"""

from typing import Any

from ptc_agent.agent.prompts import format_tool_summary, get_loader
from ptc_agent.agent.tools import create_execute_code_tool
from ptc_agent.utils.storage.storage_uploader import is_storage_enabled


def get_general_subagent_config(
    sandbox: Any,
    mcp_registry: Any,
    max_iterations: int = 10,
    additional_tools: list[Any] | None = None,
    *,
    include_mcp_docs: bool = True,
    tool_exposure_mode: str = "full",
    filesystem_tools: list[Any] | None = None,
    vision_tools: list[Any] | None = None,
) -> dict[str, Any]:
    """Get configuration for the general-purpose sub-agent.

    Args:
        sandbox: PTCSandbox instance for code execution
        mcp_registry: MCPRegistry with available MCP tools
        max_iterations: Maximum execution iterations
        additional_tools: Additional tools to include
        include_mcp_docs: Whether to include MCP tool documentation in prompt
        tool_exposure_mode: How to format tool docs ("full" or "summary")
        filesystem_tools: Custom filesystem tools (read, write, edit, glob, grep)
            to use instead of relying on FilesystemMiddleware
        vision_tools: Optional vision tools (e.g., view_image) for multimodal capabilities

    Returns:
        Sub-agent configuration dictionary for deepagent
    """
    # Generate MCP tool summary if requested
    mcp_tool_summary = ""
    if include_mcp_docs and mcp_registry:
        tools_by_server = mcp_registry.get_all_tools()
        if tools_by_server:
            # Convert to format expected by formatter
            tools_dict = {}
            for server_name, tools in tools_by_server.items():
                tools_dict[server_name] = [tool.to_dict() for tool in tools]

            mcp_tool_summary = f"""
<MCP Tools>
The following MCP tools are available via execute_code:

{format_tool_summary(tools_dict, mode=tool_exposure_mode)}

Import and use MCP tools in your execute_code calls:
```python
from tools.{{server_name}} import {{tool_name}}
result = tool_name(param="value")
```
</MCP Tools>
"""

    # Render instructions using template loader (date auto-injected from session)
    loader = get_loader()
    instructions = loader.get_subagent_prompt(
        "general",
        max_iterations=max_iterations,
        tool_summary=mcp_tool_summary,
        storage_enabled=is_storage_enabled(),
    )

    # Create execute_code tool with sandbox and MCP registry
    execute_code_tool = create_execute_code_tool(sandbox, mcp_registry)

    # Base tools for general agent
    tools = [execute_code_tool]

    # Add custom filesystem tools if provided
    # This overrides deepagent's FilesystemMiddleware for these operations
    if filesystem_tools:
        tools.extend(filesystem_tools)

    # Add vision tools if provided (e.g., view_image for multimodal capabilities)
    if vision_tools:
        tools.extend(vision_tools)

    # Add any additional tools
    if additional_tools:
        tools.extend(additional_tools)

    return {
        "name": "general-purpose",  # Override built-in general-purpose with our custom prompt
        "description": (
            "Delegate complex tasks to the general-purpose sub-agent. "
            "This agent has access to all filesystem tools (read, write, edit, glob, grep, bash) "
            "and can execute Python code with MCP tools. Use for multi-step operations, "
            "data processing, file manipulation, or any task requiring full tool access."
        ),
        "system_prompt": instructions,
        "tools": tools,
    }


def create_general_subagent(
    sandbox: Any,
    mcp_registry: Any,
    max_iterations: int = 10,
    additional_tools: list[Any] | None = None,
    *,
    include_mcp_docs: bool = True,
    tool_exposure_mode: str = "full",
    filesystem_tools: list[Any] | None = None,
    vision_tools: list[Any] | None = None,
) -> dict[str, Any]:
    """Create a general-purpose sub-agent for deepagent.

    Convenience wrapper around get_general_subagent_config.

    Args:
        sandbox: PTCSandbox instance for code execution
        mcp_registry: MCPRegistry with available MCP tools
        max_iterations: Maximum execution iterations
        additional_tools: Additional tools to include
        include_mcp_docs: Whether to include MCP tool documentation in prompt
        tool_exposure_mode: How to format tool docs ("full" or "summary")
        filesystem_tools: Custom filesystem tools (read, write, edit, glob, grep)
        vision_tools: Optional vision tools (e.g., view_image) for multimodal capabilities

    Returns:
        Sub-agent configuration dictionary
    """
    return get_general_subagent_config(
        sandbox=sandbox,
        mcp_registry=mcp_registry,
        max_iterations=max_iterations,
        additional_tools=additional_tools,
        include_mcp_docs=include_mcp_docs,
        tool_exposure_mode=tool_exposure_mode,
        filesystem_tools=filesystem_tools,
        vision_tools=vision_tools,
    )
