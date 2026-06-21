# Codex ChatGPT Bridge

**Codex ChatGPT Bridge** is a local MCP bridge that lets ChatGPT web sessions use approved local context and hand bounded tasks to local Codex.

It is built for people who want ChatGPT's web-side model experience and Codex's local execution ability to work together without moving their project files into a remote sandbox.

> Alpha status: this project is intentionally small and security-first. It defaults to no local file access until the user grants directories.

## Why

ChatGPT web is often the better researcher, planner, and discussion surface. Codex is often the better local executor because it can inspect and modify a real working tree. This bridge gives ChatGPT a controlled way to:

- see user-approved local files;
- search approved folders;
- write only inside explicitly writable grants;
- ask local Codex to run a bounded task in an explicitly executable directory.

## One-Line Install With Codex

Ask Codex:

```text
Install https://github.com/dalomeve/codex-chatgpt-bridge on this computer.
```

That should be enough. Codex should read this README and `docs/agent-install.md`, install the bridge, create a secure config, avoid broad permissions by default, and then ask you which folders to grant.

After installation, Codex should not stop at "installed." It should ask which local
project or folders ChatGPT may access, apply those grants, then try to open
ChatGPT in the browser and add the MCP connector for you. If browser automation
is unavailable, it should fall back to clear manual steps.

## Manual Install

```bash
git clone https://github.com/dalomeve/codex-chatgpt-bridge.git
cd codex-chatgpt-bridge
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
codex-chatgpt-bridge init
codex-chatgpt-bridge grant ~/Documents --name documents
codex-chatgpt-bridge grant ~/Projects --name projects --write
codex-chatgpt-bridge run
```

Check it:

```bash
curl http://127.0.0.1:8766/healthz
```

## ChatGPT Setup

The MCP endpoint is:

```text
http://127.0.0.1:8766/mcp
```

If ChatGPT cannot reach local `127.0.0.1` from the web UI, expose the local server through a tunnel you trust, then use the HTTPS URL in ChatGPT's connector/app setup.

The bridge supports two connector URLs:

- Bearer-protected URL: `/mcp`
- ChatGPT no-auth secret URL: `/mcp/<connector-secret>`

Use the no-auth secret URL when ChatGPT's app setup only offers OAuth / unauthenticated / mixed auth. Keep that URL private because the secret path is the connector credential.

To print setup instructions:

```bash
codex-chatgpt-bridge print-chatgpt-setup
```

To display local secrets on your own machine:

```bash
codex-chatgpt-bridge print-chatgpt-setup --show-token
```

If you use a tunnel, prefer a named/authenticated tunnel or another access-controlled tunnel you understand. Then add either `/mcp` for bearer auth or `/mcp/<connector-secret>` for ChatGPT's unauthenticated connector mode.

## Tools

- `bridge_status`: check bridge health and available capabilities.
- `set_bridge_mode`: switch between restricted grants and full delegate mode.
- `grant_path`: add a persisted read/write/execute grant from ChatGPT.
- `revoke_grant`: remove a persisted grant from ChatGPT.
- `list_grants`: show approved directories and permissions.
- `search_files`: search readable grants with ripgrep.
- `read_file`: read a UTF-8 text file inside a readable grant.
- `write_file`: write text inside a writable grant.
- `codex_task_run`: ask local Codex to work in an executable grant. This tool is hidden and disabled by default.
- `codex_session_start`: start a persistent local Codex session for project work.
- `codex_session_continue`: continue a recorded local Codex session.
- `codex_session_list`: list recorded local Codex sessions.
- `codex_session_status`: inspect one recorded local Codex session.

## Permission Model

Access is denied by default. The default trust mode is `restricted`, where the user grants directories:

```bash
codex-chatgpt-bridge grant ~/Documents --name documents
codex-chatgpt-bridge grant ~/Projects/my-app --name my-app --write
```

Each grant has three independent permissions:

- `read`: ChatGPT can search and read files.
- `write`: ChatGPT can write files through bridge tools.
- `execute`: ChatGPT can hand a task to local Codex in that directory.

Local Codex execution is a separate high-risk switch:

```bash
codex-chatgpt-bridge grant ~/Projects/my-app --name my-app --write --execute
codex-chatgpt-bridge enable-codex-tasks
```

