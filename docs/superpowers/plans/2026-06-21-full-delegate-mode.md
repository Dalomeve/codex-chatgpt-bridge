# Full Delegate Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let ChatGPT web delegate broad local work to this machine through full file permissions and persistent local Codex sessions.

**Architecture:** Keep the public default restricted, but add an explicit `full_delegate` trust mode that bypasses grant and sensitive-path checks for the current machine. Add config-mutating MCP tools for grants/mode, and Codex session tools backed by `codex exec` plus `codex exec resume`, with bridge session metadata persisted under the bridge config directory.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, asyncio subprocesses, pytest, ruff, uv build.

---

### Task 1: Full Delegate Authorization And Runtime Config Tools

**Files:**
- Modify: `src/codex_chatgpt_bridge/config.py`
- Modify: `src/codex_chatgpt_bridge/gateway.py`
- Modify: `src/codex_chatgpt_bridge/mcp.py`
- Modify: `src/codex_chatgpt_bridge/cli.py`
- Test: `tests/test_config.py`
- Test: `tests/test_gateway.py`
- Test: `tests/test_mcp.py`

- [ ] **Step 1: Write failing tests**

Add tests proving:
- `BridgeConfig.trust_mode` defaults to `restricted` and round-trips.
- `full_delegate` can read/write paths outside grants, including sensitive-looking names.
- `set_bridge_mode`, `grant_path`, and `revoke_grant` mutate runtime config and persist it.
- MCP `tools/list` exposes the new config tools.

- [ ] **Step 2: Run focused tests to verify RED**

Run: `.venv/bin/pytest tests/test_config.py tests/test_gateway.py tests/test_mcp.py -q`

Expected: failures mentioning missing `trust_mode`, missing gateway methods, or missing tools.

- [ ] **Step 3: Implement minimal config and gateway changes**

Add `trust_mode: Literal["restricted", "full_delegate"] = "restricted"` to config. Pass a `config_path` into `LocalGateway`, add `_save_runtime_config`, and implement `set_bridge_mode`, `grant_path`, and `revoke_grant`.

- [ ] **Step 4: Implement MCP schemas and dispatch**

Add the three tools to `tool_definitions` and `call_tool`. Mark `set_bridge_mode` and grant mutations as destructive because they change local access policy.

- [ ] **Step 5: Verify GREEN**

Run: `.venv/bin/pytest tests/test_config.py tests/test_gateway.py tests/test_mcp.py -q`

Expected: all focused tests pass.

### Task 2: Persistent Codex Session Tools

**Files:**
- Create: `src/codex_chatgpt_bridge/codex_sessions.py`
- Modify: `src/codex_chatgpt_bridge/gateway.py`
- Modify: `src/codex_chatgpt_bridge/mcp.py`
- Test: `tests/test_codex_sessions.py`
- Test: `tests/test_gateway.py`
- Test: `tests/test_mcp.py`

- [ ] **Step 1: Write failing tests**

Add tests proving:
- A `codex_session_start` run invokes `codex exec`, records bridge session metadata, and returns the final message.
- A `codex_session_continue` run invokes `codex exec resume` with the recorded Codex session id.
- `codex_session_list` returns persisted sessions.
- MCP exposes session tools only when Codex tasks are enabled.

- [ ] **Step 2: Run focused tests to verify RED**

Run: `.venv/bin/pytest tests/test_codex_sessions.py tests/test_gateway.py tests/test_mcp.py -q`

Expected: failures for missing module and missing tools.

- [ ] **Step 3: Implement session registry and Codex runner**

Create a small registry JSON file under the bridge config directory. Capture a Codex session id from JSONL stdout when available; otherwise infer the newest Codex session file changed during the run.

- [ ] **Step 4: Wire gateway and MCP**

Add `codex_session_start`, `codex_session_continue`, `codex_session_list`, and `codex_session_status`. Keep `codex_task_run` as a compatibility wrapper around a single start call.

- [ ] **Step 5: Verify GREEN**

Run: `.venv/bin/pytest tests/test_codex_sessions.py tests/test_gateway.py tests/test_mcp.py -q`

Expected: all focused tests pass.

### Task 3: Docs, Local Install, And Connector Refresh

**Files:**
- Modify: `README.md`
- Modify: `docs/agent-install.md`

- [ ] **Step 1: Document the two modes**

Explain `restricted` vs `full_delegate`, state that `full_delegate` gives ChatGPT/Codex local read/write/execute power, and keep the default install restricted for public users.

- [ ] **Step 2: Add CLI commands**

Expose `set-mode restricted|full_delegate`, `grant --write --execute`, and `enable-codex-tasks` as the installer path for users who want the same full bridge.

- [ ] **Step 3: Run full verification**

Run:
- `.venv/bin/ruff check .`
- `.venv/bin/ruff format --check .`
- `.venv/bin/pytest -q`
- `.venv/bin/python -m build --wheel`

- [ ] **Step 4: Install locally and verify**

Install from the local repo, set this machine to `full_delegate`, enable Codex tasks, restart launchd, and verify public secret URL `tools/list` includes the new full delegate and Codex session tools.

- [ ] **Step 5: Review, commit, push**

Request code review, fix blocking feedback, commit with `feat: add full delegate codex sessions`, and push.
