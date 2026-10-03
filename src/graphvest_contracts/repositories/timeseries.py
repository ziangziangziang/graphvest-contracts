"""High-frequency data does not depend on graph persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from graphvest_contracts.domain.base import Window
from graphvest_contracts.domain.market import Observation


class TimeSeriesRepository(Protocol):
    async def put(self, observation: Observation) -> None: ...
    async def query(
        self, security_id: str, window: Window, *, as_of: datetime
    ) -> tuple[Observation, ...]:
        """Latest known revision per observation in the half-open event window."""
        ...
