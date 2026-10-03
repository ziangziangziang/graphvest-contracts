"""Single-writer compact collection persistence port."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from graphvest_contracts.domain.base import Window
from graphvest_contracts.domain.collection import CollectionRequest, PriceBatch, PriceCommit
from graphvest_contracts.errors import PersistenceError


def validate_commit(commit: PriceCommit, batch: PriceBatch) -> None:
    if (
        commit.commit_id != batch.batch_id
        or commit.partition_id != batch.request.partition.partition_id
        or commit.predecessor_id != batch.predecessor_id
        or commit.window != batch.request.window
        or commit.received_at != batch.receipt.received_at
        or commit.quality != batch.quality
    ):
        raise PersistenceError("price commit does not match prepared batch")


def validate_predecessor(commit: PriceCommit, predecessor: PriceCommit | None) -> None:
    if predecessor is None:
        if commit.predecessor_id is not None or commit.sequence != 1:
            raise PersistenceError("price commit predecessor is missing")
    elif (
        commit.predecessor_id != predecessor.commit_id
        or commit.partition_id != predecessor.partition_id
        or commit.sequence != predecessor.sequence + 1
        or commit.committed_at < predecessor.committed_at
        or commit.received_at < predecessor.committed_at
    ):
        raise PersistenceError("invalid price commit order")


class PriceCollectionRepository(Protocol):
    async def pending(self, partition_id: str) -> CollectionRequest | None: ...
    async def set_pending(self, request: CollectionRequest | None, partition_id: str) -> None: ...
    async def get_batch(self, batch_id: str) -> PriceBatch | None: ...
    async def put_batch(self, batch: PriceBatch) -> None: ...
    async def get_commit(self, commit_id: str) -> PriceCommit | None: ...
    async def put_commit(self, commit: PriceCommit) -> None: ...
    async def commits(
        self, partition_id: str, window: Window | None, as_of: datetime
    ) -> tuple[PriceCommit, ...]: ...
