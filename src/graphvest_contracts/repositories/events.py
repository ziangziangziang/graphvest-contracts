"""Event persistence port."""

from __future__ import annotations

from typing import Protocol

from graphvest_contracts.domain.events import Event


class EventRepository(Protocol):
    async def put(self, event: Event) -> None: ...
    async def get(self, event_id: str) -> Event | None: ...
