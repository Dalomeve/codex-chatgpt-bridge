from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from codex_chatgpt_bridge.config import BridgeConfig, BridgeGrant
from codex_chatgpt_bridge.gateway import LocalGateway
from codex_chatgpt_bridge.mcp import create_app


def test_tools_list_includes_core_tools(tmp_path: Path) -> None:
    config = BridgeConfig(auth_token="test-token", grants=[BridgeGrant(path=tmp_path)])
    app = create_app(LocalGateway(config))
    client = TestClient(app)

    response = client.post(
        "/mcp",
        headers={"Authorization": "Bearer test-token"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )

    assert response.status_code == 200
    names = {tool["name"] for tool in response.json()["result"]["tools"]}
    assert {
        "bridge_status",
        "grant_path",
        "list_grants",
        "revoke_grant",
        "search_files",
        "set_bridge_mode",
        "read_file",
        "write_file",
    } <= names
    assert "codex_task_run" not in names


def test_tools_list_requires_bearer_token(tmp_path: Path) -> None:
    config = BridgeConfig(auth_token="test-token", grants=[BridgeGrant(path=tmp_path)])
    app = create_app(LocalGateway(config))
    client = TestClient(app)

    response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    assert response.status_code == 401


def test_connector_secret_url_allows_noauth_tools_list(tmp_path: Path) -> None:
    config = BridgeConfig(
        auth_token="test-token",
        connector_secret="connector-secret",
        grants=[BridgeGrant(path=tmp_path)],
    )
    app = create_app(LocalGateway(config))
    client = TestClient(app)

    response = client.post(
        "/mcp/connector-secret",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )

    assert response.status_code == 200
    tools = response.json()["result"]["tools"]
    assert tools[0]["securitySchemes"] == [{"type": "noauth"}]


def test_connector_secret_url_rejects_wrong_secret(tmp_path: Path) -> None:
    config = BridgeConfig(
        auth_token="test-token",
        connector_secret="connector-secret",
        grants=[BridgeGrant(path=tmp_path)],
    )
    app = create_app(LocalGateway(config))
    client = TestClient(app)

    response = client.post(
        "/mcp/wrong-secret",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )

    assert response.status_code == 401


def test_initialize_succeeds_with_bearer_token(tmp_path: Path) -> None:
    config = BridgeConfig(auth_token="test-token", grants=[BridgeGrant(path=tmp_path)])
    app = create_app(LocalGateway(config))
    client = TestClient(app)

    response = client.post(
        "/mcp",
        headers={"Authorization": "Bearer test-token"},
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
    )

    assert response.status_code == 200
    assert response.json()["result"]["capabilities"] == {"tools": {}}


def test_codex_task_tool_requires_explicit_enable(tmp_path: Path) -> None:
    config = BridgeConfig(
        auth_token="test-token",
        enable_codex_tasks=True,
        grants=[BridgeGrant(path=tmp_path, execute=True)],
    )
    app = create_app(LocalGateway(config))
    client = TestClient(app)

    response = client.post(
        "/mcp",
        headers={"Authorization": "Bearer test-token"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )

    names = {tool["name"] for tool in response.json()["result"]["tools"]}
    assert "codex_task_run" in names
    assert {
        "codex_delegate",
        "codex_session_start",
        "codex_session_continue",
        "codex_session_list",
        "codex_session_status",
    } <= names


def test_delegate_tool_profile_exposes_single_action_tool(tmp_path: Path) -> None:
    config = BridgeConfig(
        auth_token="test-token",
        enable_codex_tasks=True,
        tool_profile="delegate",
        trust_mode="full_delegate",
    )
    app = create_app(LocalGateway(config))
    client = TestClient(app)

    response = client.post(
        "/mcp",
        headers={"Authorization": "Bearer test-token"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )

    assert response.status_code == 200
    names = {tool["name"] for tool in response.json()["result"]["tools"]}
    assert names == {
        "bridge_status",
        "codex_delegate",
        "codex_session_list",
        "codex_session_status",
    }


def test_codex_delegate_schema_uses_structured_scope(tmp_path: Path) -> None:
    config = BridgeConfig(
        auth_token="test-token",
        enable_codex_tasks=True,
        tool_profile="delegate",
        trust_mode="full_delegate",
    )
    app = create_app(LocalGateway(config))
    client = TestClient(app)

    response = client.post(
        "/mcp",
        headers={"Authorization": "Bearer test-token"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )

    assert response.status_code == 200
    tools = response.json()["result"]["tools"]
    delegate_tool = next(tool for tool in tools if tool["name"] == "codex_delegate")
    schema = delegate_tool["inputSchema"]
    assert schema["required"] == ["permission_level"]
    assert schema["properties"]["prompt"]["deprecated"] is True
    assert schema["properties"]["permission_level"]["enum"] == [
        "read_only",
        "local_file_write",
        "repo_edit",
        "shell_command",
        "gui_control",
        "full_local",
    ]
    assert "target_paths" in schema["properties"]
    assert "expected_result" in schema["properties"]
    assert schema["properties"]["sandbox_mode"]["default"] is None
    assert "outputSchema" in delegate_tool
    assert delegate_tool["annotations"] == {
        "readOnlyHint": False,
        "destructiveHint": True,
        "openWorldHint": True,
    }


def test_tools_call_codex_delegate_accepts_legacy_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = BridgeConfig(
        auth_token="test-token",
        enable_codex_tasks=True,
        tool_profile="delegate",
        trust_mode="full_delegate",
    )
    gateway = LocalGateway(config, session_store_path=tmp_path / "sessions.json")
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
    app = create_app(gateway)
    client = TestClient(app)

    response = client.post(
        "/mcp",
        headers={"Authorization": "Bearer test-token"},
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "codex_delegate",
                "arguments": {
                    "prompt": "legacy prompt",
                    "permission_level": "local_file_write",
                    "cwd": str(tmp_path),
                },
            },
        },
    )

    assert response.status_code == 200
    structured = response.json()["result"]["structuredContent"]
    assert structured["final_message"] == "delegated"
    assert structured["sandbox_mode"] == "workspace_write"
    assert "Task:\nlegacy prompt" in commands[0][-1]


def test_delegate_tool_profile_blocks_hidden_low_level_tools(tmp_path: Path) -> None:
    config = BridgeConfig(
        auth_token="test-token",
        enable_codex_tasks=True,
        tool_profile="delegate",
        trust_mode="full_delegate",
    )
    app = create_app(LocalGateway(config))
    client = TestClient(app)

    response = client.post(
        "/mcp",
        headers={"Authorization": "Bearer test-token"},
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "read_file", "arguments": {"path": str(tmp_path / "x.txt")}},
        },
    )

    assert response.status_code == 200
    assert "unknown tool" in response.json()["error"]["message"]


