"""GraphFin-backed operational state; sole writer required."""

from __future__ import annotations

from typing import Protocol


class CollectionRuntimeRepository(Protocol):
    async def get(self, kind: str, key: str) -> str | None: ...
    async def put(self, kind: str, key: str, payload: str, *, immutable: bool = False) -> None: ...
    async def list(self, kind: str) -> tuple[tuple[str, str], ...]: ...
