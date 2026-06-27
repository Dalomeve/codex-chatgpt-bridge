# Codex ChatGPT Bridge

**Codex ChatGPT Bridge** is a local MCP bridge that lets ChatGPT web sessions connect to your real machine, inspect user-approved local files, and delegate local work to Codex.

It is for people who want the ChatGPT web experience to act as the researcher, planner, reviewer, or project lead, while Codex remains the local executor with access to the real working tree.

This is an unofficial local-first bridge. It is not an OpenAI API wrapper, and it does not move your project into a remote sandbox.

> Alpha status: the default mode is intentionally conservative. No local files are exposed until the user grants folders or explicitly enables full delegate mode.

## What It Can Do

- Let ChatGPT web read and search approved local project folders through MCP tools.
- Let ChatGPT web write files only inside explicitly writable grants.
- Let ChatGPT web ask local Codex to run bounded repo, shell, or GUI tasks.
- Let users choose between a safer restricted mode and a powerful full delegate mode.
- Help installers detect broken tunnels, stale ChatGPT app URLs, and unstable quick tunnels without printing secrets.

## Core Idea

ChatGPT web is often the better discussion surface for deep research, product thinking, planning, and review. Codex is often the better local executor because it can inspect and modify the actual files on your machine.

This bridge connects those two roles:

```text
ChatGPT web model
  -> MCP App / connector
  -> stable HTTPS tunnel or local endpoint
  -> Codex ChatGPT Bridge
  -> local files and local Codex
```

## One-Line Install With Codex

Ask Codex:

```text
Install https://github.com/dalomeve/codex-chatgpt-bridge on this computer.
```

That should be enough. Codex should read this README and `docs/agent-install.md`, install the bridge, create a local config, start the service, ask which folders ChatGPT may access, and help create the ChatGPT MCP app/connector.

After installation, Codex should not stop at "installed." It should verify that ChatGPT can call the bridge with `bridge_status` or `list_grants`. If browser automation is unavailable, it should give the exact manual remaining step.

## Install Manually

Use an isolated tool install:

```bash
uv tool install git+https://github.com/dalomeve/codex-chatgpt-bridge.git
```

Or clone for local development:

