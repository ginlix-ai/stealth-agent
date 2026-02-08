# Frontend SSE Adaptation Changelog

This document summarizes the frontend changes made to adapt to the backend chat SSE event stream updates.

## 1. Tool Name Changes (snake_case → PascalCase)

**File:** `src/pages/ChatAgent/components/ToolCallMessageContent.jsx`

- **Change:** Updated `FILE_TOOLS` constant to include both PascalCase (new) and snake_case (legacy) tool names for backward compatibility.
- **New tool names:** `Read`, `Write`, `Edit`, `Save`, `ExecuteCode`, `Glob`, `Grep`, `WebFetch`, `WebSearch`
- **Legacy names retained:** `read_file`, `write_file`, `edit_file`, `save_file` (for older history)
- **Why:** Backend now uses LangChain SDK convention (PascalCase). FILE_TOOLS is used to detect file-related tools for opening in the file panel.

---

## 2. Subagent Event Detection

**Files:** `hooks/utils/streamEventHandlers.js`, `hooks/utils/historyEventHandlers.js`

### `isSubagentEvent` / `isSubagentHistoryEvent`

- **Old logic:** `event.agent.startsWith('tools:')`
- **New logic:** Subagent if `agent` contains `:` AND does NOT start with `model:` AND is NOT `"tools"`.
- **Rationale:** Backend convention:
  - Main agent: `agent.startsWith("model:")`
  - Tool node: `agent === "tools"`
  - Subagent: `agent` = `"{type}:{uuid4}"` (e.g., `"research:550e8400-..."`)

---

## 3. Subagent Status Event Handling

**File:** `hooks/utils/streamEventHandlers.js` – `handleSubagentStatus`

### Preferred Format (from BackgroundTaskRegistry)

- `active_tasks`: Array of objects with `id` (display_id), `agent_id` (stable UUID), `description`, `type`, `tool_calls`, `current_tool`
- `completed_tasks`: Array of display_id strings (`"Task-1"`, `"Task-2"`)

### Fallback Format (legacy)

- `active_subagents` / `completed_subagents`: Arrays of `agent_id` strings

### Key Changes

- Uses `agent_id` as the primary key for cards (not `id`/display_id).
- Passes `displayIdToAgentIdMap` to resolve `completed_tasks` display IDs to `agent_id`s.
- Calls `updateSubagentCard(agentId, {...})` with `agentId` as the card key.
- Stores `displayId` for human-readable UI when available.

---

## 4. Agent ID as Primary Identifier

**Files:** `hooks/useChatMessages.js`, `hooks/useFloatingCards.js`, `components/ChatView.jsx`

### Refactoring

- **`agent_id`** (format `{type}:{uuid4}`) is the stable identifier for subagent cards and event routing.
- **`display_id`** (`"Task-1"`, `"Task-2"`) is used only for UI display.
- Card IDs: `subagent-${agentId}` (e.g., `subagent-research:550e8400-...`).

### Mappings

- `agentToTaskMapRef`: Maps `agent_id` → `agent_id`.
- `toolCallIdToTaskIdMapRef`: Maps tool call IDs (from main agent’s `task` tool) → `agent_id`.
- `displayIdToAgentIdMapRef`: Maps display_id → `agent_id` for resolving `completed_tasks`.

### New Helpers

- `resolveSubagentIdToAgentId(subagentId)`: Resolves tool call ID or legacy ID to stable `agent_id`.
- `getSubagentHistory(subagentId)`: Returns history including `agentId` for card operations.

---

## 5. History Loading

**File:** `hooks/useChatMessages.js`

### Subagent Status in History

- Handles both preferred and fallback formats.
- Uses `task.agent_id` or `task.agent` for identity.
- Stores subagent history keyed by `agent_id`.

### Order-Based Matching

- `historyPendingAgentIdsRef`: Holds `agent_id`s from `subagent_status`.
- `historyPendingTaskToolCallIdsRef`: Holds tool call IDs from `task` tool calls.
- Order-based matching builds `toolCallIdToTaskIdMapRef` so segments and history resolve to the correct `agent_id`.

---

## 6. ChatView and Floating Cards

**File:** `components/ChatView.jsx`

- `onOpenSubagentTask`: Uses `resolveSubagentIdToAgentId` to convert segment `subagentId` (possibly a tool call ID) to `agent_id` before calling `updateSubagentCard` and `setSelectedAgentId`.
- Agent panel: Uses `displayId` when available for tab labels (e.g., `"Task-1"`).

**File:** `hooks/useFloatingCards.js`

- `updateSubagentCard(agentId, ...)`: First parameter is `agent_id`, not display_id.
- Stores `agentId` and `displayId` in `subagentData` for UI and routing.

---

## Summary

| Area | Old | New |
|------|-----|-----|
| Tool names | snake_case | PascalCase (with legacy fallback) |
| Subagent detection | `agent.startsWith('tools:')` | `agent` contains `:` and not `model:` and not `tools` |
| Subagent identity | display_id (`"Task-1"`) | `agent_id` (`"type:uuid4"`) |
| Card key | task ID / display ID | `agent_id` |
| `subagent_status` | `active_subagents` / `completed_subagents` | `active_tasks` / `completed_tasks` (preferred) with fallback |
