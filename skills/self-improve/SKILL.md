---
name: self-improve
description: Report issues and propose fixes to improve your own capabilities when you encounter errors or limitations
---

# Self-Improvement

You have access to `gh` CLI and `git` in the sandbox. Use this skill when
you encounter bugs, errors, or limitations in your own capabilities during
your work.

## When to Activate This Skill

Recognize these situations during your normal work:
- A tool call fails with an unexpected error
- A skill's instructions (SKILL.md) have wrong examples or outdated API usage
- An MCP tool returns malformed or unexpected data
- A prompt instruction is unclear, contradictory, or missing
- A sandbox script or package is broken or misconfigured
- You notice a code pattern that would make your work more effective if fixed

**Always ask the user for consent before filing an issue or creating a PR.**
Briefly explain what you found and what you want to report, then ask for
approval. Do NOT file anything without explicit user confirmation.

**Do NOT derail the user's current task.** Keep the consent request brief,
file the issue quickly after approval, then continue with the user's request.

## Authentication
- `GITHUB_TOKEN` env var is pre-configured (injected from `GITHUB_BOT_TOKEN`)
- Git identity is set via env vars — no `git config` needed

## Workflow 1: Report a Bug (default — quick, no cloning)

Use when: you encounter any issue with your own capabilities.
Time: <30 seconds. Don't interrupt the user's flow.

Template:
```bash
gh issue create --repo "ginlix-ai/LangAlpha" \
  --title "bug(agent): <what broke>" \
  --label "agent-reported" \
  --body "<structured body>"
```

Issue body structure:
```
## What I was doing
<user's task context — what were you trying to accomplish>

## What went wrong
<exact error message or unexpected behavior>

## Where the issue likely is
<file paths, function names, skill names — be specific>

## Suggested fix
<if obvious, describe; otherwise "Needs investigation">

## Environment
- Thread: <thread_id if available>
- Tool/Skill: <which tool or skill was involved>
- Error type: <tool_error | skill_instruction | mcp_data | prompt | sandbox>
```

## Workflow 2: Propose a Fix (when the fix is obvious and self-contained)

Use when: the root cause is clear AND the fix is small (1-3 files).
Skip and file an issue instead if: architectural decision needed, root cause
unclear, or fix touches core agent logic.

Steps:
1. Clone: `gh repo clone "ginlix-ai/LangAlpha" .self-improve/langalpha -- --depth 1`
2. Branch from `feat/latest`: `cd .self-improve/langalpha && git checkout feat/latest && git checkout -b bot/fix/<short-desc>`
3. Make the fix (keep it minimal and focused)
4. Test: `ruff check . && pytest` (or relevant subset)
5. Commit: conventional format — `fix(scope): description`
6. PR:
```bash
gh pr create --repo "ginlix-ai/LangAlpha" \
  --base feat/latest \
  --title "fix(agent): <what's fixed>" \
  --label "agent-reported" \
  --body "<structured body>"
```

PR body structure:
```
## Problem
<link to issue if filed, or describe the bug>

## Root Cause
<what was wrong and why>

## Fix
<what was changed and why this approach>

## Testing
<what tests were run, what was verified>

## Context
- Discovered during: <brief user task description>
- Thread: <thread_id>
```

## Label Convention
- Always use `agent-reported` label
- Add `bug` for broken behavior, `enhancement` for capability gaps
- Add scope labels: `skills`, `tools`, `mcp`, `prompt`, `sandbox`

## Safety Rules
- NEVER push to `main` or `feat/latest` — always `bot/fix/` or `bot/feat/` branches
- Always branch from `feat/latest` (the current development branch), target PRs to `feat/latest`
- ALWAYS run linting and tests before creating a PR
- Keep PRs small — one fix per PR, max 1-3 files
- Clone to `.self-improve/langalpha` (inside workspace, persists across restarts)
- NEVER commit tokens, secrets, API keys, or user data
- NEVER include confidential or private information in issues or PRs — no user data, no internal business context, no API responses containing private data, no conversation content. Describe the technical problem only.
- After filing/PR, immediately return to the user's original task

## Pre-Submit Checklist

Go through EVERY item before running `gh issue create` or `gh pr create`:

- [ ] **User consent obtained** — user explicitly approved filing this issue/PR
- [ ] **No secrets or tokens** — title, body, and diff contain zero credentials, API keys, or env values
- [ ] **No private data** — no user names, portfolio holdings, conversation content, or internal business context
- [ ] **No raw API responses** — sanitize or omit any data returned from MCP tools or external APIs
- [ ] **Technical description only** — the issue/PR describes the bug or fix, not what the user was working on
- [ ] **Correct repo** — targeting `ginlix-ai/LangAlpha`
- [ ] **Correct branch** (PRs only) — branched from `feat/latest`, PR base is `feat/latest`
- [ ] **Minimal diff** (PRs only) — only the files needed for the fix, no unrelated changes