Use it only for directories where you are comfortable letting ChatGPT prompt local Codex. Disable it again with:

```bash
codex-chatgpt-bridge disable-codex-tasks
```

Even inside approved grants, the bridge refuses paths that look like secrets, including `.env`, `.ssh`, private keys, certificates, token files, and credential-like names.

### Full Delegate Mode

For a personal machine where you explicitly want ChatGPT web to act as the planning brain and local Codex as the device agent, switch the bridge into full delegate mode:

```bash
codex-chatgpt-bridge set-mode full_delegate
codex-chatgpt-bridge enable-codex-tasks
```

In `full_delegate` mode, the bridge no longer requires path grants and no longer blocks sensitive-looking paths. The connector can ask the bridge to read, write, and execute anywhere the local bridge process can access. Codex session tools default to `danger_full_access`, which runs local Codex without approval prompts or sandboxing.

Use this only when the connector URL is private and you intentionally trust the ChatGPT session that will call it. To return to the safer default:

```bash
codex-chatgpt-bridge set-mode restricted
codex-chatgpt-bridge disable-codex-tasks
```

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
- Do not grant write or execute permission to large directories unless you are comfortable with that risk.
- Prefer project-level grants over full-home or full-disk grants.
- Review ChatGPT tool calls before allowing broad write or execute behavior.
- Keep `codex_task_run` disabled unless you explicitly need local Codex execution from ChatGPT.
- Treat `full_delegate` as device-agent mode: it is powerful enough to modify files and run Codex on your local machine.

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

**Codex ChatGPT Bridge** 是一个本地 MCP 桥，用来把 ChatGPT 网页端的模型能力和本机 Codex 的本地执行能力接起来。

它适合这样的场景：你希望 ChatGPT 网页端负责研究、规划、讨论和领导任务，但又希望它能读取你授权的本地文件，并把具体工程任务交给本地 Codex 执行。

> 当前是 alpha 版本：默认不开放任何本地文件权限，必须由用户显式授权目录。

## 为什么需要它

ChatGPT 网页端经常更适合做研究员、规划者和对话入口；Codex 更适合做本地执行者，因为它能直接面对真实工作区。这个桥让 ChatGPT 可以在受控权限下：

- 查看用户授权的本地文件；
- 搜索授权目录；
- 只在明确授权可写的目录里写文件；
- 只在明确授权可执行的目录里，把任务交给本地 Codex。

## 用 Codex 一句话安装

你可以直接对 Codex 说：

```text
安装 https://github.com/dalomeve/codex-chatgpt-bridge 到这台电脑。
```

这一句话就应该够了。Codex 应该自己读取本 README 和 `docs/agent-install.md`，安装本地桥，创建安全配置，默认不乱开大权限，然后再问你要授权哪些文件夹。

安装完成后，Codex 不应该只说“装好了”就结束。它应该继续问你要把哪个本地项目或文件夹开放给 ChatGPT，按你的回答添加授权，然后尝试打开 ChatGPT 网页端，帮你创建 MCP connector。如果当前环境不能操作浏览器，再退回到清晰的手动步骤。

## 手动安装

```bash
git clone https://github.com/dalomeve/codex-chatgpt-bridge.git
cd codex-chatgpt-bridge
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
codex-chatgpt-bridge init
codex-chatgpt-bridge grant ~/Documents --name documents
codex-chatgpt-bridge grant ~/Projects --name projects --write
codex-chatgpt-bridge run
```

检查服务：

```bash
curl http://127.0.0.1:8766/healthz
```

## 接入 ChatGPT

本地 MCP 地址是：

```text
http://127.0.0.1:8766/mcp
```

如果 ChatGPT 网页端不能直接访问本机 `127.0.0.1`，你需要用自己信任的 tunnel 暴露本地服务，然后在 ChatGPT 的 connector/app 设置里填写 HTTPS 地址。

桥支持两类连接地址：

- Bearer 保护地址：`/mcp`
- ChatGPT 无认证 secret 地址：`/mcp/<connector-secret>`

如果 ChatGPT 创建应用时只提供 OAuth / 未授权 / 混合认证，就使用无认证 secret 地址。这个 URL 本身就是连接凭证，不能公开分享。

