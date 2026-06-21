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
