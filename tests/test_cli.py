from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from codex_chatgpt_bridge.cli import main
from codex_chatgpt_bridge.config import BridgeConfig, load_config, save_config


def test_cli_set_mode_updates_config(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_path = tmp_path / "config.toml"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-chatgpt-bridge",
            "--config",
            str(config_path),
            "set-mode",
            "full_delegate",
        ],
    )

    main()

    loaded = load_config(config_path)
    captured = capsys.readouterr()
    assert loaded.trust_mode == "full_delegate"
    assert "full_delegate" in captured.out


def test_cli_set_tool_profile_updates_config(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_path = tmp_path / "config.toml"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-chatgpt-bridge",
            "--config",
            str(config_path),
            "set-tool-profile",
            "delegate",
        ],
    )

    main()

    loaded = load_config(config_path)
    captured = capsys.readouterr()
    assert loaded.tool_profile == "delegate"
    assert "delegate" in captured.out


def test_cli_run_passes_config_path_to_gateway(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import codex_chatgpt_bridge.cli as cli

    config_path = tmp_path / "config.toml"
    save_config(BridgeConfig(), config_path)
    captured: dict[str, Any] = {}

    class FakeGateway:
        def __init__(self, config: BridgeConfig, *, config_path: Path) -> None:
            captured["config"] = config
            captured["config_path"] = config_path

    monkeypatch.setattr(cli, "LocalGateway", FakeGateway)
    monkeypatch.setattr(cli, "create_app", lambda gateway: {"gateway": gateway})
    monkeypatch.setattr(cli.uvicorn, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-chatgpt-bridge",
            "--config",
            str(config_path),
            "run",
        ],
    )

    main()

    assert captured["config_path"] == config_path


def test_print_chatgpt_setup_prioritizes_stable_tunnels(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_path = tmp_path / "config.toml"
    save_config(BridgeConfig(), config_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-chatgpt-bridge",
            "--config",
            str(config_path),
            "print-chatgpt-setup",
        ],
    )

    main()

    captured = capsys.readouterr()
    assert "OpenAI Secure MCP Tunnel" in captured.out
    assert "named Cloudflare Tunnel" in captured.out
    assert "trycloudflare.com quick tunnel" in captured.out
    assert "not a stable install target" in captured.out


def test_tunnel_doctor_redacts_secret_urls_and_reports_unstable_tunnel(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    log_path = tmp_path / "cloudflared.err.log"
    log_path.write_text(
        "ERR Unable to establish connection with Cloudflare edge "
        'error="DialContext error: dial tcp 203.0.113.10:7844: i/o timeout"\n'
        "ERR Connection failed\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-chatgpt-bridge",
            "tunnel-doctor",
            "--url",
            "https://old-random-name.trycloudflare.com/mcp/super-secret-path",
            "--log",
            str(log_path),
        ],
    )

    main()

    captured = capsys.readouterr()
    assert "https://old-random-name.trycloudflare.com/mcp/[redacted]" in captured.out
    assert "trycloudflare.com quick tunnel: unstable" in captured.out
    assert "connection failures: found" in captured.out
    assert "7844 timeout: found" in captured.out
    assert "super-secret-path" not in captured.out


def test_tunnel_doctor_redacts_userinfo_query_fragment_and_opaque_path(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-chatgpt-bridge",
            "tunnel-doctor",
            "--url",
            "https://user:pass@bridge.example.com/tunnel-secret?token=query-secret#frag",
        ],
    )

    main()

    captured = capsys.readouterr()
    assert "https://bridge.example.com/[redacted]" in captured.out
    assert "user:pass" not in captured.out
    assert "tunnel-secret" not in captured.out
    assert "query-secret" not in captured.out
    assert "frag" not in captured.out


def test_tunnel_doctor_detects_quick_tunnel_without_scheme(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-chatgpt-bridge",
            "tunnel-doctor",
            "--url",
            "old-random-name.trycloudflare.com/mcp/super-secret-path",
        ],
    )

    main()

    captured = capsys.readouterr()
    assert "old-random-name.trycloudflare.com/mcp/[redacted]" in captured.out
    assert "HTTPS: missing" in captured.out
    assert "trycloudflare.com quick tunnel: unstable" in captured.out
    assert "super-secret-path" not in captured.out


def test_print_chatgpt_setup_redacts_supplied_url_without_show_token(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_path = tmp_path / "config.toml"
    save_config(BridgeConfig(), config_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-chatgpt-bridge",
            "--config",
            str(config_path),
            "print-chatgpt-setup",
            "--url",
            "https://user:pass@bridge.example.com/mcp?token=query-secret#frag",
        ],
    )

    main()

    captured = capsys.readouterr()
    assert "Bearer-protected MCP URL: https://bridge.example.com/mcp" in captured.out
    assert "user:pass" not in captured.out
    assert "query-secret" not in captured.out
    assert "frag" not in captured.out


def test_tunnel_doctor_reports_missing_and_unreadable_logs(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    missing_log = tmp_path / "missing.log"
    unreadable_log = tmp_path / "log-directory"
    unreadable_log.mkdir()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-chatgpt-bridge",
            "tunnel-doctor",
            "--url",
            "https://bridge.example.com/mcp",
            "--log",
            str(missing_log),
            "--log",
            str(unreadable_log),
        ],
    )

    main()

    captured = capsys.readouterr()
    assert f"log missing: {missing_log}" in captured.out
    assert f"log not readable: {unreadable_log}" in captured.out
