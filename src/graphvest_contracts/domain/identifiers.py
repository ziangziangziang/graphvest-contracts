"""Opaque stable IDs; ticker symbols are scoped, temporal identifiers only."""

from __future__ import annotations

from uuid import UUID, uuid5

from pydantic import AwareDatetime, model_validator

from graphvest_contracts.domain.base import Model, NonEmpty

_NAMESPACE = UUID("743a80af-2b12-4ac2-bb50-814bb192c222")


def stable_id(namespace: str, key: str) -> str:
    return str(uuid5(_NAMESPACE, f"{len(namespace)}:{namespace}{key}"))


class Identifier(Model):
    scheme: NonEmpty
    value: NonEmpty
    scope: str | None = None
    effective_from: AwareDatetime | None = None
    effective_to: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_interval(self) -> Identifier:
        if self.scheme.lower() == "ticker" and not self.scope:
            raise ValueError("ticker identifiers require a venue/scope")
        if self.effective_to and (
            not self.effective_from or self.effective_to <= self.effective_from
        ):
            raise ValueError("effective_to requires an earlier effective_from")
        return self