打印设置说明：

```bash
codex-chatgpt-bridge print-chatgpt-setup
```

在本机显示连接 secret：

```bash
codex-chatgpt-bridge print-chatgpt-setup --show-token
```

如果使用 tunnel，优先使用 named/authenticated tunnel 或其它你理解的访问控制方式。然后根据 ChatGPT 支持的认证方式，使用 `/mcp` 或 `/mcp/<connector-secret>`。

## 可用工具

- `bridge_status`：查看桥是否在线。
- `set_bridge_mode`：在 restricted 授权模式和 full delegate 模式之间切换。
- `grant_path`：让 ChatGPT 添加持久化读/写/执行授权。
- `revoke_grant`：让 ChatGPT 删除持久化授权。
- `list_grants`：查看用户授权的目录和权限。
- `search_files`：用 ripgrep 搜索可读授权目录。
- `read_file`：读取可读授权目录内的 UTF-8 文本文件。
- `write_file`：写入可写授权目录内的文本文件。
- `codex_task_run`：让本地 Codex 在可执行授权目录中完成一个任务。这个工具默认隐藏且禁用。
- `codex_session_start`：启动一个可持续的本地 Codex session。
- `codex_session_continue`：继续一个已记录的本地 Codex session。
- `codex_session_list`：列出桥记录的本地 Codex session。
- `codex_session_status`：查看某个本地 Codex session 的状态。

## 权限模型

默认拒绝访问。默认 trust mode 是 `restricted`，用户必须显式授权目录：

```bash
codex-chatgpt-bridge grant ~/Documents --name documents
codex-chatgpt-bridge grant ~/Projects/my-app --name my-app --write
```

每个目录有三个独立权限：

- `read`：ChatGPT 可以搜索和读取文件。
- `write`：ChatGPT 可以通过桥写文件。
- `execute`：ChatGPT 可以把任务交给本地 Codex 在该目录运行。

本地 Codex 执行是单独的高风险开关：

```bash
codex-chatgpt-bridge grant ~/Projects/my-app --name my-app --write --execute
codex-chatgpt-bridge enable-codex-tasks
```

只有当你确实希望 ChatGPT 能提示本地 Codex 工作时才开启。关闭命令：

```bash
codex-chatgpt-bridge disable-codex-tasks
```

即使在授权目录内，桥也会拒绝看起来像密钥或凭证的路径，例如 `.env`、`.ssh`、私钥、证书、token 文件和 credential 类文件名。

### Full Delegate 模式

如果这是你自己的机器，并且你明确希望 ChatGPT 网页端做总控大脑、本地 Codex 做设备 agent，可以切到 full delegate：

```bash
codex-chatgpt-bridge set-mode full_delegate
codex-chatgpt-bridge enable-codex-tasks
```

在 `full_delegate` 下，桥不再要求路径 grant，也不再拦截看起来像密钥的路径。connector 可以要求桥读取、写入、执行本地 bridge 进程能访问的任何路径。Codex session 工具默认使用 `danger_full_access`，也就是让本地 Codex 不经审批、无沙盒执行。

只有在 connector URL 保密，并且你信任会调用它的 ChatGPT session 时才使用这个模式。恢复安全默认值：

```bash
codex-chatgpt-bridge set-mode restricted
codex-chatgpt-bridge disable-codex-tasks
```

## macOS 常驻服务

```bash
codex-chatgpt-bridge install-launch-agent --load
```

日志位置：

```text
~/Library/Logs/codex-chatgpt-bridge/
```

## 安全说明

- 不要在没有认证或可信 tunnel 策略的情况下，把这个桥直接暴露到公网。
- 不要轻易给大目录开启写入或执行权限。
- 优先给单个项目目录授权，而不是给整个 home 或全盘授权。
- 在开启大范围写入或执行权限前，认真审查 ChatGPT 的工具调用。
- 除非确实需要 ChatGPT 调本地 Codex，否则保持 `codex_task_run` 禁用。
- 把 `full_delegate` 当作设备 agent 模式看待：它足够强，可以修改本地文件并驱动本地 Codex。

## 开发

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest
```
