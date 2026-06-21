"""Command-line installer and server runner."""

from __future__ import annotations

import argparse
import platform
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

import uvicorn

from .config import BridgeConfig, add_grant, default_config_path, load_config, save_config
from .gateway import LocalGateway
from .mcp import create_app


def main() -> None:
    """CLI entrypoint."""

    parser = _build_parser()
    args = parser.parse_args()
    if args.command == "init":
        _cmd_init(args)
    elif args.command == "grant":
        _cmd_grant(args)
    elif args.command == "run":
        _cmd_run(args)
    elif args.command == "doctor":
        _cmd_doctor(args)
    elif args.command == "enable-codex-tasks":
        _cmd_set_codex_tasks(args, enabled=True)
    elif args.command == "disable-codex-tasks":
        _cmd_set_codex_tasks(args, enabled=False)
    elif args.command == "install-launch-agent":
        _cmd_install_launch_agent(args)
    elif args.command == "print-chatgpt-setup":
        _cmd_print_chatgpt_setup(args)
    else:
        parser.print_help()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codex-chatgpt-bridge",
        description="Install and run a local bridge between ChatGPT web sessions and local Codex.",
    )
    parser.add_argument("--config", type=Path, default=default_config_path())
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="Create a secure empty config file")

    grant = subparsers.add_parser("grant", help="Add or replace a user-approved local path grant")
    grant.add_argument("path", type=Path)
    grant.add_argument("--name", default=None)
    grant.add_argument("--no-read", action="store_true")
    grant.add_argument("--write", action="store_true")
    grant.add_argument("--execute", action="store_true")

    run = subparsers.add_parser("run", help="Run the local MCP server")
    run.add_argument("--host", default=None)
    run.add_argument("--port", type=int, default=None)
    run.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"])

    subparsers.add_parser("doctor", help="Check config and local dependencies")

    subparsers.add_parser(
        "enable-codex-tasks",
        help="Expose codex_task_run after the user understands the local execution risk",
    )
    subparsers.add_parser("disable-codex-tasks", help="Hide and disable codex_task_run")

    launch = subparsers.add_parser("install-launch-agent", help="Install a macOS launchd service")
    launch.add_argument("--label", default="com.codex-chatgpt-bridge")
    launch.add_argument(
        "--load",
        action="store_true",
        help="Load and start the service after writing it",
    )

    setup = subparsers.add_parser("print-chatgpt-setup", help="Print ChatGPT connector setup text")
    setup.add_argument("--url", default="http://127.0.0.1:8766/mcp")
    setup.add_argument(
        "--show-token",
        action="store_true",
        help="Print the local bearer token needed by ChatGPT connector setup",
    )
    return parser


def _cmd_init(args: argparse.Namespace) -> None:
    path = save_config(BridgeConfig(), args.config)
    print(f"Created secure empty config: {path}")
    print("Next: codex-chatgpt-bridge grant ~/Projects --write --execute")


def _cmd_grant(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    updated = add_grant(
        config,
        path=args.path,
        name=args.name,
        read=not args.no_read,
        write=bool(args.write),
        execute=bool(args.execute),
    )
    path = save_config(updated, args.config)
    print(f"Updated config: {path}")
    print(f"Granted: {args.path.expanduser().resolve(strict=False)}")


def _cmd_run(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port
    gateway = LocalGateway(config)
    app = create_app(gateway)
    uvicorn.run(app, host=config.host, port=config.port, log_level=args.log_level)


def _cmd_doctor(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    print(f"Config: {args.config}")
    print(f"Host: {config.host}")
    print(f"Port: {config.port}")
    print(f"Auth token: {'configured' if config.auth_token else 'missing'}")
    print(f"Codex tasks: {'enabled' if config.enable_codex_tasks else 'disabled'}")
    print(f"Grants: {len(config.grants)}")
    for grant in config.grants:
        status = "exists" if grant.resolved_path.exists() else "missing"
        print(
            f"- {grant.resolved_path} [{status}] "
            f"read={grant.read} write={grant.write} execute={grant.execute}"
        )
    print(f"codex: {shutil.which('codex') or 'missing'}")
    print(f"rg: {shutil.which('rg') or 'missing'}")
    print(f"cloudflared: {shutil.which('cloudflared') or 'optional, missing'}")


def _cmd_set_codex_tasks(args: argparse.Namespace, *, enabled: bool) -> None:
    config = load_config(args.config)
    save_config(config.model_copy(update={"enable_codex_tasks": enabled}), args.config)
    if enabled:
        print("Enabled codex_task_run. Only grants with execute=true may run local Codex.")
    else:
        print("Disabled codex_task_run.")


def _cmd_install_launch_agent(args: argparse.Namespace) -> None:
    if platform.system() != "Darwin":
        raise SystemExit("install-launch-agent currently supports macOS launchd only")
    executable = shutil.which("codex-chatgpt-bridge") or str(Path(sys.argv[0]).resolve())
    label = str(args.label)
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
    log_dir = Path.home() / "Library" / "Logs" / "codex-chatgpt-bridge"
    log_dir.mkdir(parents=True, exist_ok=True)
    plist = {
        "Label": label,
        "ProgramArguments": [
            executable,
            "--config",
            str(args.config),
            "run",
        ],
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(log_dir / "bridge.out.log"),
        "StandardErrorPath": str(log_dir / "bridge.err.log"),
        "EnvironmentVariables": {
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        },
    }
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    with plist_path.open("wb") as handle:
        plistlib.dump(plist, handle)
    print(f"Wrote launch agent: {plist_path}")
    if args.load:
        uid = str(_user_id())
        subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(plist_path)], check=False)
        subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)], check=True)
        subprocess.run(["launchctl", "enable", f"gui/{uid}/{label}"], check=True)
        subprocess.run(["launchctl", "kickstart", "-k", f"gui/{uid}/{label}"], check=True)
        print(f"Started launch agent: {label}")
    else:
        print(f"Load it with: launchctl bootstrap gui/$(id -u) {plist_path}")


def _cmd_print_chatgpt_setup(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    connector_url = _connector_secret_url(args.url, config.connector_secret)
    token_line = (
        f"Bearer token: {config.auth_token}"
        if args.show_token
        else "Bearer token: stored in config; rerun with --show-token to display it locally."
    )
    connector_url_line = (
        f"ChatGPT no-auth connector URL: {connector_url}"
        if args.show_token
        else (
            "ChatGPT no-auth connector URL: stored in config; rerun with "
            "--show-token to display it locally."
        )
    )
    print(
        "\n".join(
            [
                "ChatGPT connector setup",
                "1. Start the bridge: codex-chatgpt-bridge run",
                "2. If ChatGPT needs HTTPS, run a trusted tunnel to the local port.",
                f"3. Bearer-protected MCP URL: {args.url}",
                f"4. {connector_url_line}",
                "5. If ChatGPT only offers OAuth / unauthenticated / mixed auth, "
                "use the no-auth connector URL and keep it private.",
                "6. If ChatGPT supports HTTP Bearer / API key bearer, use the "
                "bearer-protected URL and paste the local token.",
                f"7. {token_line}",
                "8. In any ChatGPT conversation, mention the connector and ask it to "
                "list_grants first.",
            ]
        )
    )


def _connector_secret_url(base_url: str, connector_secret: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/mcp"):
        return f"{trimmed}/{connector_secret}"
    return f"{trimmed}/mcp/{connector_secret}"


def _user_id() -> int:
    if hasattr(Path, "home"):
        import os

        return os.getuid()
    raise RuntimeError("cannot determine user id")


if __name__ == "__main__":
    main()
