"""Compact raw-price collection contracts, separate from qualified publications.

Original responses are transient. A batch retains shared receipt metadata and a
bounded lossless block of changed points and selected source fields. Committed
batches are immutable; they do not imply calendar/action/benchmark qualification.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, model_validator

from graphvest_contracts.domain.base import Model, NonEmpty, Window
from graphvest_contracts.domain.identifiers import stable_id

type Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
type ExactNumber = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]


class PricePartition(Model):
    """Caller-resolved instrument identity; symbols are request aliases only."""

    security_id: NonEmpty
    listing_id: NonEmpty
    source: NonEmpty
    currency: NonEmpty
    calendar: NonEmpty
    interval: Literal["1d"] = "1d"
    price_convention: Literal["unadjusted"] = "unadjusted"
    schema_version: Literal["price-block-v1"] = "price-block-v1"

    @property
    def partition_id(self) -> str:
        return stable_id("price-partition", self.model_dump_json())


class CollectionRequest(Model):
    partition: PricePartition
    symbol: NonEmpty
    alias_validity: Window
    mode: Literal["backfill", "refresh", "repair"]
    window: Window
    trigger_id: NonEmpty
    expected_sessions: tuple[AwareDatetime, ...] = Field(max_length=4096)

    @model_validator(mode="after")
    def validate_scope(self) -> CollectionRequest:
        if not (
            self.alias_validity.period_start
            <= self.window.period_start
            < self.window.period_end
            <= self.alias_validity.period_end
        ):
            raise ValueError("request window must lie within the reviewed listing alias")
        if tuple(sorted(set(self.expected_sessions))) != self.expected_sessions:
            raise ValueError("expected sessions must be unique and ordered")
        if any(
            not self.window.period_start <= t < self.window.period_end
            for t in self.expected_sessions
        ):
            raise ValueError("expected session outside request window")
        return self

    @property
    def run_id(self) -> str:
        # Normalize equivalent timezone representations before identifying a run.
        document = self.model_dump(mode="json")
        for name in ("window", "alias_validity"):
            value = getattr(self, name)
            document[name] = {
                "period_start": value.period_start.astimezone(UTC).isoformat(),
                "period_end": value.period_end.astimezone(UTC).isoformat(),
            }
        document["expected_sessions"] = [
            t.astimezone(UTC).isoformat() for t in self.expected_sessions
        ]

        return stable_id("price-collection", json.dumps(document, sort_keys=True))


class PricePoint(Model):
    event_time: AwareDatetime
    open: ExactNumber
    high: ExactNumber
    low: ExactNumber
    close: ExactNumber
    volume: ExactNumber

    @model_validator(mode="after")
    def validate_ohlc(self) -> PricePoint:
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise ValueError("OHLC prices must lie within low/high")
        return self


class SourceReceipt(Model):
    source: NonEmpty
    source_url: NonEmpty
    received_at: AwareDatetime
    original_response_hash: Sha256
    retained_fragment_hash: Sha256
    normalized_output_hash: Sha256
    extractor_version: NonEmpty
    retention_state: Literal["fragment_retained", "metadata_only"]


class CollectionQuality(Model):
    status: Literal["collected", "partial", "empty"]
    accepted: int = Field(ge=0, le=4096)
    rejected: int = Field(ge=0, le=4096)
    missing_sessions: tuple[AwareDatetime, ...] = Field(default=(), max_length=4096)
    reasons: tuple[Annotated[str, Field(max_length=256)], ...] = Field(default=(), max_length=100)
    action_coverage: Literal["not_collected"] = "not_collected"

    @model_validator(mode="after")
    def validate_status(self) -> CollectionQuality:
        expected = (
            "partial"
            if self.rejected or self.missing_sessions
            else ("collected" if self.accepted else "empty")
        )
        if self.status != expected:
            raise ValueError("collection status must reflect rejects, gaps and accepted rows")
        return self


class PriceBatch(Model):
    """One prepared immutable delta, capped independently of source response size."""

    request: CollectionRequest
    receipt: SourceReceipt
    quality: CollectionQuality
    predecessor_id: str | None
    changed_count: int = Field(ge=0, le=4096)
    content_hash: Sha256
    content: bytes = Field(repr=False, max_length=2 * 1024 * 1024)

    @model_validator(mode="after")
    def validate_batch(self) -> PriceBatch:
        if hashlib.sha256(self.content).hexdigest() != self.content_hash:
            raise ValueError("price block content hash mismatch")
        if self.receipt.source != self.request.partition.source:
            raise ValueError("receipt source does not match partition")
        if self.changed_count > self.quality.accepted:
            raise ValueError("changed rows exceed accepted rows")
        if self.changed_count and self.receipt.retention_state != "fragment_retained":
            raise ValueError("changed rows require retained source fields")
        return self

    @property
    def batch_id(self) -> str:
        return self.request.run_id


class PriceCommit(Model):
    """Visibility boundary for collected inputs, not a qualified dataset publication."""

    commit_id: NonEmpty
    partition_id: NonEmpty
    predecessor_id: str | None
    sequence: int = Field(default=1, ge=1)
    window: Window
    committed_at: AwareDatetime
    received_at: AwareDatetime
    quality: CollectionQuality

    @model_validator(mode="after")
    def validate_time(self) -> PriceCommit:
        if self.committed_at < self.received_at:
            raise ValueError("commit must not precede receipt")
        if (self.predecessor_id is None and self.sequence != 1) or (
            self.predecessor_id is not None and self.sequence < 2
        ):
            raise ValueError("commit sequence must match predecessor presence")
        return self


class CollectedPrice(Model):
    point: PricePoint
    batch_id: NonEmpty
    row_index: int = Field(ge=0)
    content_hash: Sha256
