"""Events and reported economic/fundamental observations."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from graphvest_contracts.domain.base import Knowledge, Model, NonEmpty, Window
from graphvest_contracts.domain.provenance import Provenance


class Event(Model):
    event_id: NonEmpty
    kind: NonEmpty
    entity_ids: tuple[str, ...]
    event_time: AwareDatetime
    knowledge: Knowledge
    evidence: tuple[Provenance, ...] = Field(min_length=1)
    description: str


class ReportedObservation(Model):
    observation_id: NonEmpty
    revision_id: NonEmpty
    entity_id: NonEmpty
    metric: NonEmpty
    value: Decimal
    unit: NonEmpty
    window: Window
    knowledge: Knowledge
    evidence: tuple[Provenance, ...] = Field(min_length=1)


type CorporateActionType = Literal["split", "dividend"]


class CorporateAction(Model):
    """A split or cash dividend as its own event; raw prices stay immutable.

    ``split_factor`` is new-shares-per-old-share (4 for a 4:1 split);
    ``dividend_amount`` is per-share cash. ``ex_time`` is the event time;
    knowledge tracks when the action was knowable.
    """

    action_id: NonEmpty
    security_id: NonEmpty
    action_type: CorporateActionType
    ex_time: AwareDatetime
    split_factor: Decimal | None = Field(gt=0, default=None)
    dividend_amount: Decimal | None = Field(ge=0, default=None)
    knowledge: Knowledge
    evidence: tuple[Provenance, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_payload(self) -> CorporateAction:
        if self.action_type == "split" and self.split_factor is None:
            raise ValueError("splits require a split factor")
        if self.action_type == "dividend" and self.dividend_amount is None:
            raise ValueError("dividends require an amount")
        if self.action_type == "split" and self.dividend_amount is not None:
            raise ValueError("splits must not carry a dividend amount")
        if self.action_type == "dividend" and self.split_factor is not None:
            raise ValueError("dividends must not carry a split factor")
        return self
