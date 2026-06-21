# Agent Install Guide

This project is designed to be installed by Codex or another local coding agent.

## Suggested Prompt

```text
Install https://github.com/dalomeve/codex-chatgpt-bridge on this computer.
Create a secure default config.
Grant read access to ~/Documents and read/write/execute access to ~/Projects.
Do not enable local Codex task execution unless I explicitly ask for it.
Install it as a local service if this OS supports it.
Then print the ChatGPT MCP connector setup URL and safety summary.
```

## What The Agent Should Do

1. Clone the repository.
2. Install it with `pipx`, `uv tool`, or an isolated virtual environment.
3. Use Python 3.11 or newer.
4. Run `codex-chatgpt-bridge init`.
5. Run one or more `codex-chatgpt-bridge grant ...` commands.
6. Start the bridge with `codex-chatgpt-bridge run`.
7. If ChatGPT cannot reach localhost directly, start a user-approved authenticated HTTPS tunnel.
8. Tell the user which MCP URL and HTTP Bearer token to add in ChatGPT.

## Safety Rules For Installers

- Do not grant all files by default.
- Do not grant write or execute permission unless the user asked for it.
- Do not run `codex-chatgpt-bridge enable-codex-tasks` unless the user asked for it.
- Do not expose the bridge over an unauthenticated public tunnel.
- Do not copy secrets into the config or README.
- Do not print tokens, private keys, cookies, `.env` contents, or cloud credentials.
