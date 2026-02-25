"""
Skills endpoint — list available agent skills.
"""

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from ptc_agent.agent.skills import list_skills, SkillMode

router = APIRouter(prefix="/api/v1/skills", tags=["Skills"])


class SkillInfo(BaseModel):
    name: str
    description: str
    tool_count: int
    tools: list[str] = Field(default_factory=list)


class SkillsResponse(BaseModel):
    skills: list[SkillInfo]


@router.get("", response_model=SkillsResponse)
async def get_skills(mode: Optional[SkillMode] = Query(None, description="Filter by agent mode: ptc or flash")):
    """
    List available skills that can be loaded by the agent.

    Args:
        mode: Optional agent mode filter (ptc/flash). Returns mode-compatible skills only.

    Returns:
        Dict with skills array containing name, description, tool_count, tools
    """
    return {"skills": list_skills(mode=mode)}
