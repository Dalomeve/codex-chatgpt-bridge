from __future__ import annotations

from pathlib import Path

import pytest

from codex_chatgpt_bridge.config import BridgeConfig, BridgeGrant, load_config
from codex_chatgpt_bridge.gateway import BridgeError, LocalGateway


@pytest.mark.asyncio
async def test_read_file_requires_read_grant(tmp_path: Path) -> None:
    approved = tmp_path / "approved"
    approved.mkdir()
    note = approved / "note.md"
    note.write_text("hello bridge", encoding="utf-8")
    gateway = LocalGateway(
        BridgeConfig(grants=[BridgeGrant(path=approved, read=True, write=False, execute=False)])
    )

    result = await gateway.read_file(path=str(note))

    assert result["text"] == "hello bridge"


@pytest.mark.asyncio
async def test_read_file_denies_outside_grant(tmp_path: Path) -> None:
    gateway = LocalGateway(BridgeConfig(grants=[BridgeGrant(path=tmp_path / "approved")]))

    with pytest.raises(BridgeError, match="not inside an approved grant"):
        await gateway.read_file(path=str(tmp_path / "outside.txt"))


@pytest.mark.asyncio
async def test_write_file_requires_write_grant(tmp_path: Path) -> None:
    approved = tmp_path / "approved"
    approved.mkdir()
    read_only = LocalGateway(
        BridgeConfig(grants=[BridgeGrant(path=approved, read=True, write=False, execute=False)])
    )

    with pytest.raises(BridgeError, match="write is not allowed"):
        await read_only.write_file(path=str(approved / "new.txt"), content="nope")

    writable = LocalGateway(
        BridgeConfig(grants=[BridgeGrant(path=approved, read=True, write=True, execute=False)])
    )
    result = await writable.write_file(path=str(approved / "new.txt"), content="ok")

    assert result["bytes"] == 2
    assert (approved / "new.txt").read_text(encoding="utf-8") == "ok"


