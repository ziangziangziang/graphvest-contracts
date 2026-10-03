"""Immutable boundary models and reusable validated primitives."""

from __future__ import annotations

from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

type NonEmpty = Annotated[str, Field(min_length=1)]
type Confidence = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
type AttributeValue = str | bool | int | float


class Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class Attribute(Model):
    name: NonEmpty
    value: AttributeValue
    unit: str | None = None


class Knowledge(Model):
    published_at: AwareDatetime | None = None
    first_observed_at: AwareDatetime
    ingested_at: AwareDatetime

    @model_validator(mode="after")
    def validate_order(self) -> Knowledge:
        if self.first_observed_at > self.ingested_at:
            raise ValueError("first_observed_at must not follow ingested_at")
        return self

    @property
    def available_at(self) -> AwareDatetime:
        """Conservative system knowledge cutoff, including ingestion latency."""
        return max(self.first_observed_at, self.ingested_at, self.published_at or self.ingested_at)


class Window(Model):
    period_start: AwareDatetime
    period_end: AwareDatetime

    @model_validator(mode="after")
    def validate_order(self) -> Window:
        if self.period_end <= self.period_start:
            raise ValueError("period_end must follow period_start")
        return self