```bash
git clone https://github.com/dalomeve/codex-chatgpt-bridge.git
cd codex-chatgpt-bridge
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Create config and start the bridge:

```bash
codex-chatgpt-bridge init
codex-chatgpt-bridge grant ~/Projects/my-app --name my-app
codex-chatgpt-bridge run
```

Check local health:

```bash
curl http://127.0.0.1:8766/healthz
```

## ChatGPT Setup

The local MCP endpoint is:

```text
http://127.0.0.1:8766/mcp
```

If ChatGPT web cannot reach local `127.0.0.1`, expose the local bridge through a stable HTTPS tunnel and use the HTTPS URL in ChatGPT's Developer Mode app or MCP connector.

A stable tunnel is part of a successful install. A random `trycloudflare.com` quick tunnel is useful for a short smoke test, but it should not be treated as a long-term connector URL.

Recommended tunnel order:

1. OpenAI Secure MCP Tunnel, when available.
2. A named Cloudflare Tunnel or another stable, access-controlled HTTPS endpoint.
3. A temporary `trycloudflare.com` quick tunnel only for smoke tests.

The bridge supports two connector URLs:

- Bearer-protected URL: `/mcp`
- ChatGPT no-auth secret URL: `/mcp/<connector-secret>`

Use the no-auth secret URL when ChatGPT's app setup only offers OAuth, unauthenticated, or mixed auth. Treat the full secret URL as a credential.

Print setup instructions without secrets:

```bash
codex-chatgpt-bridge print-chatgpt-setup
```

Display the local bearer token and secret connector URL on your own machine:

```bash
codex-chatgpt-bridge print-chatgpt-setup --show-token
```

Diagnose a connector URL or tunnel log without printing the connector secret:

```bash
codex-chatgpt-bridge tunnel-doctor --url <connector-url> --log <tunnel-log>
```

When using ChatGPT web, type `@` and select the bridge app from the menu so it becomes a real app chip. Plain text such as `@Codex ChatGPT Bridge` is not enough.

## Typical Use Cases

Ask ChatGPT web to read local project context:

```text
@Codex ChatGPT Bridge read the README, package config, and src tree for this project.
Explain what this repo does and where the main extension points are.
```

Ask ChatGPT web to review local code and delegate fixes:

```text
@Codex ChatGPT Bridge inspect the current repo, identify the failing test, and ask local Codex to implement the smallest fix. Run the focused tests before reporting back.
```

Ask ChatGPT web to use Codex as a local device agent:

```text
@Codex ChatGPT Bridge call codex_delegate with permission_level=repo_edit.
Task: update the CLI help text, add tests, and run the test suite.
Expected result: tests pass and the diff contains only the requested change.
```

Ask ChatGPT web to drive a local GUI task, if you explicitly enabled that level:

```text
@Codex ChatGPT Bridge call codex_delegate with permission_level=gui_control.
Task: open TextEdit and type 你好.
Expected result: TextEdit is open and contains the requested text.
```

## Modes

### Restricted Mode

Restricted mode is the default. ChatGPT can only access folders the user grants:

```bash
codex-chatgpt-bridge grant ~/Projects/my-app --name my-app
codex-chatgpt-bridge grant ~/Projects/my-app --name my-app --write
codex-chatgpt-bridge grant ~/Projects/my-app --name my-app --write --execute
```

Each grant can allow:

- `read`: search and read files.
- `write`: write files through bridge tools.
- `execute`: ask local Codex to work in that directory.

Even inside grants, restricted mode blocks paths that look like secrets, including `.env`, `.ssh`, private keys, certificates, token files, and credential-like names.

### Full Delegate Mode

Full delegate mode is for a trusted personal machine where you explicitly want ChatGPT web to act as the planning brain and local Codex as the local device agent.

```bash
codex-chatgpt-bridge set-mode full_delegate
codex-chatgpt-bridge enable-codex-tasks
codex-chatgpt-bridge set-tool-profile delegate
```

In `full_delegate`, the bridge no longer requires path grants and no longer blocks sensitive-looking paths. The connector can ask the bridge to read, write, and execute anywhere the local bridge process can access. Codex session tools default to full local execution.

Use this only when the connector URL is private and you trust the ChatGPT session that will call it.

Return to safer defaults:

```bash
codex-chatgpt-bridge set-mode restricted
codex-chatgpt-bridge set-tool-profile full
codex-chatgpt-bridge disable-codex-tasks
```

## Tools

- `bridge_status`: check bridge health and available capabilities.
- `set_bridge_mode`: switch between restricted grants and full delegate mode.
- `grant_path`: add a persisted read, write, or execute grant from ChatGPT.
- `revoke_grant`: remove a persisted grant from ChatGPT.
- `list_grants`: show approved directories and permissions.
- `search_files`: search readable grants with ripgrep.
- `read_file`: read a UTF-8 text file inside a readable grant.
- `write_file`: write text inside a writable grant.
- `codex_task_run`: ask local Codex to work in an executable grant. Hidden and disabled by default.
- `codex_delegate`: hand one structured local computer, file, shell, repo, GUI, or project task to local Codex in a single MCP call.
- `codex_session_start`: start a persistent local Codex session for project work.
- `codex_session_continue`: continue a recorded local Codex session.
- `codex_session_list`: list recorded local Codex sessions.
- `codex_session_status`: inspect one recorded local Codex session.

The default tool profile is `full`, which exposes low-level file, grant, and Codex session tools. For ChatGPT web as the planning brain and local Codex as the device agent, use the `delegate` profile. It exposes one main action tool, `codex_delegate`, plus read-only status tools.

## ChatGPT Host Limits

Developer Mode and MCP app availability are account and rollout dependent. Treat the current account UI and an actual `bridge_status` tool call as the source of truth.

ChatGPT web may still block destructive custom MCP calls before they reach this bridge. If ChatGPT replies with `blocked_by_openai_safety_check` or says the tool call was blocked by OpenAI's safety check, the local bridge did not receive that request and no local Codex session was started.

## macOS Service

```bash
codex-chatgpt-bridge install-launch-agent --load
```

Logs are written to:

```text
~/Library/Logs/codex-chatgpt-bridge/
```

## Security Notes

- Do not expose this bridge to the public internet without authentication or a tunnel policy you understand.
- Do not publish the bearer token, connector secret URL, tunnel runtime key, `.env` contents, cookies, or private local paths.
- Prefer project-level grants over full-home or full-disk grants.
- Do not grant write or execute access to large directories unless you are comfortable with that risk.
- Review ChatGPT tool calls before allowing broad write or execute behavior.
- Treat `full_delegate` as device-agent mode: it is powerful enough to modify local files and run Codex on your machine.

## Development

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest
```

---

# Codex ChatGPT Bridge（中文）

**Codex ChatGPT Bridge** 是一个本地 MCP 桥，用来让 ChatGPT 网页端连接到你的真实本机，读取用户授权的本地文件，并把本地任务交给 Codex 执行。

它适合这样的工作方式：ChatGPT 网页端负责研究、规划、讨论、审查和验收；Codex 负责面对真实项目文件，执行本地修改、命令、测试或 GUI 操作。

这是一个非官方的 local-first 桥。它不是 OpenAI API 包装器，也不会把你的项目搬到远程沙盒里。

