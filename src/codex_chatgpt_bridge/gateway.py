"""Local gateway used by MCP tools."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Any, Literal

from .config import BridgeConfig, BridgeGrant
from .security import is_relative_to, is_sensitive_path, resolve_user_path

SandboxMode = Literal["read_only", "workspace_write"]
JsonObject = dict[str, Any]


class BridgeError(RuntimeError):
    """User-facing bridge error."""


class LocalGateway:
    """Authorize local actions and execute them for the MCP layer."""

    def __init__(self, config: BridgeConfig) -> None:
        self._config = config

    @property
    def config(self) -> BridgeConfig:
        """Return runtime config."""

        return self._config

    async def bridge_status(self) -> JsonObject:
        """Return basic bridge status without leaking file contents."""

        return {
            "status": "ok",
            "host": self._config.host,
            "port": self._config.port,
            "grant_count": len(self._config.grants),
            "auth_required": True,
            "codex_tasks_enabled": self._config.enable_codex_tasks,
            "tools": [
                "bridge_status",
                "list_grants",
                "search_files",
                "read_file",
                "write_file",
                *(["codex_task_run"] if self._config.enable_codex_tasks else []),
            ],
        }

    async def list_grants(self) -> JsonObject:
        """List configured grants."""

        return {
            "grants": [
                {
                    "name": grant.name,
                    "path": str(grant.resolved_path),
                    "read": grant.read,
                    "write": grant.write,
                    "execute": grant.execute,
                }
                for grant in self._config.grants
            ]
        }

    async def read_file(self, *, path: str, max_chars: int | None = None) -> JsonObject:
        """Read an approved UTF-8 file."""

        resolved = self._authorize(path, read=True)
        limit = max_chars or self._config.max_file_chars
        if limit <= 0 or limit > self._config.max_file_chars:
            raise BridgeError(f"max_chars must be between 1 and {self._config.max_file_chars}")
        if not resolved.exists() or not resolved.is_file():
            raise BridgeError(f"file does not exist: {resolved}")
        text = await asyncio.to_thread(resolved.read_text, encoding="utf-8", errors="replace")
        truncated = len(text) > limit
        return {
            "path": str(resolved),
            "text": text[:limit],
            "truncated": truncated,
            "chars": min(len(text), limit),
        }

    async def write_file(
        self,
        *,
        path: str,
        content: str,
        create_parents: bool = False,
    ) -> JsonObject:
        """Write UTF-8 text to an approved path."""

        if len(content) > self._config.max_write_chars:
            raise BridgeError(f"content exceeds max_write_chars={self._config.max_write_chars}")
        resolved = self._authorize(path, write=True)
        if create_parents:
            await asyncio.to_thread(resolved.parent.mkdir, parents=True, exist_ok=True)
        if not resolved.parent.exists():
            raise BridgeError(f"parent directory does not exist: {resolved.parent}")
        await asyncio.to_thread(resolved.write_text, content, encoding="utf-8")
        return {"path": str(resolved), "bytes": len(content.encode("utf-8"))}

    async def search_files(
        self,
        *,
        query: str,
        root: str | None = None,
        max_results: int = 50,
    ) -> JsonObject:
        """Search approved readable grants with ripgrep."""

        if not query.strip():
            raise BridgeError("query must not be empty")
        if max_results <= 0 or max_results > 200:
            raise BridgeError("max_results must be between 1 and 200")
        if shutil.which("rg") is None:
            raise BridgeError("ripgrep is required for search_files")
        roots = [self._authorize(root, read=True)] if root else self._readable_roots()
        matches: list[JsonObject] = []
        for search_root in roots:
            if not search_root.exists():
                continue
            matches.extend(
                await self._run_rg(
                    query=query,
                    root=search_root,
                    remaining=max_results - len(matches),
                )
            )
            if len(matches) >= max_results:
                break
        return {"query": query, "matches": matches, "truncated": len(matches) >= max_results}

    async def codex_task_run(
        self,
        *,
        prompt: str,
        cwd: str,
        sandbox_mode: SandboxMode = "read_only",
        wait_timeout_s: float = 120.0,
    ) -> JsonObject:
        """Run a bounded local Codex task in an approved executable directory."""

        if not self._config.enable_codex_tasks:
            raise BridgeError(
                "codex_task_run is disabled; enable it explicitly in the bridge config"
            )
        if not prompt.strip():
            raise BridgeError("prompt must not be empty")
        if sandbox_mode not in {"read_only", "workspace_write"}:
            raise BridgeError("sandbox_mode must be read_only or workspace_write")
        resolved_cwd = self._authorize(cwd, read=True, execute=True)
        if sandbox_mode == "workspace_write":
            self._authorize(str(resolved_cwd), write=True)
        codex_path = shutil.which("codex")
        if codex_path is None:
            raise BridgeError("codex CLI was not found on PATH")
        with tempfile.NamedTemporaryFile(
            prefix="codex-chatgpt-bridge-",
            suffix=".txt",
            delete=False,
        ) as handle:
            output_path = Path(handle.name)
        sandbox = "workspace-write" if sandbox_mode == "workspace_write" else "read-only"
        command = [
            codex_path,
            "exec",
            "--cd",
            str(resolved_cwd),
            "--sandbox",
            sandbox,
            "--output-last-message",
            str(output_path),
            prompt,
        ]
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=wait_timeout_s,
            )
        except TimeoutError as exc:
            process.kill()
            await process.communicate()
            await asyncio.to_thread(output_path.unlink, missing_ok=True)
            raise BridgeError(f"codex task timed out after {wait_timeout_s} seconds") from exc
        final_message = ""
        if output_path.exists():
            final_message = await asyncio.to_thread(
                output_path.read_text,
                encoding="utf-8",
                errors="replace",
            )
            await asyncio.to_thread(output_path.unlink, missing_ok=True)
        return {
            "cwd": str(resolved_cwd),
            "sandbox_mode": sandbox_mode,
            "returncode": process.returncode,
            "final_message": final_message,
            "stdout_tail": stdout_bytes.decode("utf-8", errors="replace")[-8000:],
            "stderr_tail": stderr_bytes.decode("utf-8", errors="replace")[-8000:],
        }

    def _readable_roots(self) -> list[Path]:
        return [grant.resolved_path for grant in self._config.grants if grant.read]

    def _authorize(
        self,
        raw_path: str,
        *,
        read: bool = False,
        write: bool = False,
        execute: bool = False,
    ) -> Path:
        resolved = resolve_user_path(raw_path)
        if is_sensitive_path(resolved):
            raise BridgeError(f"refusing sensitive-looking path: {resolved}")
        grant = self._matching_grant(resolved)
        if grant is None:
            raise BridgeError(f"path is not inside an approved grant: {resolved}")
        if read and not grant.read:
            raise BridgeError(f"read is not allowed for grant: {grant.resolved_path}")
        if write and not grant.write:
            raise BridgeError(f"write is not allowed for grant: {grant.resolved_path}")
        if execute and not grant.execute:
            raise BridgeError(f"execute is not allowed for grant: {grant.resolved_path}")
        return resolved

    def _matching_grant(self, path: Path) -> BridgeGrant | None:
        matches = [
            grant for grant in self._config.grants if is_relative_to(path, grant.resolved_path)
        ]
        if not matches:
            return None
        return max(matches, key=lambda grant: len(grant.resolved_path.parts))

    async def _run_rg(self, *, query: str, root: Path, remaining: int) -> list[JsonObject]:
        command = [
            "rg",
            "--line-number",
            "--column",
            "--no-heading",
            "--color",
            "never",
            "--glob",
            "!.git/**",
            "--glob",
            "!.venv/**",
            "--glob",
            "!node_modules/**",
            query,
            str(root),
        ]
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await process.communicate()
        if process.returncode not in {0, 1}:
            raise BridgeError(stderr_bytes.decode("utf-8", errors="replace")[-2000:])
        matches: list[JsonObject] = []
        for line in stdout_bytes.decode("utf-8", errors="replace").splitlines():
            if len(matches) >= remaining:
                break
            parts = line.split(":", 3)
            if len(parts) != 4:
                continue
            path, line_no, column, text = parts
            candidate = Path(path).resolve(strict=False)
            if is_sensitive_path(candidate):
                continue
            matches.append(
                {
                    "path": str(candidate),
                    "line": int(line_no),
                    "column": int(column),
                    "text": text[:500],
                }
            )
        return matches
