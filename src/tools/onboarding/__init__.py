"""
Onboarding tools: user profile management + HITL workspace/question tools.

Combines USER_PROFILE_TOOLS with create_workspace and start_question
for the complete onboarding flow.
"""

from src.tools.onboarding.tools import create_workspace, start_question
from src.tools.user_profile import USER_PROFILE_TOOLS

ONBOARDING_TOOLS = [*USER_PROFILE_TOOLS, create_workspace, start_question]

__all__ = [
    "create_workspace",
    "start_question",
    "ONBOARDING_TOOLS",
]
