"""Raw object preservation port."""

from __future__ import annotations

from typing import Protocol

from graphvest_contracts.ingestion import RawArtifact


class RawObjectStore(Protocol):
    async def put(self, artifact: RawArtifact) -> str:
        """Preserve bytes immutably; identical artifact IDs return the original object."""
        ...

    async def get(self, artifact_id: str) -> RawArtifact: ...
