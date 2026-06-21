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

## Quick Start With Codex

Ask Codex:

```text
Install https://github.com/dalomeve/codex-chatgpt-bridge on this computer.
Create a secure default config.
Grant read access to ~/Documents and read/write/execute access to ~/Projects.
Only enable local Codex task execution if I explicitly ask for it.
Install it as a local service if possible.
Then print the ChatGPT MCP connector setup URL and safety summary.
```

Codex should clone the repo, install the package, create the config, add your grants, and help you connect it to ChatGPT.

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

If ChatGPT cannot reach local `127.0.0.1` from the web UI, expose the local server through a tunnel you trust, then use the HTTPS `/mcp` URL in ChatGPT's connector/app setup.

Do not expose the bridge through a public URL without bearer-token auth. The bridge requires an HTTP Bearer token generated in the local config. To print setup instructions:

```bash
codex-chatgpt-bridge print-chatgpt-setup
```

To display the local token on your own machine:

```bash
codex-chatgpt-bridge print-chatgpt-setup --show-token
```

If you use a tunnel, prefer a named/authenticated tunnel or another access-controlled tunnel you understand. Then add the generated HTTPS URL with `/mcp` appended and configure ChatGPT auth as HTTP Bearer / bearer API key.

## Tools

- `bridge_status`: check bridge health and available capabilities.
- `list_grants`: show approved directories and permissions.
- `search_files`: search readable grants with ripgrep.
- `read_file`: read a UTF-8 text file inside a readable grant.
- `write_file`: write text inside a writable grant.
- `codex_task_run`: ask local Codex to work in an executable grant. This tool is hidden and disabled by default.

## Permission Model

Access is denied by default. The user grants directories:

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
创建安全默认配置。
给 ~/Documents 只读权限，给 ~/Projects 读写和执行权限。
只有在我明确要求时，才开启本地 Codex 任务执行。
如果系统支持，把它安装成本地常驻服务。
最后告诉我 ChatGPT MCP 连接地址和安全边界。
```

Codex 应该完成 clone、安装、初始化配置、添加授权目录、启动服务，并指导你把它接到 ChatGPT。

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

如果 ChatGPT 网页端不能直接访问本机 `127.0.0.1`，你需要用自己信任的 tunnel 暴露本地服务，然后在 ChatGPT 的 connector/app 设置里填写 HTTPS `/mcp` 地址。

不要把这个桥用无认证公网 URL 裸露出去。桥默认要求本地配置生成的 HTTP Bearer token。打印设置说明：

```bash
codex-chatgpt-bridge print-chatgpt-setup
```

在本机显示 token：

```bash
codex-chatgpt-bridge print-chatgpt-setup --show-token
```

如果使用 tunnel，优先使用 named/authenticated tunnel 或其它你理解的访问控制方式。然后把生成的 HTTPS 地址后面加上 `/mcp`，并在 ChatGPT 里把认证方式设为 HTTP Bearer / bearer API key。

## 可用工具

- `bridge_status`：查看桥是否在线。
- `list_grants`：查看用户授权的目录和权限。
- `search_files`：用 ripgrep 搜索可读授权目录。
- `read_file`：读取可读授权目录内的 UTF-8 文本文件。
- `write_file`：写入可写授权目录内的文本文件。
- `codex_task_run`：让本地 Codex 在可执行授权目录中完成一个任务。这个工具默认隐藏且禁用。

## 权限模型

默认拒绝访问。用户必须显式授权目录：

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

## 开发

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest
```
