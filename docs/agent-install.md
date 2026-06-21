# Agent Install Guide

This project is designed to be installed by Codex or another local coding agent.

## One-Line Prompt

```text
Install https://github.com/dalomeve/codex-chatgpt-bridge on this computer.
```

If the user only says this one sentence, treat it as enough instruction to install the bridge safely. Do not require them to paste a longer setup prompt.

## What The Agent Should Do

1. Clone the repository.
2. Install it with `pipx`, `uv tool`, or an isolated virtual environment.
3. Use Python 3.11 or newer.
4. Run `codex-chatgpt-bridge init`.
5. Install the local service if the OS supports it.
6. Ask the user which folders to grant before adding read, write, or execute permissions.
7. Start the bridge with `codex-chatgpt-bridge run` or the installed service.
8. If ChatGPT cannot reach localhost directly, ask before starting an authenticated HTTPS tunnel.
9. Tell the user which MCP URL and auth method to add in ChatGPT.
10. Tell the user to run `codex-chatgpt-bridge print-chatgpt-setup --show-token` locally if they need to display the bearer token.

## Safety Rules For Installers

- Do not grant all files by default.
- Do not grant write or execute permission unless the user asked for it.
- Do not run `codex-chatgpt-bridge enable-codex-tasks` unless the user asked for it.
- Do not expose the bridge over an unauthenticated public tunnel.
- Do not copy secrets into the config or README.
- Do not print tokens, private keys, cookies, `.env` contents, or cloud credentials.
