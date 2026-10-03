"""Market contracts. Prices use Decimal, all datetimes require timezones."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, model_validator

from graphvest_contracts.domain.base import Knowledge, Model, NonEmpty
from graphvest_contracts.domain.provenance import Provenance

type Price = Annotated[Decimal, Field(ge=0)]
type Quantity = Annotated[Decimal, Field(ge=0)]
type Count = Annotated[int, Field(ge=0)]


class MarketObservation(Model):
    observation_id: NonEmpty
    revision_id: NonEmpty
    security_id: NonEmpty
    event_time: AwareDatetime
    knowledge: Knowledge
    provenance: Provenance
    revision_seq: int = Field(ge=1, default=1)


class EquityTrade(MarketObservation):
    kind: Literal["trade"] = "trade"
    price: Price
    size: Quantity
    venue: NonEmpty
    conditions: tuple[str, ...] = ()
    price_quality: Literal["midquote", "last"] = "last"


class EquityQuote(MarketObservation):
    kind: Literal["quote"] = "quote"
    bid: Price
    bid_size: Quantity
    ask: Price
    ask_size: Quantity
    venue: NonEmpty


class Bar(MarketObservation):
    kind: Literal["bar"] = "bar"
    interval: NonEmpty
    open: Price
    high: Price
    low: Price
    close: Price
    volume: Quantity
    vwap: Price | None = None
    trade_count: Count | None = None

    @model_validator(mode="after")
    def validate_ohlc(self) -> Bar:
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise ValueError("OHLC prices must lie within low/high")
        return self


class OptionContract(Model):
    option_id: NonEmpty
    underlying_security_id: NonEmpty
    expiration: date
    strike: Price
    put_call: Literal["put", "call"]


class OptionSnapshot(MarketObservation):
    """security_id is the option contract's option_id; crossed quotes are retained."""

    kind: Literal["option_snapshot"] = "option_snapshot"
    bid: Price | None = None
    ask: Price | None = None
    bid_size: Quantity | None = None
    ask_size: Quantity | None = None
    last: Price | None = None
    volume: Count | None = None
    open_interest: Count | None = None
    implied_volatility: Annotated[float, Field(ge=0)] | None = None
    delta: Annotated[float, Field(ge=-1, le=1)] | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None


type Observation = EquityTrade | EquityQuote | Bar | OptionSnapshot
