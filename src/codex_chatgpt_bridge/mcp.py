"""Minimal HTTP MCP-compatible server for ChatGPT connectors."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .gateway import BridgeError, LocalGateway

JsonObject = dict[str, Any]


class JsonRpcRequest(BaseModel):
    """A JSON-RPC request used by MCP over HTTP."""

    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str
    params: JsonObject = Field(default_factory=dict)


def create_app(gateway: LocalGateway) -> FastAPI:
    """Create the FastAPI app."""

    app = FastAPI(title="Codex ChatGPT Bridge", version="0.1.0")

    @app.get("/healthz")
    async def healthz() -> JsonObject:
        return {"status": "ok", "server": "codex-chatgpt-bridge"}

    @app.post("/mcp")
    async def mcp_endpoint(
        request: JsonRpcRequest,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        auth_error = _auth_error(gateway.config.auth_token, authorization)
        if auth_error is not None:
            return auth_error
        return await _handle_mcp_request(gateway, request, auth_mode="bearer")

    @app.post("/mcp/{connector_secret}")
    async def mcp_connector_secret_endpoint(
        connector_secret: str,
        request: JsonRpcRequest,
    ) -> JSONResponse:
        if connector_secret != gateway.config.connector_secret:
            return _auth_error(gateway.config.connector_secret, None)
        return await _handle_mcp_request(gateway, request, auth_mode="connector_secret")

    return app


async def call_tool(gateway: LocalGateway, params: JsonObject) -> JsonObject:
    """Dispatch a tool call."""

    name = str(params.get("name", ""))
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise ValueError("tools/call params.arguments must be an object")
    handlers: dict[str, Callable[..., Awaitable[JsonObject]]] = {
        "bridge_status": gateway.bridge_status,
        "set_bridge_mode": gateway.set_bridge_mode,
        "grant_path": gateway.grant_path,
        "revoke_grant": gateway.revoke_grant,
        "list_grants": gateway.list_grants,
        "search_files": gateway.search_files,
        "read_file": gateway.read_file,
        "write_file": gateway.write_file,
    }
    if gateway.config.enable_codex_tasks:
        handlers["codex_task_run"] = gateway.codex_task_run
        handlers["codex_session_start"] = gateway.codex_session_start
        handlers["codex_session_continue"] = gateway.codex_session_continue
        handlers["codex_session_list"] = gateway.codex_session_list
        handlers["codex_session_status"] = gateway.codex_session_status
    handler = handlers.get(name)
    if handler is None:
        raise ValueError(f"unknown tool: {name}")
    structured = await handler(**arguments)
    return {
        "structuredContent": structured,
        "content": [{"type": "text", "text": json.dumps(structured, ensure_ascii=False, indent=2)}],
    }


async def _handle_mcp_request(
    gateway: LocalGateway,
    request: JsonRpcRequest,
    *,
    auth_mode: str,
) -> JSONResponse:
    try:
        if request.method == "tools/list":
            result = {
                "tools": tool_definitions(
                    gateway.config.enable_codex_tasks,
                    auth_mode=auth_mode,
                )
            }
        elif request.method == "tools/call":
            result = await call_tool(gateway, request.params)
        elif request.method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "codex-chatgpt-bridge", "version": "0.1.0"},
            }
        elif request.method == "notifications/initialized" or request.method == "ping":
            result = {}
        else:
            return _jsonrpc_error(request.id, -32601, f"unknown method: {request.method}")
    except BridgeError as exc:
        return _jsonrpc_error(request.id, -32000, str(exc))
    except ValueError as exc:
        return _jsonrpc_error(request.id, -32602, str(exc))
    return JSONResponse({"jsonrpc": "2.0", "id": request.id, "result": result})


def tool_definitions(enable_codex_tasks: bool, *, auth_mode: str = "bearer") -> list[JsonObject]:
    """Return tool schemas visible to ChatGPT."""

    tools: list[JsonObject] = [
        {
            "name": "bridge_status",
            "title": "Bridge status",
            "description": (
                "Check whether the local bridge is alive and which capabilities are available."
            ),
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        },
        {
            "name": "set_bridge_mode",
            "title": "Set bridge trust mode",
            "description": (
                "Switch the local bridge between restricted grants and full delegate mode. "
                "full_delegate gives this connector broad local read, write, and execute access."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["restricted", "full_delegate"],
                    }
                },
                "required": ["mode"],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": False, "destructiveHint": True, "openWorldHint": False},
        },
        {
            "name": "grant_path",
            "title": "Grant local path",
            "description": (
                "Add or replace a persisted local path grant for reading, writing, and execution."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1, "maxLength": 1000},
                    "name": {"type": ["string", "null"], "default": None},
                    "read": {"type": "boolean", "default": True},
                    "write": {"type": "boolean", "default": False},
                    "execute": {"type": "boolean", "default": False},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": False, "destructiveHint": True, "openWorldHint": False},
        },
        {
            "name": "revoke_grant",
            "title": "Revoke local path grant",
            "description": "Remove a persisted local path grant by path.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1, "maxLength": 1000},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": False, "destructiveHint": True, "openWorldHint": False},
        },
        {
            "name": "list_grants",
            "title": "List local grants",
            "description": (
                "List user-approved local directories and their read, write, "
                "and execute permissions."
            ),
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        },
        {
            "name": "search_files",
            "title": "Search approved local files",
            "description": "Search text in user-approved readable directories with ripgrep.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "minLength": 1, "maxLength": 240},
                    "root": {"type": ["string", "null"], "default": None},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        },
        {
            "name": "read_file",
            "title": "Read approved local file",
            "description": "Read a UTF-8 text file inside a user-approved readable directory.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1, "maxLength": 1000},
                    "max_chars": {"type": ["integer", "null"], "minimum": 1, "default": None},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        },
        {
            "name": "write_file",
            "title": "Write approved local file",
            "description": "Write UTF-8 text to a file inside a user-approved writable directory.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1, "maxLength": 1000},
                    "content": {"type": "string", "maxLength": 400000},
                    "create_parents": {"type": "boolean", "default": False},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
            "annotations": {
                "readOnlyHint": False,
                "destructiveHint": True,
                "openWorldHint": False,
            },
        },
    ]
    if enable_codex_tasks:
        tools.extend(_codex_tool_definitions())
    for tool in tools:
        security_schemes = (
            [{"type": "noauth"}]
            if auth_mode == "connector_secret"
            else [{"type": "http", "scheme": "bearer"}]
        )
        tool["securitySchemes"] = security_schemes
        tool["_meta"] = {
            "securitySchemes": security_schemes,
            "openai/visibility": "public",
            "openai/toolInvocation/invoking": f"Running {tool['name']}",
            "openai/toolInvocation/invoked": f"{tool['name']} finished",
        }
    return tools


def _codex_tool_definitions() -> list[JsonObject]:
    codex_session_sandbox = {
        "type": "string",
        "enum": ["read_only", "workspace_write", "danger_full_access"],
        "default": "danger_full_access",
    }
    return [
        {
            "name": "codex_task_run",
            "title": "Run local Codex task",
            "description": (
                "Hand one bounded task to local Codex in an approved executable directory."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "minLength": 1, "maxLength": 20000},
                    "cwd": {"type": "string", "minLength": 1, "maxLength": 1000},
                    "sandbox_mode": {
                        "type": "string",
                        "enum": ["read_only", "workspace_write"],
                        "default": "read_only",
                    },
                    "wait_timeout_s": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "maximum": 600,
                        "default": 120,
                    },
                },
                "required": ["prompt", "cwd"],
                "additionalProperties": False,
            },
            "annotations": {
                "readOnlyHint": False,
                "destructiveHint": True,
                "openWorldHint": False,
            },
        },
        {
            "name": "codex_session_start",
            "title": "Start local Codex session",
            "description": (
                "Start a persistent local Codex session. Use this as the main execution path "
                "when ChatGPT needs local project changes, command execution, tests, or repo work."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "minLength": 1, "maxLength": 20000},
                    "cwd": {"type": "string", "minLength": 1, "maxLength": 1000},
                    "sandbox_mode": codex_session_sandbox,
                    "wait_timeout_s": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "maximum": 1200,
                        "default": 600,
                    },
                },
                "required": ["prompt", "cwd"],
                "additionalProperties": False,
            },
            "annotations": {
                "readOnlyHint": False,
                "destructiveHint": True,
                "openWorldHint": False,
            },
        },
        {
            "name": "codex_session_continue",
            "title": "Continue local Codex session",
            "description": "Send a follow-up prompt to a persisted local Codex session.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "minLength": 1, "maxLength": 20000},
                    "bridge_session_id": {
                        "type": "string",
                        "default": "latest",
                        "description": "Use latest, a bridge_session_id, or a Codex session id.",
                    },
                    "sandbox_mode": codex_session_sandbox,
                    "wait_timeout_s": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "maximum": 1200,
                        "default": 600,
                    },
                },
                "required": ["prompt"],
                "additionalProperties": False,
            },
            "annotations": {
                "readOnlyHint": False,
                "destructiveHint": True,
                "openWorldHint": False,
            },
        },
        {
            "name": "codex_session_list",
            "title": "List local Codex sessions",
            "description": "List persistent local Codex sessions known to the bridge.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        },
        {
            "name": "codex_session_status",
            "title": "Get local Codex session status",
            "description": "Return metadata for a persisted local Codex session.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "bridge_session_id": {
                        "type": "string",
                        "default": "latest",
                    },
                },
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        },
    ]


def _auth_error(expected_token: str, authorization: str | None) -> JSONResponse | None:
    if authorization == f"Bearer {expected_token}":
        return None
    return JSONResponse(
        {"error": "missing or invalid bearer token"},
        status_code=401,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _jsonrpc_error(request_id: int | str | None, code: int, message: str) -> JSONResponse:
    return JSONResponse(
        {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}},
        status_code=200,
    )