> 当前是 alpha 版本：默认模式非常保守。除非用户授权目录，或明确开启 full delegate，否则不会暴露本地文件。

## 它能做什么

- 让 ChatGPT 网页端通过 MCP 工具读取和搜索你授权的本地项目目录。
- 只在你明确给了写权限的目录里写文件。
- 让 ChatGPT 网页端把 repo、shell、GUI 或项目任务交给本地 Codex。
- 让用户在安全的 restricted 模式和强力的 full delegate 模式之间选择。
- 帮安装者诊断坏掉的 tunnel、ChatGPT app 旧 URL、以及不稳定 quick tunnel，同时不打印 secret。

## 核心思路

ChatGPT 网页端往往更适合做深度研究、产品思考、规划和验收；Codex 往往更适合做本地执行，因为它能看到并修改机器上的真实工作区。

这个桥把两者接起来：

```text
ChatGPT 网页端模型
  -> MCP App / connector
  -> 稳定 HTTPS tunnel 或本地 endpoint
  -> Codex ChatGPT Bridge
  -> 本地文件和本地 Codex
```

## 用 Codex 一句话安装

你可以直接对 Codex 说：

```text
安装 https://github.com/dalomeve/codex-chatgpt-bridge 到这台电脑。
```

这一句话就应该够了。Codex 应该自己读取本 README 和 `docs/agent-install.md`，安装 bridge，创建本地配置，启动服务，询问哪些文件夹可以开放给 ChatGPT，并帮你创建 ChatGPT MCP app/connector。

安装完成后，Codex 不应该只说“装好了”就结束。它应该继续验证 ChatGPT 能调用 `bridge_status` 或 `list_grants`。如果当前环境不能自动操作浏览器，它应该给出精确的剩余手动步骤。

## 手动安装

用独立工具安装：

```bash
uv tool install git+https://github.com/dalomeve/codex-chatgpt-bridge.git
```

或者克隆下来做本地开发：

