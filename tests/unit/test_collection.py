"""Collection boundary invariants; no source/storage dependencies."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from graphvest_contracts.domain.base import Window
from graphvest_contracts.domain.collection import (
    CollectionQuality,
    CollectionRequest,
    PriceCommit,
    PricePartition,
    PricePoint,
)

NOW = datetime(2025, 1, 2, 14, 30, tzinfo=UTC)


def request() -> CollectionRequest:
    window = Window(period_start=NOW, period_end=NOW + timedelta(days=2))
    return CollectionRequest(
        partition=PricePartition(
            security_id="opaque-instrument-1",
            listing_id="opaque-listing-1",
            source="yahoo_bars",
            currency="USD",
            calendar="XNYS",
        ),
        symbol="DG",
        alias_validity=window,
        mode="backfill",
        window=window,
        trigger_id="schedule-1",
        expected_sessions=(NOW,),
    )


def test_identity_does_not_depend_on_symbol() -> None:
    req = request()
    assert (
        req.partition.partition_id
        == req.model_copy(update={"symbol": "NEW"}).partition.partition_id
    )
    assert req.run_id != req.model_copy(update={"symbol": "NEW"}).run_id
    foreign = req.partition.model_copy(update={"listing_id": "other-listing"})
    assert foreign.partition_id != req.partition.partition_id
    assert req.run_id == CollectionRequest.model_validate_json(req.model_dump_json()).run_id


@pytest.mark.parametrize(
    "sessions", [(NOW, NOW), (NOW + timedelta(days=3),), (NOW, NOW - timedelta(days=1))]
)
def test_unordered_duplicate_and_outside_sessions_rejected(sessions: tuple[datetime, ...]) -> None:
    payload = request().model_dump()
    payload["expected_sessions"] = sessions
    with pytest.raises(ValidationError):
        CollectionRequest.model_validate(payload)


def test_alias_window_cannot_cover_ticker_reuse() -> None:
    payload = request().model_dump()
    payload["alias_validity"] = Window(period_start=NOW, period_end=NOW + timedelta(days=1))
    with pytest.raises(ValidationError, match="reviewed listing alias"):
        CollectionRequest.model_validate(payload)


@pytest.mark.parametrize("bad", [Decimal("NaN"), Decimal("Infinity"), Decimal("-1")])
def test_exact_prices_are_finite_and_nonnegative(bad: Decimal) -> None:
    with pytest.raises(ValidationError):
        PricePoint(
            event_time=NOW,
            open=bad,
            high=Decimal(2),
            low=Decimal(0),
            close=Decimal(1),
            volume=Decimal(10),
        )


def test_quality_cannot_claim_complete_when_rows_are_missing() -> None:
    with pytest.raises(ValidationError, match="collection status"):
        CollectionQuality(status="collected", accepted=2, rejected=0, missing_sessions=(NOW,))


def test_commit_cannot_be_backdated_before_receipt() -> None:
    req = request()
    with pytest.raises(ValidationError, match="precede receipt"):
        PriceCommit(
            commit_id=req.run_id,
            partition_id=req.partition.partition_id,
            predecessor_id=None,
            window=req.window,
            committed_at=NOW,
            received_at=NOW + timedelta(seconds=1),
            quality=CollectionQuality(status="collected", accepted=1, rejected=0),
        )
