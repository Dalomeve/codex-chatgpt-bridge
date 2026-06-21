"""Configuration loading and writing for Codex ChatGPT Bridge."""

from __future__ import annotations

import tomllib
from pathlib import Path
from secrets import token_urlsafe

from pydantic import BaseModel, Field


class BridgeGrant(BaseModel):
    """One user-approved local path grant."""

    path: Path
    name: str | None = None
    read: bool = True
    write: bool = False
    execute: bool = False

    @property
    def resolved_path(self) -> Path:
        """Return the expanded, absolute path without requiring it to exist."""

        return self.path.expanduser().resolve(strict=False)


class BridgeConfig(BaseModel):
    """Runtime configuration for the local bridge."""

    host: str = "127.0.0.1"
    port: int = 8766
    auth_token: str = Field(default_factory=lambda: token_urlsafe(32))
    enable_codex_tasks: bool = False
    max_file_chars: int = 200_000
    max_write_chars: int = 400_000
    grants: list[BridgeGrant] = Field(default_factory=list)


def default_config_path() -> Path:
    """Return the per-user config path."""

    return Path.home() / ".codex-chatgpt-bridge" / "config.toml"


def default_config() -> BridgeConfig:
    """Return a secure empty config."""

    return BridgeConfig()


def load_config(path: Path | None = None) -> BridgeConfig:
    """Load bridge config from TOML, returning the secure default if missing."""

    config_path = path or default_config_path()
    if not config_path.exists():
        return default_config()
    with config_path.open("rb") as handle:
        data = tomllib.load(handle)
    return BridgeConfig.model_validate(data)


def save_config(config: BridgeConfig, path: Path | None = None) -> Path:
    """Write bridge config as TOML and return the path."""

    config_path = path or default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(_to_toml(config), encoding="utf-8")
    config_path.chmod(0o600)
    return config_path


def add_grant(
    config: BridgeConfig,
    *,
    path: Path,
    name: str | None,
    read: bool,
    write: bool,
    execute: bool,
) -> BridgeConfig:
    """Return a config with a grant added or replaced by resolved path."""

    grant = BridgeGrant(path=path, name=name, read=read, write=write, execute=execute)
    grant_path = grant.resolved_path
    grants = [item for item in config.grants if item.resolved_path != grant_path]
    grants.append(grant)
    return config.model_copy(update={"grants": grants})


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _to_toml(config: BridgeConfig) -> str:
    lines = [
        f"host = {_quote(config.host)}",
        f"port = {config.port}",
        f"auth_token = {_quote(config.auth_token)}",
        f"enable_codex_tasks = {str(config.enable_codex_tasks).lower()}",
        f"max_file_chars = {config.max_file_chars}",
        f"max_write_chars = {config.max_write_chars}",
        "",
    ]
    for grant in config.grants:
        lines.append("[[grants]]")
        lines.append(f"path = {_quote(str(grant.resolved_path))}")
        if grant.name:
            lines.append(f"name = {_quote(grant.name)}")
        lines.append(f"read = {str(grant.read).lower()}")
        lines.append(f"write = {str(grant.write).lower()}")
        lines.append(f"execute = {str(grant.execute).lower()}")
        lines.append("")
    return "\n".join(lines)