@pytest.mark.asyncio
async def test_full_delegate_can_read_and_write_outside_grants(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    secret_named = outside / ".env"
    secret_named.write_text("full access", encoding="utf-8")
    gateway = LocalGateway(BridgeConfig(trust_mode="full_delegate", grants=[]))

    read_result = await gateway.read_file(path=str(secret_named))
    write_result = await gateway.write_file(path=str(outside / "new.txt"), content="ok")

    assert read_result["text"] == "full access"
    assert write_result["bytes"] == 2
    assert (outside / "new.txt").read_text(encoding="utf-8") == "ok"


@pytest.mark.asyncio
async def test_runtime_mode_and_grant_tools_persist_to_config(tmp_path: Path) -> None:
    config_path = tmp_path / "bridge.toml"
    grant_path = tmp_path / "project"
    grant_path.mkdir()
    gateway = LocalGateway(BridgeConfig(), config_path=config_path)

    mode_result = await gateway.set_bridge_mode(mode="full_delegate")
    grant_result = await gateway.grant_path(
        path=str(grant_path),
        name="project",
        read=True,
        write=True,
        execute=True,
    )
    revoke_result = await gateway.revoke_grant(path=str(grant_path))

    loaded = load_config(config_path)
    assert mode_result["trust_mode"] == "full_delegate"
    assert grant_result["grant"]["write"] is True
    assert revoke_result["removed"] is True
    assert loaded.trust_mode == "full_delegate"
    assert loaded.grants == []


@pytest.mark.asyncio
async def test_grant_path_defaults_to_read_only(tmp_path: Path) -> None:
    grant_path = tmp_path / "project"
    grant_path.mkdir()
    gateway = LocalGateway(BridgeConfig())

    result = await gateway.grant_path(path=str(grant_path))

    assert result["grant"]["read"] is True
    assert result["grant"]["write"] is False
    assert result["grant"]["execute"] is False


@pytest.mark.asyncio
async def test_codex_task_run_requires_execute_grant(tmp_path: Path) -> None:
    gateway = LocalGateway(
        BridgeConfig(
            enable_codex_tasks=True,
            grants=[BridgeGrant(path=tmp_path, read=True, write=True, execute=False)],
        )
    )

    with pytest.raises(BridgeError, match="execute is not allowed"):
        await gateway.codex_task_run(prompt="say hi", cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_codex_task_run_disabled_by_default(tmp_path: Path) -> None:
    gateway = LocalGateway(
        BridgeConfig(grants=[BridgeGrant(path=tmp_path, read=True, write=True, execute=True)])
    )

    with pytest.raises(BridgeError, match="disabled"):
        await gateway.codex_task_run(prompt="say hi", cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_codex_session_start_records_persistent_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = LocalGateway(
        BridgeConfig(trust_mode="full_delegate", enable_codex_tasks=True),
        session_store_path=tmp_path / "sessions.json",
    )
    commands: list[list[str]] = []

    async def fake_run_codex_command(
        command: list[str],
        output_path: Path,
        wait_timeout_s: float,
        cwd: Path,
    ) -> tuple[int, str, str]:
        commands.append(command)
        output_path.write_text("done", encoding="utf-8")
        return (
            0,
            '{"type":"session_configured","session_id":"019ee9e9-ecb8-72e3-a495-43674e1d7576"}\n',
            "",
        )

    monkeypatch.setattr(gateway, "_run_codex_command", fake_run_codex_command)
    monkeypatch.setattr(gateway, "_codex_path", lambda: "/usr/local/bin/codex")

    result = await gateway.codex_session_start(prompt="inspect repo", cwd=str(tmp_path))

    assert result["codex_session_id"] == "019ee9e9-ecb8-72e3-a495-43674e1d7576"
    assert result["final_message"] == "done"
    assert commands[0][1] == "exec"
    assert "--dangerously-bypass-approvals-and-sandbox" in commands[0]
    sessions = await gateway.codex_session_list()
    assert sessions["sessions"][0]["codex_session_id"] == result["codex_session_id"]


@pytest.mark.asyncio
async def test_codex_session_continue_resumes_latest_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = LocalGateway(
        BridgeConfig(trust_mode="full_delegate", enable_codex_tasks=True),
        session_store_path=tmp_path / "sessions.json",
    )
    commands: list[list[str]] = []

    async def fake_run_codex_command(
        command: list[str],
        output_path: Path,
        wait_timeout_s: float,
        cwd: Path,
    ) -> tuple[int, str, str]:
        commands.append(command)
        output_path.write_text(f"message {len(commands)}", encoding="utf-8")
        return (
            0,
            '{"type":"session_configured","session_id":"019ee9e9-ecb8-72e3-a495-43674e1d7576"}\n',
            "",
        )

    monkeypatch.setattr(gateway, "_run_codex_command", fake_run_codex_command)
    monkeypatch.setattr(gateway, "_codex_path", lambda: "/usr/local/bin/codex")
    await gateway.codex_session_start(prompt="start", cwd=str(tmp_path))

    result = await gateway.codex_session_continue(
        prompt="continue",
        bridge_session_id="latest",
    )

    assert result["final_message"] == "message 2"
    assert commands[1][1:3] == ["exec", "resume"]
    assert "019ee9e9-ecb8-72e3-a495-43674e1d7576" in commands[1]


@pytest.mark.asyncio
async def test_codex_session_continue_omits_sandbox_for_resume_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = LocalGateway(
        BridgeConfig(trust_mode="full_delegate", enable_codex_tasks=True),
        session_store_path=tmp_path / "sessions.json",
    )
    commands: list[list[str]] = []

    async def fake_run_codex_command(
        command: list[str],
        output_path: Path,
        wait_timeout_s: float,
        cwd: Path,
    ) -> tuple[int, str, str]:
        commands.append(command)
        output_path.write_text("ok", encoding="utf-8")
        return (
            0,
            '{"type":"session_configured","session_id":"019ee9e9-ecb8-72e3-a495-43674e1d7576"}\n',
            "",
        )

    monkeypatch.setattr(gateway, "_run_codex_command", fake_run_codex_command)
    monkeypatch.setattr(gateway, "_codex_path", lambda: "/usr/local/bin/codex")
    await gateway.codex_session_start(prompt="start", cwd=str(tmp_path), sandbox_mode="read_only")

    await gateway.codex_session_continue(
        prompt="continue",
        bridge_session_id="latest",
        sandbox_mode="read_only",
    )

    assert commands[1][1:3] == ["exec", "resume"]
    assert "--sandbox" not in commands[1]


@pytest.mark.asyncio
async def test_codex_session_continue_runs_resume_in_recorded_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    gateway = LocalGateway(
        BridgeConfig(trust_mode="full_delegate", enable_codex_tasks=True),
        session_store_path=tmp_path / "sessions.json",
    )
    cwd_values: list[Path] = []

    async def fake_run_codex_command(
        command: list[str],
        output_path: Path,
        wait_timeout_s: float,
        cwd: Path,
    ) -> tuple[int, str, str]:
        cwd_values.append(cwd)
        output_path.write_text("ok", encoding="utf-8")
        return (
            0,
            '{"type":"session_configured","session_id":"019ee9e9-ecb8-72e3-a495-43674e1d7576"}\n',
            "",
        )

    monkeypatch.setattr(gateway, "_run_codex_command", fake_run_codex_command)
    monkeypatch.setattr(gateway, "_codex_path", lambda: "/usr/local/bin/codex")
    await gateway.codex_session_start(prompt="start", cwd=str(project), sandbox_mode="read_only")

    await gateway.codex_session_continue(
        prompt="continue",
        bridge_session_id="latest",
        sandbox_mode="read_only",
    )

    assert cwd_values == [project.resolve(strict=False), project.resolve(strict=False)]


@pytest.mark.asyncio
async def test_codex_session_continue_rechecks_current_permissions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    gateway = LocalGateway(
        BridgeConfig(trust_mode="full_delegate", enable_codex_tasks=True),
        session_store_path=tmp_path / "sessions.json",
    )

    async def fake_run_codex_command(
        command: list[str],
        output_path: Path,
        wait_timeout_s: float,
        cwd: Path,
    ) -> tuple[int, str, str]:
        output_path.write_text("ok", encoding="utf-8")
        return (
            0,
            '{"type":"session_configured","session_id":"019ee9e9-ecb8-72e3-a495-43674e1d7576"}\n',
            "",
        )

    monkeypatch.setattr(gateway, "_run_codex_command", fake_run_codex_command)
    monkeypatch.setattr(gateway, "_codex_path", lambda: "/usr/local/bin/codex")
    await gateway.codex_session_start(prompt="start", cwd=str(project))
    await gateway.set_bridge_mode(mode="restricted")

    with pytest.raises(BridgeError, match="not inside an approved grant"):
        await gateway.codex_session_continue(prompt="continue", bridge_session_id="latest")


@pytest.mark.asyncio
async def test_codex_delegate_starts_one_local_codex_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = LocalGateway(
        BridgeConfig(trust_mode="full_delegate", enable_codex_tasks=True),
        session_store_path=tmp_path / "sessions.json",
    )
    commands: list[list[str]] = []

    async def fake_run_codex_command(
        command: list[str],
        output_path: Path,
        wait_timeout_s: float,
        cwd: Path,
    ) -> tuple[int, str, str]:
        commands.append(command)
        output_path.write_text("delegated", encoding="utf-8")
        return (
            0,
            '{"type":"session_configured","session_id":"019ee9e9-ecb8-72e3-a495-43674e1d7576"}\n',
            "",
        )

    monkeypatch.setattr(gateway, "_run_codex_command", fake_run_codex_command)
    monkeypatch.setattr(gateway, "_codex_path", lambda: "/usr/local/bin/codex")

    result = await gateway.codex_delegate(
        task="open TextEdit and type hello",
        permission_level="gui_control",
        target_paths=[],
        expected_result="TextEdit contains hello.",
        cwd=str(tmp_path),
    )

    assert result["final_message"] == "delegated"
    assert result["delegation_mode"] == "start"
    assert result["permission_level"] == "gui_control"
    assert result["target_paths"] == []
    assert result["sandbox_mode"] == "danger_full_access"
    assert commands[0][1] == "exec"
    assert "--skip-git-repo-check" in commands[0]
    assert "--dangerously-bypass-approvals-and-sandbox" in commands[0]
    delegated_prompt = commands[0][-1]
    assert "Permission level: gui_control" in delegated_prompt
    assert "Task:\nopen TextEdit and type hello" in delegated_prompt
    assert "Expected result:\nTextEdit contains hello." in delegated_prompt


@pytest.mark.asyncio
async def test_codex_delegate_accepts_legacy_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = LocalGateway(
        BridgeConfig(trust_mode="full_delegate", enable_codex_tasks=True),
        session_store_path=tmp_path / "sessions.json",
    )
    commands: list[list[str]] = []

    async def fake_run_codex_command(
        command: list[str],
        output_path: Path,
        wait_timeout_s: float,
        cwd: Path,
    ) -> tuple[int, str, str]:
        commands.append(command)
        output_path.write_text("delegated", encoding="utf-8")
        return (
            0,
            '{"type":"session_configured","session_id":"019ee9e9-ecb8-72e3-a495-43674e1d7576"}\n',
            "",
        )

    monkeypatch.setattr(gateway, "_run_codex_command", fake_run_codex_command)
    monkeypatch.setattr(gateway, "_codex_path", lambda: "/usr/local/bin/codex")

    result = await gateway.codex_delegate(prompt="legacy prompt", cwd=str(tmp_path))

    assert result["final_message"] == "delegated"
    assert result["permission_level"] == "full_local"
    assert result["sandbox_mode"] == "danger_full_access"
    assert "Task:\nlegacy prompt" in commands[0][-1]


@pytest.mark.asyncio
async def test_codex_delegate_defaults_sandbox_from_permission_level(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = LocalGateway(
        BridgeConfig(trust_mode="full_delegate", enable_codex_tasks=True),
        session_store_path=tmp_path / "sessions.json",
    )
    commands: list[list[str]] = []

    async def fake_run_codex_command(
        command: list[str],
        output_path: Path,
        wait_timeout_s: float,
        cwd: Path,
    ) -> tuple[int, str, str]:
        commands.append(command)
        output_path.write_text("delegated", encoding="utf-8")
        return (
            0,
            '{"type":"session_configured","session_id":"019ee9e9-ecb8-72e3-a495-43674e1d7576"}\n',
            "",
        )

    monkeypatch.setattr(gateway, "_run_codex_command", fake_run_codex_command)
    monkeypatch.setattr(gateway, "_codex_path", lambda: "/usr/local/bin/codex")

    read_result = await gateway.codex_delegate(
        task="inspect files",
        permission_level="read_only",
        cwd=str(tmp_path),
    )
    write_result = await gateway.codex_delegate(
        task="write local file",
        permission_level="local_file_write",
        cwd=str(tmp_path),
    )

    assert read_result["sandbox_mode"] == "read_only"
    assert write_result["sandbox_mode"] == "workspace_write"
    assert commands[0][-3:-1] == ["--sandbox", "read-only"]
    assert commands[1][-3:-1] == ["--sandbox", "workspace-write"]


@pytest.mark.asyncio
async def test_codex_delegate_rejects_sandbox_above_permission_level(tmp_path: Path) -> None:
    gateway = LocalGateway(
        BridgeConfig(trust_mode="full_delegate", enable_codex_tasks=True),
        session_store_path=tmp_path / "sessions.json",
    )

    with pytest.raises(BridgeError, match="exceeds permission_level"):
        await gateway.codex_delegate(
            task="inspect files",
            permission_level="read_only",
            sandbox_mode="danger_full_access",
            cwd=str(tmp_path),
        )


@pytest.mark.asyncio
async def test_codex_delegate_rejects_empty_structured_task(tmp_path: Path) -> None:
    gateway = LocalGateway(
        BridgeConfig(trust_mode="full_delegate", enable_codex_tasks=True),
        session_store_path=tmp_path / "sessions.json",
    )

    with pytest.raises(BridgeError, match="task must not be empty"):
        await gateway.codex_delegate(task="   ", cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_codex_delegate_continues_existing_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = LocalGateway(
        BridgeConfig(trust_mode="full_delegate", enable_codex_tasks=True),
        session_store_path=tmp_path / "sessions.json",
    )
    commands: list[list[str]] = []

    async def fake_run_codex_command(
        command: list[str],
        output_path: Path,
        wait_timeout_s: float,
        cwd: Path,
    ) -> tuple[int, str, str]:
        commands.append(command)
        output_path.write_text(f"delegated {len(commands)}", encoding="utf-8")
        return (
            0,
            '{"type":"session_configured","session_id":"019ee9e9-ecb8-72e3-a495-43674e1d7576"}\n',
            "",
        )

    monkeypatch.setattr(gateway, "_run_codex_command", fake_run_codex_command)
    monkeypatch.setattr(gateway, "_codex_path", lambda: "/usr/local/bin/codex")
    await gateway.codex_delegate(task="start", cwd=str(tmp_path))

    result = await gateway.codex_delegate(task="continue", bridge_session_id="latest")

    assert result["final_message"] == "delegated 2"
    assert result["delegation_mode"] == "continue"
    assert result["permission_level"] == "full_local"
    assert commands[1][1:3] == ["exec", "resume"]
    assert "--skip-git-repo-check" in commands[1]


def test_codex_exec_permission_args_match_exec_cli(tmp_path: Path) -> None:
    gateway = LocalGateway(
        BridgeConfig(trust_mode="full_delegate", enable_codex_tasks=True),
        session_store_path=tmp_path / "sessions.json",
    )

    assert gateway._codex_permission_args("read_only") == ["--sandbox", "read-only"]
    assert gateway._codex_permission_args("workspace_write") == ["--sandbox", "workspace-write"]
    assert gateway._codex_permission_args("danger_full_access") == [
        "--dangerously-bypass-approvals-and-sandbox"
    ]
