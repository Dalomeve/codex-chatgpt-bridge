"""Local gateway used by MCP tools."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from .codex_sessions import (
    CodexSessionRecord,
    CodexSessionStore,
    default_session_store_path,
    extract_codex_session_id,
)
from .config import (
    BridgeConfig,
    BridgeGrant,
    TrustMode,
    add_grant,
    default_config_path,
    save_config,
)
from .security import is_relative_to, is_sensitive_path, resolve_user_path

SandboxMode = Literal["read_only", "workspace_write"]
CodexSessionSandboxMode = Literal["read_only", "workspace_write", "danger_full_access"]
DelegatePermissionLevel = Literal[
    "read_only",
    "local_file_write",
    "repo_edit",
    "shell_command",
    "gui_control",
    "full_local",
]
JsonObject = dict[str, Any]
DELEGATE_PERMISSION_LEVELS: set[str] = {
    "read_only",
    "local_file_write",
    "repo_edit",
    "shell_command",
    "gui_control",
    "full_local",
}
DELEGATE_DEFAULT_SANDBOX: dict[str, CodexSessionSandboxMode] = {
    "read_only": "read_only",
    "local_file_write": "workspace_write",
    "repo_edit": "workspace_write",
    "shell_command": "danger_full_access",
    "gui_control": "danger_full_access",
    "full_local": "danger_full_access",
}
SANDBOX_RANK: dict[str, int] = {
    "read_only": 0,
    "workspace_write": 1,
    "danger_full_access": 2,
}


class BridgeError(RuntimeError):
    """User-facing bridge error."""


class LocalGateway:
    """Authorize local actions and execute them for the MCP layer."""

    def __init__(
        self,
        config: BridgeConfig,
        *,
        config_path: Path | None = None,
        session_store_path: Path | None = None,
    ) -> None:
        self._config = config
        self._config_path = config_path or default_config_path()
        self._session_store = CodexSessionStore(
            session_store_path or default_session_store_path(self._config_path)
        )

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
            "trust_mode": self._config.trust_mode,
            "tool_profile": self._config.tool_profile,
            "grant_count": len(self._config.grants),
            "auth_required": True,
            "codex_tasks_enabled": self._config.enable_codex_tasks,
            "tools": self._visible_tool_names(),
        }

    def _visible_tool_names(self) -> list[str]:
        if self._config.tool_profile == "delegate":
            return [
                "bridge_status",
                *(
                    [
                        "codex_delegate",
                        "codex_session_list",
                        "codex_session_status",
                    ]
                    if self._config.enable_codex_tasks
                    else []
                ),
            ]
        return [
            "bridge_status",
            "set_bridge_mode",
            "grant_path",
            "revoke_grant",
            "list_grants",
            "search_files",
            "read_file",
            "write_file",
            *(["codex_task_run"] if self._config.enable_codex_tasks else []),
            *(
                [
                    "codex_delegate",
                    "codex_session_start",
                    "codex_session_continue",
                    "codex_session_list",
                    "codex_session_status",
                ]
                if self._config.enable_codex_tasks
                else []
            ),
        ]

    async def list_grants(self) -> JsonObject:
        """List configured grants."""

        return {
            "trust_mode": self._config.trust_mode,
            "full_delegate": self._config.trust_mode == "full_delegate",
            "grants": [
                {
                    "name": grant.name,
                    "path": str(grant.resolved_path),
                    "read": grant.read,
                    "write": grant.write,
                    "execute": grant.execute,
                }
                for grant in self._config.grants
            ],
        }

    async def set_bridge_mode(self, *, mode: TrustMode) -> JsonObject:
        """Set and persist the bridge trust mode."""

        if mode not in {"restricted", "full_delegate"}:
            raise BridgeError("mode must be restricted or full_delegate")
        self._config = self._config.model_copy(update={"trust_mode": mode})
        self._save_runtime_config()
        return {
            "trust_mode": self._config.trust_mode,
            "full_delegate": self._config.trust_mode == "full_delegate",
        }

    async def grant_path(
        self,
        *,
        path: str,
        name: str | None = None,
        read: bool = True,
        write: bool = False,
        execute: bool = False,
    ) -> JsonObject:
        """Grant a local path at runtime and persist the config."""

        self._config = add_grant(
            self._config,
            path=Path(path),
            name=name,
            read=read,
            write=write,
            execute=execute,
        )
        self._save_runtime_config()
        grant = self._matching_grant(resolve_user_path(path))
        if grant is None:
            raise BridgeError(f"failed to persist grant: {path}")
        return {
            "grant": {
                "name": grant.name,
                "path": str(grant.resolved_path),
                "read": grant.read,
                "write": grant.write,
                "execute": grant.execute,
            }
        }

    async def revoke_grant(self, *, path: str) -> JsonObject:
        """Remove a local path grant at runtime and persist the config."""

        resolved = resolve_user_path(path)
        before = len(self._config.grants)
        grants = [grant for grant in self._config.grants if grant.resolved_path != resolved]
        self._config = self._config.model_copy(update={"grants": grants})
        self._save_runtime_config()
        return {"path": str(resolved), "removed": len(grants) < before}

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

    async def codex_session_start(
        self,
        *,
        prompt: str,
        cwd: str,
        sandbox_mode: CodexSessionSandboxMode = "danger_full_access",
        wait_timeout_s: float = 600.0,
    ) -> JsonObject:
        """Start a persisted local Codex session and return its bridge handle."""

        if not self._config.enable_codex_tasks:
            raise BridgeError(
                "codex session tools are disabled; enable codex tasks in the bridge config"
            )
        if not prompt.strip():
            raise BridgeError("prompt must not be empty")
        resolved_cwd = self._authorize_codex_cwd(cwd, sandbox_mode)
        output_path = self._new_output_path()
        command = [
            self._codex_path(),
            "exec",
            "--cd",
            str(resolved_cwd),
            "--skip-git-repo-check",
            "--json",
            "--output-last-message",
            str(output_path),
            *self._codex_permission_args(sandbox_mode),
            prompt,
        ]
        return await self._finish_codex_session_run(
            command=command,
            output_path=output_path,
            wait_timeout_s=wait_timeout_s,
            prompt=prompt,
            cwd=resolved_cwd,
            existing_record=None,
            sandbox_mode=sandbox_mode,
        )

    async def codex_delegate(
        self,
        *,
        task: str | None = None,
        prompt: str | None = None,
        permission_level: DelegatePermissionLevel = "full_local",
        target_paths: list[str] | None = None,
        expected_result: str | None = None,
        cwd: str | None = None,
        bridge_session_id: str | None = None,
        sandbox_mode: CodexSessionSandboxMode | None = None,
        wait_timeout_s: float = 600.0,
    ) -> JsonObject:
        """Delegate one whole local task to Codex through a single MCP call."""

        task_text = self._delegate_task_text(task=task, prompt=prompt)
        if permission_level not in DELEGATE_PERMISSION_LEVELS:
            raise BridgeError("permission_level must be a supported delegate permission level")
        resolved_sandbox_mode = self._resolve_delegate_sandbox_mode(
            permission_level=permission_level,
            sandbox_mode=sandbox_mode,
        )
        normalized_paths = self._normalize_delegate_target_paths(target_paths)
        effective_prompt = self._build_delegate_prompt(
            task=task_text,
            permission_level=permission_level,
            target_paths=normalized_paths,
            expected_result=expected_result,
        )
        if bridge_session_id:
            result = await self.codex_session_continue(
                prompt=effective_prompt,
                bridge_session_id=bridge_session_id,
                sandbox_mode=resolved_sandbox_mode,
                wait_timeout_s=wait_timeout_s,
            )
            result["delegation_mode"] = "continue"
        else:
            result = await self.codex_session_start(
                prompt=effective_prompt,
                cwd=cwd or str(Path.home()),
                sandbox_mode=resolved_sandbox_mode,
                wait_timeout_s=wait_timeout_s,
            )
            result["delegation_mode"] = "start"
        result["permission_level"] = permission_level
        result["target_paths"] = normalized_paths
        return result

    def _delegate_task_text(self, *, task: str | None, prompt: str | None) -> str:
        raw_task = task if task is not None else prompt
        if raw_task is None or not raw_task.strip():
            raise BridgeError("task must not be empty")
        return raw_task.strip()

    def _normalize_delegate_target_paths(self, target_paths: list[str] | None) -> list[str]:
        if target_paths is None:
            return []
        normalized: list[str] = []
        for raw_path in target_paths:
            if not raw_path.strip():
                raise BridgeError("target_paths must not contain empty paths")
            normalized.append(str(resolve_user_path(raw_path)))
        return normalized

    def _resolve_delegate_sandbox_mode(
        self,
        *,
        permission_level: DelegatePermissionLevel,
        sandbox_mode: CodexSessionSandboxMode | None,
    ) -> CodexSessionSandboxMode:
        default_sandbox = DELEGATE_DEFAULT_SANDBOX[permission_level]
        if sandbox_mode is None:
            return default_sandbox
        if sandbox_mode not in SANDBOX_RANK:
            raise BridgeError(
                "sandbox_mode must be read_only, workspace_write, or danger_full_access"
            )
        if SANDBOX_RANK[sandbox_mode] > SANDBOX_RANK[default_sandbox]:
            raise BridgeError(
                f"sandbox_mode={sandbox_mode} exceeds permission_level={permission_level}"
            )
        return sandbox_mode

    def _build_delegate_prompt(
        self,
        *,
        task: str,
        permission_level: DelegatePermissionLevel,
        target_paths: list[str],
        expected_result: str | None,
    ) -> str:
        path_block = (
            "\n".join(f"- {path}" for path in target_paths)
            if target_paths
            else "Not specified by ChatGPT."
        )
        result_block = (
            expected_result.strip()
            if expected_result and expected_result.strip()
            else ("Complete the delegated task and report the outcome.")
        )
        return "\n\n".join(
            [
                "You are local Codex executing a task delegated from ChatGPT web.",
                "Act as the local device agent for this machine.",
                f"Permission level: {permission_level}",
                f"Target paths:\n{path_block}",
                f"Expected result:\n{result_block}",
                f"Task:\n{task}",
                (
                    "When finished, summarize the actual local actions taken, changed files "
                    "or apps touched, commands or checks run, and any exact blocker if the task "
                    "could not be completed."
                ),
            ]
        )

    async def codex_session_continue(
        self,
        *,
        prompt: str,
        bridge_session_id: str = "latest",
        sandbox_mode: CodexSessionSandboxMode = "danger_full_access",
        wait_timeout_s: float = 600.0,
    ) -> JsonObject:
        """Continue a persisted local Codex session."""

        if not self._config.enable_codex_tasks:
            raise BridgeError(
                "codex session tools are disabled; enable codex tasks in the bridge config"
            )
        if not prompt.strip():
            raise BridgeError("prompt must not be empty")
        try:
            record = self._session_store.resolve(bridge_session_id)
        except KeyError as exc:
            raise BridgeError(str(exc)) from exc
        if not record.codex_session_id:
            raise BridgeError(f"record has no Codex session id: {record.bridge_session_id}")
        resolved_cwd = self._authorize_codex_cwd(record.cwd, sandbox_mode)
        output_path = self._new_output_path()
        command = [
            self._codex_path(),
            "exec",
            "resume",
            "--skip-git-repo-check",
            "--json",
            "--output-last-message",
            str(output_path),
            *self._codex_resume_permission_args(sandbox_mode),
            record.codex_session_id,
            prompt,
        ]
        return await self._finish_codex_session_run(
            command=command,
            output_path=output_path,
            wait_timeout_s=wait_timeout_s,
            prompt=prompt,
            cwd=resolved_cwd,
            existing_record=record,
            sandbox_mode=sandbox_mode,
        )

    async def codex_session_list(self) -> JsonObject:
        """List Codex sessions known to the bridge."""

        return {
            "sessions": [record.model_dump(mode="json") for record in self._session_store.list()]
        }

    async def codex_session_status(self, *, bridge_session_id: str = "latest") -> JsonObject:
        """Return one Codex session record."""

        try:
            record = self._session_store.resolve(bridge_session_id)
        except KeyError as exc:
            raise BridgeError(str(exc)) from exc
        return {"session": record.model_dump(mode="json")}

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

    def _authorize_codex_cwd(self, cwd: str, sandbox_mode: CodexSessionSandboxMode) -> Path:
        if sandbox_mode not in {"read_only", "workspace_write", "danger_full_access"}:
            raise BridgeError(
                "sandbox_mode must be read_only, workspace_write, or danger_full_access"
            )
        resolved_cwd = self._authorize(cwd, read=True, execute=True)
        if sandbox_mode in {"workspace_write", "danger_full_access"}:
            self._authorize(str(resolved_cwd), write=True)
        return resolved_cwd

    def _codex_path(self) -> str:
        codex_path = shutil.which("codex")
        if codex_path is None:
            raise BridgeError("codex CLI was not found on PATH")
        return codex_path

    def _codex_permission_args(self, sandbox_mode: CodexSessionSandboxMode) -> list[str]:
        if sandbox_mode == "danger_full_access":
            return ["--dangerously-bypass-approvals-and-sandbox"]
        sandbox = "workspace-write" if sandbox_mode == "workspace_write" else "read-only"
        return ["--sandbox", sandbox]

    def _codex_resume_permission_args(self, sandbox_mode: CodexSessionSandboxMode) -> list[str]:
        if sandbox_mode == "danger_full_access":
            return ["--dangerously-bypass-approvals-and-sandbox"]
        return []

    def _new_output_path(self) -> Path:
        with tempfile.NamedTemporaryFile(
            prefix="codex-chatgpt-bridge-",
            suffix=".txt",
            delete=False,
        ) as handle:
            return Path(handle.name)

    async def _finish_codex_session_run(
        self,
        *,
        command: list[str],
        output_path: Path,
        wait_timeout_s: float,
        prompt: str,
        cwd: Path,
        existing_record: CodexSessionRecord | None,
        sandbox_mode: CodexSessionSandboxMode,
    ) -> JsonObject:
        returncode, stdout, stderr = await self._run_codex_command(
            command,
            output_path,
            wait_timeout_s,
            cwd,
        )
        final_message = ""
        if output_path.exists():
            final_message = await asyncio.to_thread(
                output_path.read_text,
                encoding="utf-8",
                errors="replace",
            )
            await asyncio.to_thread(output_path.unlink, missing_ok=True)
        now = datetime.now(UTC).isoformat()
        codex_session_id = extract_codex_session_id(stdout)
        if codex_session_id is None and existing_record is not None:
            codex_session_id = existing_record.codex_session_id
        bridge_session_id = (
            existing_record.bridge_session_id if existing_record is not None else str(uuid4())
        )
        record = CodexSessionRecord(
            bridge_session_id=bridge_session_id,
            codex_session_id=codex_session_id,
            cwd=str(cwd),
            created_at=existing_record.created_at if existing_record is not None else now,
            updated_at=now,
            last_prompt=prompt,
            last_final_message=final_message,
            last_returncode=returncode,
        )
        self._session_store.upsert(record)
        return {
            "bridge_session_id": record.bridge_session_id,
            "codex_session_id": record.codex_session_id,
            "cwd": record.cwd,
            "sandbox_mode": sandbox_mode,
            "returncode": returncode,
            "final_message": final_message,
            "stdout_tail": stdout[-8000:],
            "stderr_tail": stderr[-8000:],
        }

    async def _run_codex_command(
        self,
        command: list[str],
        output_path: Path,
        wait_timeout_s: float,
        cwd: Path,
    ) -> tuple[int, str, str]:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
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
            raise BridgeError(f"codex session timed out after {wait_timeout_s} seconds") from exc
        return (
            process.returncode or 0,
            stdout_bytes.decode("utf-8", errors="replace"),
            stderr_bytes.decode("utf-8", errors="replace"),
        )

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
        if self._config.trust_mode == "full_delegate":
            return resolved
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

    def _save_runtime_config(self) -> None:
        save_config(self._config, self._config_path)

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
