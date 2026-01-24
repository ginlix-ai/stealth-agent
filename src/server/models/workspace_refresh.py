"""Request/response models for workspace refresh.

Workspace refresh is a lightweight operation that re-syncs skills and
rebuilds the sandbox tools/modules for enabled MCP servers.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WorkspaceRefreshResponse(BaseModel):
    workspace_id: str = Field(description="Workspace identifier")
    status: str = Field(description="ok or error")
    message: str = Field(description="Human-readable summary")
    refreshed_tools: bool = Field(description="Whether tool modules were rebuilt")
    skills_uploaded: bool = Field(description="Whether skills were uploaded")
    servers: list[str] = Field(default_factory=list, description="Connected MCP servers")
    details: dict[str, Any] = Field(default_factory=dict, description="Extra info")
