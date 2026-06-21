from __future__ import annotations

from pathlib import Path

from codex_chatgpt_bridge.security import is_relative_to, is_sensitive_path, resolve_user_path


def test_resolve_user_path_expands_relative_to_home() -> None:
    resolved = resolve_user_path("Documents")

    assert resolved == (Path.home() / "Documents").resolve(strict=False)


def test_is_relative_to_accepts_nested_path(tmp_path: Path) -> None:
    parent = tmp_path / "root"
    child = parent / "nested" / "file.txt"

    assert is_relative_to(child, parent) is True
    assert is_relative_to(tmp_path / "elsewhere.txt", parent) is False


def test_sensitive_path_detects_secret_files() -> None:
    assert is_sensitive_path(Path.home() / ".ssh" / "id_rsa") is True
    assert is_sensitive_path(Path.home() / "project" / ".env") is True
    assert is_sensitive_path(Path.home() / "project" / ".env.development") is True
    assert is_sensitive_path(Path.home() / "project" / ".envrc") is True
    assert is_sensitive_path(Path.home() / "project" / ".pypirc") is True
    assert is_sensitive_path(Path.home() / "project" / "api_key.txt") is True
    assert is_sensitive_path(Path.home() / "project" / "notes.md") is False