```bash
git clone https://github.com/dalomeve/codex-chatgpt-bridge.git
cd codex-chatgpt-bridge
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

创建配置并启动：

```bash
codex-chatgpt-bridge init
codex-chatgpt-bridge grant ~/Projects/my-app --name my-app
codex-chatgpt-bridge run
```

检查本地服务：

```bash
curl http://127.0.0.1:8766/healthz
```

## 接入 ChatGPT

本地 MCP 地址是：

```text
http://127.0.0.1:8766/mcp
```

如果 ChatGPT 网页端不能直接访问本机 `127.0.0.1`，你需要用稳定的 HTTPS tunnel 暴露本地 bridge，然后在 ChatGPT Developer Mode app 或 MCP connector 里填写 HTTPS 地址。

稳定 tunnel 是安装成功条件。随机 `trycloudflare.com` quick tunnel 可以做短暂冒烟测试，但不应该当作长期 connector URL。

推荐 tunnel 顺序：

1. OpenAI Secure MCP Tunnel，如果当前账号和环境可用。
2. named Cloudflare Tunnel，或其它稳定、带访问控制的 HTTPS endpoint。
3. 临时 `trycloudflare.com` quick tunnel，只用于冒烟测试。

bridge 支持两类连接地址：

- Bearer 保护地址：`/mcp`
- ChatGPT 无认证 secret 地址：`/mcp/<connector-secret>`

如果 ChatGPT 创建 app 时只提供 OAuth、未授权或混合认证，就使用无认证 secret 地址。这个完整 URL 本身就是连接凭证，不能公开分享。

打印不含 secret 的设置说明：

```bash
codex-chatgpt-bridge print-chatgpt-setup
```

在你自己的机器上显示 bearer token 和 secret connector URL：

```bash
codex-chatgpt-bridge print-chatgpt-setup --show-token
```

诊断 connector URL 或 tunnel 日志，同时隐藏 connector secret：

```bash
codex-chatgpt-bridge tunnel-doctor --url <connector-url> --log <tunnel-log>
```

在 ChatGPT 网页端使用时，要输入 `@` 并从菜单里选中 bridge app，让它变成真正的 app chip。只打一段普通文本 `@Codex ChatGPT Bridge` 不会挂上工具。

## 典型用例

让 ChatGPT 网页端读取本地项目上下文：

```text
@Codex ChatGPT Bridge 读取这个项目的 README、包配置和 src 目录。
解释这个仓库是做什么的，以及主要扩展点在哪里。
```

让 ChatGPT 网页端审查本地代码并委托 Codex 修复：

```text
@Codex ChatGPT Bridge 检查当前 repo，找出失败测试，然后让本地 Codex 做最小修复。汇报前先运行相关测试。
```

让 ChatGPT 网页端把 Codex 当成本地设备 agent：

```text
@Codex ChatGPT Bridge 调用 codex_delegate，permission_level=repo_edit。
任务：更新 CLI help 文案、补测试、运行测试套件。
预期结果：测试通过，diff 只包含这个请求相关的改动。
```

让 ChatGPT 网页端驱动本地 GUI，如果你明确开启了对应权限：

```text
@Codex ChatGPT Bridge 调用 codex_delegate，permission_level=gui_control。
任务：打开 TextEdit 并输入“你好”。
预期结果：TextEdit 已打开，并包含指定文本。
```

## 两种模式

### Restricted 模式

Restricted 是默认模式。ChatGPT 只能访问用户授权过的目录：

```bash
codex-chatgpt-bridge grant ~/Projects/my-app --name my-app
codex-chatgpt-bridge grant ~/Projects/my-app --name my-app --write
codex-chatgpt-bridge grant ~/Projects/my-app --name my-app --write --execute
```

每个授权可以包含：

- `read`：搜索和读取文件。
- `write`：通过 bridge 工具写文件。
- `execute`：让本地 Codex 在该目录工作。

即使在授权目录内，restricted 模式也会拦截看起来像密钥的路径，例如 `.env`、`.ssh`、私钥、证书、token 文件和 credential 类文件名。

### Full Delegate 模式

Full delegate 用于你信任的个人机器：你明确希望 ChatGPT 网页端做总控大脑，本地 Codex 做本地设备 agent。

```bash
codex-chatgpt-bridge set-mode full_delegate
codex-chatgpt-bridge enable-codex-tasks
codex-chatgpt-bridge set-tool-profile delegate
```

在 `full_delegate` 下，bridge 不再要求路径 grant，也不再拦截看起来像密钥的路径。connector 可以要求 bridge 读取、写入和执行本地 bridge 进程能访问的任何路径。Codex session 工具默认使用完整本地执行。

只有在 connector URL 保密，并且你信任会调用它的 ChatGPT session 时才使用这个模式。

恢复安全默认值：

```bash
codex-chatgpt-bridge set-mode restricted
codex-chatgpt-bridge set-tool-profile full
codex-chatgpt-bridge disable-codex-tasks
```

## 可用工具

- `bridge_status`：查看 bridge 健康状态和可用能力。
- `set_bridge_mode`：在 restricted 和 full delegate 之间切换。
- `grant_path`：从 ChatGPT 添加持久化读、写或执行授权。
- `revoke_grant`：从 ChatGPT 删除持久化授权。
- `list_grants`：查看已授权目录和权限。
- `search_files`：用 ripgrep 搜索可读授权目录。
- `read_file`：读取可读授权目录内的 UTF-8 文本文件。
- `write_file`：写入可写授权目录内的文本文件。
- `codex_task_run`：让本地 Codex 在可执行授权目录中完成任务。默认隐藏且禁用。
- `codex_delegate`：用一次 MCP 调用，把结构化的本地电脑、文件、shell、repo、GUI 或项目任务交给本地 Codex。
- `codex_session_start`：启动一个可持续的本地 Codex session。
- `codex_session_continue`：继续一个已记录的本地 Codex session。
- `codex_session_list`：列出已记录的本地 Codex session。
- `codex_session_status`：查看某个本地 Codex session 状态。

默认 tool profile 是 `full`，会暴露底层文件、授权和 Codex session 工具。如果想让 ChatGPT 网页端做总控大脑、本地 Codex 做设备 agent，使用 `delegate` profile。它主要暴露 `codex_delegate`，再加少量只读状态工具。

## ChatGPT 宿主限制

Developer Mode 和 MCP app 可用性会受账号和灰度影响。最终以当前账号 UI 和一次真实 `bridge_status` 工具调用为准。

ChatGPT 网页端仍可能在请求到达 bridge 之前拦截破坏性 custom MCP 调用。如果 ChatGPT 回复 `blocked_by_openai_safety_check`，或说工具调用被 OpenAI safety check 拦截，说明本地 bridge 没收到这个请求，也没有启动本地 Codex session。

## macOS 常驻服务

```bash
codex-chatgpt-bridge install-launch-agent --load
```

日志位置：

```text
~/Library/Logs/codex-chatgpt-bridge/
```

## 安全说明

- 不要在没有认证或可信 tunnel 策略的情况下，把 bridge 直接暴露到公网。
- 不要公开 bearer token、connector secret URL、tunnel runtime key、`.env` 内容、cookies 或私人本地路径。
- 优先给单个项目目录授权，而不是给整个 home 或全盘授权。
- 不要轻易给大目录开启写入或执行权限。
- 在开启大范围写入或执行权限前，认真审查 ChatGPT 的工具调用。
- 把 `full_delegate` 当作设备 agent 模式：它足够强，可以修改本地文件，并在你的机器上运行 Codex。

## 开发

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest
```
