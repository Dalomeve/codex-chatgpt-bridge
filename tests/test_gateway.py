from __future__ import annotations

from pathlib import Path

import pytest

from codex_chatgpt_bridge.config import BridgeConfig, BridgeGrant
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
