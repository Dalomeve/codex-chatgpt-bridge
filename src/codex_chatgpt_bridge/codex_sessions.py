"""Persistent metadata for local Codex sessions started by the bridge."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel

JsonObject = dict[str, Any]

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


class CodexSessionRecord(BaseModel):
    """A bridge-visible handle for a Codex CLI session."""

    bridge_session_id: str
    codex_session_id: str | None
    cwd: str
    created_at: str
    updated_at: str
    last_prompt: str
    last_final_message: str
    last_returncode: int | None


class CodexSessionStore:
    """Tiny JSON-backed registry for bridge-created Codex sessions."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def list(self) -> list[CodexSessionRecord]:
        """Return records sorted by newest update first."""

        return sorted(self._read(), key=lambda record: record.updated_at, reverse=True)

    def upsert(self, record: CodexSessionRecord) -> None:
        """Insert or replace a record."""

        records = [
            existing
            for existing in self._read()
            if existing.bridge_session_id != record.bridge_session_id
        ]
        records.append(record)
        self._write(records)

    def resolve(self, identifier: str) -> CodexSessionRecord:
        """Resolve latest, bridge session id, or Codex session id."""

        records = self.list()
        if identifier == "latest":
            if not records:
                raise KeyError("no Codex sessions have been recorded")
            return records[0]
        for record in records:
            if identifier in {record.bridge_session_id, record.codex_session_id}:
                return record
        raise KeyError(f"unknown Codex session: {identifier}")

    def _read(self) -> list[CodexSessionRecord]:
        if not self._path.exists():
            return []
        data = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return [CodexSessionRecord.model_validate(item) for item in data]

    def _write(self, records: list[CodexSessionRecord]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = [record.model_dump(mode="json") for record in records]
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._path.chmod(0o600)


def default_session_store_path(config_path: Path) -> Path:
    """Return the session store path next to the bridge config."""

    return config_path.parent / "codex_sessions.json"


def extract_codex_session_id(stdout: str) -> str | None:
    """Extract a Codex session id from JSONL stdout or plain text."""

    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            item = json.loads(stripped)
        except json.JSONDecodeError:
            match = _UUID_RE.search(stripped)
            if match:
                return match.group(0)
            continue
        found = _find_uuid_in_json(item)
        if found:
            return found
    match = _UUID_RE.search(stdout)
    return match.group(0) if match else None


def _find_uuid_in_json(value: Any) -> str | None:
    if isinstance(value, str):
        match = _UUID_RE.search(value)
        return match.group(0) if match else None
    if isinstance(value, dict):
        preferred_keys = ("session_id", "sessionId", "id")
        for key in preferred_keys:
            found = _find_uuid_in_json(value.get(key))
            if found:
                return found
        for child in value.values():
            found = _find_uuid_in_json(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_uuid_in_json(child)
            if found:
                return found
    return None
