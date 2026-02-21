---
name: automation
description: Create and manage scheduled automations (cron jobs, one-time tasks).
---

# Automation Skill

This skill provides 3 tools for creating and managing scheduled automations:
- `check_automations` - List all or inspect a specific automation
- `create_automation` - Create a new scheduled automation
- `manage_automation` - Update, pause, resume, trigger, or delete automations

You should call these tools directly instead of using ExecuteCode tool.

---

## Tool 1: check_automations

List all automations or inspect a specific one with execution history.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `automation_id` | str | No | Automation ID to inspect. Omit to list all. |

### Examples

```python
# List all automations
check_automations()

# Inspect a specific automation (includes last 5 executions)
check_automations(automation_id="abc-123")
```

---

## Tool 2: create_automation

Create a new scheduled automation.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | str | Yes | Short name for the automation |
| `instruction` | str | Yes | The prompt the agent will execute on each run |
| `schedule` | str | Yes | Cron expression or ISO datetime (see below) |
| `description` | str | No | Optional description |
| `agent_mode` | str | No | `"flash"` (fast, default) or `"ptc"` (full sandbox) |

### Schedule Format

- **Recurring (cron):** Standard 5-field cron expression
  - `0 9 * * 1-5` — weekdays at 9 AM
  - `0 */4 * * *` — every 4 hours
  - `30 8 1 * *` — 1st of each month at 8:30 AM
- **One-time (ISO datetime):**
  - `2026-03-01T10:00:00` — single execution at that time

### Examples

```python
# Daily market briefing on weekdays at 9 AM
create_automation(
    name="Morning Market Brief",
    instruction="Summarize overnight market moves, top gainers/losers, and any news for my watchlist.",
    schedule="0 9 * * 1-5",
    agent_mode="flash",
)

# One-time earnings reminder
create_automation(
    name="AAPL Earnings Reminder",
    instruction="Analyze AAPL ahead of earnings: recent price action, analyst expectations, key metrics to watch.",
    schedule="2026-04-30T08:00:00",
    description="Pre-earnings analysis for Apple Q2 2026",
)
```

---

## Tool 3: manage_automation

Manage an existing automation.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `automation_id` | str | Yes | Automation ID to manage |
| `action` | str | Yes | One of: `update`, `pause`, `resume`, `trigger`, `delete` |
| `name` | str | No | New name (update only) |
| `description` | str | No | New description (update only) |
| `instruction` | str | No | New prompt (update only) |
| `schedule` | str | No | New cron or ISO datetime (update only) |
| `agent_mode` | str | No | New agent mode (update only) |

### Action Reference

| Action | Description |
|--------|-------------|
| `update` | Change name, description, instruction, schedule, or agent_mode |
| `pause` | Temporarily stop the automation from running |
| `resume` | Re-enable a paused automation |
| `trigger` | Run the automation immediately (outside normal schedule) |
| `delete` | Permanently remove the automation |

### Examples

```python
# Pause an automation
manage_automation(automation_id="abc-123", action="pause")

# Resume it
manage_automation(automation_id="abc-123", action="resume")

# Trigger an immediate run
manage_automation(automation_id="abc-123", action="trigger")

# Update the schedule to run every Monday at 8 AM
manage_automation(
    automation_id="abc-123",
    action="update",
    schedule="0 8 * * 1",
)

# Delete an automation
manage_automation(automation_id="abc-123", action="delete")
```