def test_tools_call_read_file(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text("local text", encoding="utf-8")
    config = BridgeConfig(auth_token="test-token", grants=[BridgeGrant(path=tmp_path)])
    app = create_app(LocalGateway(config))
    client = TestClient(app)

    response = client.post(
        "/mcp",
        headers={"Authorization": "Bearer test-token"},
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "read_file", "arguments": {"path": str(note)}},
        },
    )

    assert response.status_code == 200
    assert response.json()["result"]["structuredContent"]["text"] == "local text"


def test_tools_call_set_bridge_mode_and_grant_path(tmp_path: Path) -> None:
    config_path = tmp_path / "bridge.toml"
    project = tmp_path / "project"
    project.mkdir()
    config = BridgeConfig(auth_token="test-token")
    app = create_app(LocalGateway(config, config_path=config_path))
    client = TestClient(app)

    mode_response = client.post(
        "/mcp",
        headers={"Authorization": "Bearer test-token"},
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "set_bridge_mode",
                "arguments": {"mode": "full_delegate"},
            },
        },
    )
    grant_response = client.post(
        "/mcp",
        headers={"Authorization": "Bearer test-token"},
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "grant_path",
                "arguments": {
                    "path": str(project),
                    "name": "project",
                    "read": True,
                    "write": True,
                    "execute": True,
                },
            },
        },
    )

    assert mode_response.status_code == 200
    assert grant_response.status_code == 200
    assert mode_response.json()["result"]["structuredContent"]["trust_mode"] == "full_delegate"
    assert grant_response.json()["result"]["structuredContent"]["grant"]["execute"] is True


def test_tools_call_grant_path_defaults_to_read_only(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    config = BridgeConfig(auth_token="test-token")
    app = create_app(LocalGateway(config, config_path=tmp_path / "bridge.toml"))
    client = TestClient(app)

    response = client.post(
        "/mcp",
        headers={"Authorization": "Bearer test-token"},
        json={
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "grant_path",
                "arguments": {"path": str(project)},
            },
        },
    )

    grant = response.json()["result"]["structuredContent"]["grant"]
    assert grant["read"] is True
    assert grant["write"] is False
    assert grant["execute"] is False
