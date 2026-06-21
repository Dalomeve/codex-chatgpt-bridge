from __future__ import annotations

from pathlib import Path

from codex_chatgpt_bridge.codex_sessions import (
    CodexSessionRecord,
    CodexSessionStore,
    extract_codex_session_id,
)


def test_extract_codex_session_id_from_jsonl_stdout() -> None:
    stdout = (
        '{"type":"session_configured","session_id":"019ee9e9-ecb8-72e3-a495-43674e1d7576"}\n'
        '{"type":"message","text":"ok"}\n'
    )

    session_id = extract_codex_session_id(stdout)

    assert session_id == "019ee9e9-ecb8-72e3-a495-43674e1d7576"


def test_codex_session_store_roundtrip_and_latest(tmp_path: Path) -> None:
    store = CodexSessionStore(tmp_path / "sessions.json")
    first = CodexSessionRecord(
        bridge_session_id="bridge-1",
        codex_session_id="codex-1",
        cwd=str(tmp_path / "first"),
        created_at="2026-06-21T00:00:00+00:00",
        updated_at="2026-06-21T00:00:00+00:00",
        last_prompt="first prompt",
        last_final_message="first result",
        last_returncode=0,
    )
    second = first.model_copy(
        update={
            "bridge_session_id": "bridge-2",
            "codex_session_id": "codex-2",
            "updated_at": "2026-06-21T00:01:00+00:00",
        }
    )

    store.upsert(first)
    store.upsert(second)

    loaded = CodexSessionStore(tmp_path / "sessions.json")
    assert [record.bridge_session_id for record in loaded.list()] == ["bridge-2", "bridge-1"]
    assert loaded.resolve("latest").codex_session_id == "codex-2"
    assert loaded.resolve("bridge-1").codex_session_id == "codex-1"
    assert loaded.resolve("codex-2").bridge_session_id == "bridge-2"
