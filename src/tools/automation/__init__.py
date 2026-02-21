"""
Automation tools for creating and managing scheduled automations.

Provides 3 tools:
- check_automations: List all or inspect a specific automation
- create_automation: Create a new scheduled automation
- manage_automation: Update, pause, resume, trigger, or delete automations
"""

from src.tools.automation.tools import (
    check_automations,
    create_automation,
    manage_automation,
)

AUTOMATION_TOOLS = [
    check_automations,
    create_automation,
    manage_automation,
]

__all__ = [
    "check_automations",
    "create_automation",
    "manage_automation",
    "AUTOMATION_TOOLS",
]
