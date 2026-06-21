from __future__ import annotations

from pathlib import Path

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
        "list_grants",
        "search_files",
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
