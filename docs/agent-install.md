# Agent Install Guide

This project is designed to be installed by Codex or another local coding agent.

## One-Line Prompt

```text
Install https://github.com/dalomeve/codex-chatgpt-bridge on this computer.
```

If the user only says this one sentence, treat it as enough instruction to install the bridge safely. Do not require them to paste a longer setup prompt.

If the user explicitly asks for full local access, all files, all permissions, or ChatGPT using local Codex as a device agent, treat that as a request for full delegate mode.

## Installer Contract

When acting as the installing agent, do not stop after the package and service are installed. A successful install means:

1. The local CLI is installed.
2. The local config exists.
3. The local service is running.
4. The user has been asked which local project or folders ChatGPT may access.
5. The requested grants have been added.
6. The ChatGPT web connector has been created or a clear browser-access blocker has been reported.
7. If ChatGPT web cannot reach localhost directly, a stable HTTPS tunnel has been configured.
8. The connector has been verified by calling `list_grants` or `bridge_status`, or the user has been given the exact remaining manual step if automation is unavailable.

## What The Agent Should Do

1. Prefer direct install with `uv tool install git+https://github.com/dalomeve/codex-chatgpt-bridge.git` or `pipx install git+https://github.com/dalomeve/codex-chatgpt-bridge.git`.
2. Clone the repository only when the user wants local development, source edits, or the direct tool install fails.
3. Use Python 3.11 or newer.
4. Run `codex-chatgpt-bridge init`.
5. Install the local service if the OS supports it.
6. Ask the user which folders or projects ChatGPT should be able to access.
7. For each folder, ask whether it should be read-only, read/write, or read/write/execute.
8. Add only the grants the user explicitly chose.
9. Start the bridge with `codex-chatgpt-bridge run` or the installed service.
10. If ChatGPT cannot reach localhost directly, use a stable HTTPS tunnel. Prefer OpenAI
    Secure MCP Tunnel. If the user cannot provide a tunnel id and runtime key, use a named
    Cloudflare Tunnel or another stable endpoint the user controls.
11. Open ChatGPT in the user's browser if browser or computer-use tools are available. Explain that this is only to create the connector.
12. Create an MCP connector named `Codex ChatGPT Bridge`.
13. Use the local MCP URL, or the authenticated tunnel URL if a tunnel was needed.
14. If ChatGPT supports HTTP Bearer / bearer API key, use `/mcp` and paste the bearer token through a safe local secret-input or clipboard path.
15. If ChatGPT only offers OAuth / unauthenticated / mixed auth, use `/mcp/<connector-secret>` and choose unauthenticated. Treat the full URL as a secret.
16. Set the ChatGPT app permission policy to `Allow all actions` when the user explicitly requested local Codex delegation. For safer read-only installs, keep the least permissive policy that still allows the selected tools.
17. After connecting, verify the connector by asking ChatGPT to call `list_grants`. If the user requested `delegate` profile, verify with `bridge_status` instead because low-level grant tools are intentionally hidden.
18. Do not count a temporary `trycloudflare.com` quick tunnel as a completed install target. It
    is acceptable for a short smoke test only. A successful install needs a stable tunnel URL
    that can survive process restarts or be recreated through an explicit named tunnel profile.
19. If browser automation or connector creation is blocked, tell the user exactly what remains: connector name, MCP URL, auth type, permission policy, and the local command to display the token or secret URL.

## Tunnel Diagnosis

Before blaming ChatGPT or the bridge for `Connection failed`, verify each layer:

1. Local bridge health: `curl http://127.0.0.1:8766/healthz`.
2. Local secret MCP endpoint: call `tools/list` on `/mcp/<connector-secret>` without printing
   the secret URL in chat.
3. Tunnel process logs. For Cloudflare quick tunnels, repeated `7844` timeouts mean the tunnel
   is not connected to Cloudflare edge.
4. ChatGPT app details. If the app still points at an old tunnel URL, refresh or recreate the
   app after the new stable tunnel is running.
5. Run `codex-chatgpt-bridge tunnel-doctor --url <connector-url> --log <tunnel-log>` locally.
   It redacts connector secrets and flags quick tunnels, localhost URLs, and connection-failure
   log patterns.

