"""Command-line installer and server runner."""

from __future__ import annotations

import argparse
import platform
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import SplitResult, urlsplit, urlunsplit

import uvicorn

from .config import (
    BridgeConfig,
    ToolProfile,
    TrustMode,
    add_grant,
    default_config_path,
    load_config,
    save_config,
)
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
    elif args.command == "set-mode":
        _cmd_set_mode(args)
    elif args.command == "set-tool-profile":
        _cmd_set_tool_profile(args)
    elif args.command == "enable-codex-tasks":
        _cmd_set_codex_tasks(args, enabled=True)
    elif args.command == "disable-codex-tasks":
        _cmd_set_codex_tasks(args, enabled=False)
    elif args.command == "install-launch-agent":
        _cmd_install_launch_agent(args)
    elif args.command == "print-chatgpt-setup":
        _cmd_print_chatgpt_setup(args)
    elif args.command == "tunnel-doctor":
        _cmd_tunnel_doctor(args)
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

    mode = subparsers.add_parser("set-mode", help="Set restricted or full_delegate trust mode")
    mode.add_argument("mode", choices=["restricted", "full_delegate"])

    profile = subparsers.add_parser(
        "set-tool-profile",
        help="Set full or delegate tool profile for ChatGPT",
    )
    profile.add_argument("profile", choices=["full", "delegate"])

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

    tunnel_doctor = subparsers.add_parser(
        "tunnel-doctor",
        help="Diagnose ChatGPT remote MCP tunnel setup without printing connector secrets",
    )
    tunnel_doctor.add_argument(
        "--url",
        default=None,
        help="ChatGPT connector URL or tunnel base URL to inspect; secret path is redacted.",
    )
    tunnel_doctor.add_argument(
        "--log",
        action="append",
        type=Path,
        default=[],
        help="Tunnel log file to scan for connection failures; can be passed more than once.",
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
    gateway = LocalGateway(config, config_path=args.config)
    app = create_app(gateway)
    uvicorn.run(app, host=config.host, port=config.port, log_level=args.log_level)


def _cmd_doctor(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    print(f"Config: {args.config}")
    print(f"Host: {config.host}")
    print(f"Port: {config.port}")
    print(f"Trust mode: {config.trust_mode}")
    print(f"Tool profile: {config.tool_profile}")
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


def _cmd_set_mode(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    mode: TrustMode = args.mode
    save_config(config.model_copy(update={"trust_mode": mode}), args.config)
    print(f"Set bridge trust mode: {mode}")
    if mode == "full_delegate":
        print("full_delegate allows broad local read, write, and execute access via the bridge.")


def _cmd_set_tool_profile(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    profile: ToolProfile = args.profile
    save_config(config.model_copy(update={"tool_profile": profile}), args.config)
    print(f"Set ChatGPT tool profile: {profile}")
    if profile == "delegate":
        print("delegate exposes one primary Codex delegation tool plus read-only status tools.")


def _cmd_set_codex_tasks(args: argparse.Namespace, *, enabled: bool) -> None:
    config = load_config(args.config)
    save_config(config.model_copy(update={"enable_codex_tasks": enabled}), args.config)
    if enabled:
        print("Enabled Codex delegation tools. Only executable grants may run local Codex.")
    else:
        print("Disabled Codex delegation tools.")


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
    safe_bearer_url = _redact_connector_url(args.url)
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
                "2. ChatGPT web needs a stable HTTPS tunnel for local MCP. Prefer "
                "OpenAI Secure MCP Tunnel.",
                "3. If Secure MCP Tunnel is not available, use a named Cloudflare Tunnel "
                "or another stable HTTPS endpoint you control.",
                "4. Do not treat a trycloudflare.com quick tunnel as a stable install target; "
                "it is not a stable install target and is useful only for short smoke tests.",
                f"5. Bearer-protected MCP URL: {safe_bearer_url}",
                f"6. {connector_url_line}",
                "7. If ChatGPT only offers OAuth / unauthenticated / mixed auth, "
                "use the no-auth connector URL and keep it private.",
                "8. If ChatGPT supports HTTP Bearer / API key bearer, use the "
                "bearer-protected URL and paste the local token.",
                f"9. {token_line}",
                "10. In any ChatGPT conversation, mention the connector and ask it to "
                "list_grants first.",
            ]
        )
    )


def _cmd_tunnel_doctor(args: argparse.Namespace) -> None:
    url = str(args.url or "").strip()
    print("Tunnel doctor")
    print("Recommended: OpenAI Secure MCP Tunnel")
    print("Fallback: named Cloudflare Tunnel or another stable HTTPS endpoint")
    print(f"tunnel-client: {shutil.which('tunnel-client') or 'missing'}")
    print(f"cloudflared: {shutil.which('cloudflared') or 'missing'}")
    if not url:
        print("URL: missing")
    else:
        print(f"URL: {_redact_connector_url(url)}")
        parsed = _split_diagnostic_url(url)
        print(f"HTTPS: {'ok' if parsed.scheme == 'https' else 'missing'}")
        host = parsed.hostname or ""
        if host.endswith(".trycloudflare.com"):
            print("trycloudflare.com quick tunnel: unstable")
        else:
            print("trycloudflare.com quick tunnel: not detected")
        if host in {"127.0.0.1", "localhost"}:
            print("remote reachability: localhost is not reachable from ChatGPT web")
    log_text, log_issues = _read_logs(args.log)
    for issue in log_issues:
        print(issue)
    if log_text:
        connection_failed = _contains_any(
            log_text,
            [
                "Connection failed",
                "Unable to establish connection",
                "Serve tunnel error",
                "Connection terminated",
            ],
        )
        timeout_7844 = "7844" in log_text and "timeout" in log_text.lower()
        print(f"connection failures: {'found' if connection_failed else 'not found'}")
        print(f"7844 timeout: {'found' if timeout_7844 else 'not found'}")
    else:
        print("connection failures: no logs provided")
        print("7844 timeout: no logs provided")


def _connector_secret_url(base_url: str, connector_secret: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/mcp"):
        return f"{trimmed}/{connector_secret}"
    return f"{trimmed}/mcp/{connector_secret}"


def _redact_connector_url(url: str) -> str:
    parsed = _split_diagnostic_url(url)
    netloc = _safe_netloc(parsed)
    path = _redacted_url_path(parsed.path)
    if netloc:
        prefix = f"{parsed.scheme}://{netloc}" if parsed.scheme else netloc
        return f"{prefix}{path}"
    return urlunsplit((parsed.scheme, "", path, "", ""))


def _split_diagnostic_url(url: str) -> SplitResult:
    raw_url = url.strip()
    if "://" in raw_url:
        return urlsplit(raw_url)
    first_part = raw_url.split("/", 1)[0]
    if first_part in {"localhost", "127.0.0.1"} or "." in first_part or ":" in first_part:
        return urlsplit(f"//{raw_url}")
    return urlsplit(raw_url)


def _safe_netloc(parsed: SplitResult) -> str:
    host = parsed.hostname or ""
    if not host:
        return ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    try:
        port = parsed.port
    except ValueError:
        port = None
    return f"{host}:{port}" if port is not None else host


def _redacted_url_path(path: str) -> str:
    path_parts = [part for part in path.split("/") if part]
    if "mcp" in path_parts:
        mcp_index = path_parts.index("mcp")
        redacted_parts = path_parts[: mcp_index + 1]
        if len(path_parts) > mcp_index + 1:
            redacted_parts.append("[redacted]")
        redacted_path = "/" + "/".join(redacted_parts)
        return redacted_path
    if path and path != "/":
        return "/[redacted]"
    return path


def _read_logs(paths: list[Path]) -> tuple[str, list[str]]:
    chunks: list[str] = []
    issues: list[str] = []
    for path in paths:
        if not path.exists():
            issues.append(f"log missing: {path}")
            continue
        if not path.is_file():
            issues.append(f"log not readable: {path}")
            continue
        try:
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            issues.append(f"log not readable: {path}")
    return "\n".join(chunks), issues


def _contains_any(haystack: str, needles: list[str]) -> bool:
    return any(needle in haystack for needle in needles)


def _user_id() -> int:
    if hasattr(Path, "home"):
        import os

        return os.getuid()
    raise RuntimeError("cannot determine user id")


if __name__ == "__main__":
    main()
