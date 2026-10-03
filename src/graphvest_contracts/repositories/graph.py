"""Graph facts use effective time plus a mandatory knowledge cutoff."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from graphvest_contracts.domain.entities import Entity
from graphvest_contracts.domain.relationships import Relationship


class GraphRepository(Protocol):
    async def put_entity(self, entity: Entity) -> None: ...
    async def get_entity(self, entity_id: str) -> Entity | None: ...
    async def put_relationship(self, relationship: Relationship) -> None: ...
    async def neighbors(
        self, entity_id: str, *, effective_at: datetime, as_of: datetime
    ) -> tuple[Relationship, ...]:
        """Return latest known revision per fact, active at effective_at, either direction."""
        ...