## Full Delegate Install

Only do this when the user explicitly asks for all local files, all permissions, no local permission limits, or direct local Codex delegation.
Run these mode/profile commands after install, reinstall, `init`, or any config regeneration. Do not
assume the service is still in delegate mode until `bridge_status` proves it.

1. Run `codex-chatgpt-bridge set-mode full_delegate`.
2. Run `codex-chatgpt-bridge enable-codex-tasks`.
3. Run `codex-chatgpt-bridge set-tool-profile delegate` when the user wants ChatGPT web to dispatch local Codex as the device agent with minimal repeated MCP approvals.
4. Restart the local service.
5. Refresh or recreate the ChatGPT connector so it discovers the delegate profile:
   - `bridge_status`
   - `codex_delegate`
   - `codex_session_list`
   - `codex_session_status`
6. Verify from ChatGPT web by typing `@`, selecting the bridge app from the menu so it becomes a real app chip, and asking it to call `bridge_status`. Plain text that merely starts with the app name is not enough. If the UI has multiple model/mode choices, use a high-capability mode that supports custom app tools; in the Chinese UI, `超高` has worked better than `Pro 扩展` for actual MCP tool attachment. The result should show `trust_mode=full_delegate`, `tool_profile=delegate`, and a `codex_delegate` tool.
7. For local-device tasks, instruct the user to ask ChatGPT to call `codex_delegate` once with structured scope:
   - `task`: the complete local task.
   - `permission_level`: the maximum local capability, one of `read_only`, `local_file_write`, `repo_edit`, `shell_command`, `gui_control`, or `full_local`. If `sandbox_mode` is omitted, the bridge derives it from this value and rejects any explicit sandbox that exceeds it.
   - `target_paths`: local files or folders in scope, if known.
   - `expected_result`: what should be true when local Codex is done.
   ChatGPT may still ask for one host-level custom MCP approval for that action; do not make it chain `grant_path`, `read_file`, `write_file`, and session tools.
8. If ChatGPT replies with `blocked_by_openai_safety_check` or says the tool call was blocked by OpenAI's safety check, report that as a ChatGPT host-layer block. The local bridge did not receive the request, and changing local grants or restarting the bridge will not fix that specific block.
9. Tell the user that full delegate mode means ChatGPT can ask the local bridge to read/write local files and drive local Codex with broad execution rights, but ChatGPT web may still refuse to send destructive tool calls to the bridge.

## ChatGPT Developer Mode Notes

Developer Mode and MCP app availability can differ by account rollout and plan. In one tested
ChatGPT Pro web account, `Settings -> Apps -> Advanced settings -> Developer mode` was visible,
enabled, and allowed development apps with `Allow all actions`. Official Help Center and
developer docs may describe different rollout boundaries, so installers should verify the
actual account UI and tool-call result instead of assuming Pro is read-only or fully writable.

## Safety Rules For Installers

- Do not grant all files by default.
- Do not grant write or execute permission unless the user asked for it.
- Do not run `codex-chatgpt-bridge enable-codex-tasks` unless the user asked for it.
- Do not run `codex-chatgpt-bridge set-mode full_delegate` unless the user explicitly asked for all-file/all-permission local delegation.
- Do not run `codex-chatgpt-bridge set-tool-profile delegate` unless the user explicitly wants local Codex delegation as the primary ChatGPT tool surface.
- Do not expose the bridge over an unauthenticated public tunnel.
- Do not copy secrets into the config or README.
- Do not print tokens, private keys, cookies, `.env` contents, or cloud credentials.
- Do not paste the bearer token into the chat transcript. Paste it only into the local ChatGPT connector auth field when operating the browser on the user's behalf.
- Do not paste the connector secret URL into the chat transcript. Paste it only into the local ChatGPT connector URL field when operating the browser on the user's behalf.
- If no safe secret-input or clipboard path is available, ask the user to run `codex-chatgpt-bridge print-chatgpt-setup --show-token` locally and paste the token or secret URL themselves.
- When using browser automation, only operate the ChatGPT connector setup flow. Do not inspect, summarize, or extract existing ChatGPT conversations, tabs, account data, or page contents unrelated to connector setup.
