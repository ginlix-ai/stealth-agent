# PTC Agent

Core agent package for Programmatic Tool Calling (PTC) - an AI agent framework built on LangGraph that executes code in secure Daytona sandboxes and integrates with MCP (Model Context Protocol) servers for extensible tool capabilities.

> **Note**: This package is not yet published to PyPI. Install from the repository root or local source.

## Architecture

```
ptc_agent/
├── agent/                    # Agent implementation
│   ├── agent.py              # PTCAgent, PTCExecutor classes
│   ├── graph.py              # Agent graph construction
│   ├── backends/             # Sandbox backends (Daytona)
│   ├── middleware/           # Middleware stack (deepagent, plan_mode, background)
│   ├── tools/                # Built-in tools (bash.py, code_execution.py, file_ops.py, glob.py, grep.py, tavily.py, think.py)
│   ├── subagents/            # Subagent definitions (general, research)
│   └── prompts/              # Jinja2 prompt templates
├── config/                   # Configuration system
│   ├── core.py               # CoreConfig, MCPServerConfig
│   ├── agent.py              # AgentConfig, LLMConfig
│   ├── loaders.py            # File-based config loading
│   └── utils.py              # Config utilities
├── core/                     # Core infrastructure
│   ├── sandbox.py            # PTCSandbox (Daytona wrapper)
│   ├── mcp_registry.py       # MCPRegistry (tool discovery)
│   ├── session.py            # Session, SessionManager
│   ├── security.py           # Code validation
│   └── tool_generator.py     # MCP schema → Python functions
└── utils/                    # Shared utilities
    └── storage/              # Cloud storage (S3, R2, OSS)
```

### Key Components

- **agent/**: Main `PTCAgent` class with middleware stack (background agent orchestration, plan mode, background tasks), built-in tools, subagent system, and Jinja2-based prompt templates
- **config/**: Two configuration modes - programmatic via `AgentConfig.create()` or file-based via `load_from_files()` for YAML configs
- **core/**: Infrastructure layer with `PTCSandbox` for Daytona code execution, `MCPRegistry` for MCP server management, and `SessionManager` for conversation lifecycle
- **utils/**: Cloud storage uploaders supporting AWS S3, Cloudflare R2, and Alibaba Cloud OSS

## Installation

```bash
# From project root (recommended)
uv sync

# Or pip install from local source
pip install -e libs/ptc-agent
```

## Quick Start (Use as Package)

```python
import asyncio
import os
from langchain.chat_models import init_chat_model
from ptc_agent import AgentConfig, PTCAgent
from ptc_agent.config import MCPServerConfig
from ptc_agent.core import SessionManager

async def main():
    # 1. Create LLM
    llm = init_chat_model("gpt-5.1-codex")

    # 2. Configure with MCP servers
    config = AgentConfig.create(
        llm=llm,
        mcp_servers=[
            MCPServerConfig(
                name="yfinance",
                description="Use this to get stock data",
                command="uv",
                args=["run", "python", "mcp_servers/yfinance_mcp_server.py"],
            ),
        ],
        subagents_enabled=["general-purpose", "research"],
    )
    config.validate_api_keys()

    # 3. Create session
    session = SessionManager.get_session("demo", config.to_core_config())
    await session.initialize()

    try:
        # 4. Create agent
        ptc_agent = PTCAgent(config)
        agent = ptc_agent.create_agent(
            sandbox=session.sandbox,
            mcp_registry=session.mcp_registry,
            subagent_names=config.subagents_enabled,
        )

        # 5. Execute task
        result = await agent.ainvoke({
            "messages": [{
                "role": "user",
                "content": "Get AAPL stock price and create a chart"
            }]
        })

        print("Task completed!")

    finally:
        # 6. Cleanup
        await session.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
```

### Model Switching

To switch models without recreating `PTCAgent`, pass an `llm` override to `create_agent()`:

```python
from langchain_openai import ChatOpenAI

# Switch to a different model for this agent instance
new_llm = ChatOpenAI(model="gpt-4o")
agent = ptc_agent.create_agent(
    sandbox=session.sandbox,
    mcp_registry=session.mcp_registry,
    llm=new_llm,  # Overrides the LLM from config
)
```

## Configuration Methods

### Method A: File-Based (Recommended; used for CLI)

Make sure you have a `config.yaml` and `llms.json` file in the current working directory or in the project root.

Use `load_from_files()` for file-based configuration:

```python
from ptc_agent.config import load_from_files

# Auto-discovers config.yaml, llms.json, .env
config = await load_from_files()
config.validate_api_keys()
```

**Config File Search Paths** depend on the `ConfigContext`:

| Context | Search Order | Use Case |
|---------|--------------|----------|
| `SDK` (default) | CWD → git root → `~/.ptc-agent/` | Programmatic usage, scripts |
| `CLI` | `~/.ptc-agent/` → CWD | CLI applications, user-facing tools |

```python
from ptc_agent.config import ConfigContext, load_from_files

# SDK context (default) - searches CWD first
config = await load_from_files()

# CLI context - searches ~/.ptc-agent/ first (user config takes priority)
config = await load_from_files(context=ConfigContext.CLI)
```

**Environment Variable Overrides:**
- `PTC_CONFIG_FILE` - Path to config.yaml
- `PTC_LLMS_FILE` - Path to llms.json

**With Explicit Paths:**

```python
from pathlib import Path

config = await load_from_files(
    config_file=Path("path/to/config.yaml"),
    llms_file=Path("path/to/llms.json"),
    env_file=Path(".env"),
)
```

### Method B: Programmatic

Use `AgentConfig.create()` for programmatic configuration with sensible defaults:

```python
from langchain_anthropic import ChatAnthropic
from ptc_agent import AgentConfig
from ptc_agent.config import MCPServerConfig

llm = ChatAnthropic(model="claude-sonnet-4-20250514")


config = AgentConfig.create(
    llm=llm,
    mcp_servers=[
        MCPServerConfig(
            name="tavily",
            description="Web search capabilities",
            command="npx",
            args=["-y", "tavily-mcp@latest"],
            env={"TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", "")},
        ),
    ],
)
```

**Path Resolution**: Relative paths in `args` (e.g., `mcp_servers/my_server.py`) are resolved relative to the config file location first, then fall back to CWD. Absolute paths are also supported.

**With Custom Parameters:**

```python
config = AgentConfig.create(
    llm=llm,
    # Daytona settings
    daytona_base_url="https://app.daytona.io/api",
    python_version="3.12",
    auto_stop_interval=3600,

    # Security
    max_execution_time=300,
    max_code_length=10000,

    # Agent features
    use_custom_filesystem_tools=True,
    subagents_enabled=["general-purpose", "research"],

    # Logging
    log_level="INFO",
)
```


## Requirements

- Python 3.12+
- Daytona account ([app.daytona.io](https://app.daytona.io))
- LLM API key (Anthropic, OpenAI, etc.)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DAYTONA_API_KEY` | Yes | Daytona sandbox API key |
| `ANTHROPIC_API_KEY` | Depends | Required if using Anthropic models |
| `OPENAI_API_KEY` | Depends | Required if using OpenAI models |
| MCP server keys | Optional | e.g., `TAVILY_API_KEY` for web search |