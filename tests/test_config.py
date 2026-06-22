from __future__ import annotations

from pathlib import Path

from codex_chatgpt_bridge.config import BridgeConfig, add_grant, load_config, save_config


def test_save_and_load_config_roundtrip(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config = add_grant(
        BridgeConfig(),
        path=tmp_path / "project",
        name="project",
        read=True,
        write=True,
        execute=True,
    )

    save_config(config, config_path)
    loaded = load_config(config_path)

    assert len(loaded.grants) == 1
    grant = loaded.grants[0]
    assert grant.name == "project"
    assert grant.read is True
    assert grant.write is True
    assert grant.execute is True
    assert grant.resolved_path == (tmp_path / "project").resolve(strict=False)
    assert loaded.auth_token
    assert loaded.enable_codex_tasks is False
    assert loaded.trust_mode == "restricted"


def test_add_grant_replaces_same_resolved_path(tmp_path: Path) -> None:
    config = BridgeConfig()

    first = add_grant(
        config,
        path=tmp_path,
        name="first",
        read=True,
        write=False,
        execute=False,
    )
    second = add_grant(
        first,
        path=tmp_path,
        name="second",
        read=True,
        write=True,
        execute=False,
    )

    assert len(second.grants) == 1
    assert second.grants[0].name == "second"
    assert second.grants[0].write is True


def test_full_delegate_trust_mode_roundtrip(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config = BridgeConfig(trust_mode="full_delegate", tool_profile="delegate")

    save_config(config, config_path)
    loaded = load_config(config_path)

    assert loaded.trust_mode == "full_delegate"
    assert loaded.tool_profile == "delegate"
