"""M1a contracts checks: boundaries, serialization, temporal semantics."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from graphvest_contracts import __version__
from graphvest_contracts.domain.base import Attribute, Knowledge, Model, Window
from graphvest_contracts.domain.entities import Entity
from graphvest_contracts.domain.events import CorporateAction, Event, ReportedObservation
from graphvest_contracts.domain.evidence import IngestCursor, IngestRun, SourceArtifact
from graphvest_contracts.domain.identifiers import Identifier, stable_id
from graphvest_contracts.domain.identity import Company, Listing, Security, relation_id
from graphvest_contracts.domain.market import Bar, EquityTrade, OptionContract
from graphvest_contracts.domain.provenance import Provenance
from graphvest_contracts.domain.relationships import Relationship
from graphvest_contracts.domain.revisions import CHANGE_RANK, FactRevision
from graphvest_contracts.errors import (
    DataPipeError,
    PersistenceError,
    PipelineStageError,
    TransientSourceError,
)
from graphvest_contracts.ingestion import Context, Envelope, RawArtifact
from graphvest_contracts.temporal import latest_observations, latest_relationships

FORBIDDEN_IMPORT_FRAGMENTS = (
    "graphvest_datapipe",
    "graphvest_storage",
    "graphvest_analytics",
    "graphvest_backend",
    "graphvest_frontend",
)


def _utc(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


def _knowledge(
    first: datetime,
    ingested: datetime,
    published: datetime | None = None,
) -> Knowledge:
    return Knowledge(published_at=published, first_observed_at=first, ingested_at=ingested)


def _provenance(raw_id: str = "artifact-1") -> Provenance:
    return Provenance(
        source="test-source",
        source_record_id="rec-1",
        source_version="1",
        raw_artifact_id=raw_id,
        content_hash="ab" * 32,
        extracted_at=_utc(2025, 1, 2),
        extractor_version="test-v1",
    )


def test_version_is_pinned() -> None:
    assert __version__ == "0.1.0"


def test_no_forbidden_module_dependencies() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "graphvest_contracts"
    offenders: list[str] = []
    for path in sorted(root.rglob("*.py")):
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                for fragment in FORBIDDEN_IMPORT_FRAGMENTS:
                    if fragment in stripped:
                        offenders.append(f"{path.name}:{lineno}: {stripped}")
    assert offenders == []


def test_public_import_surface() -> None:
    import graphvest_contracts.ingestion as ingestion_module
    import graphvest_contracts.repositories.events as events_repo
    import graphvest_contracts.repositories.graph as graph_repo
    import graphvest_contracts.repositories.raw as raw_repo
    import graphvest_contracts.repositories.state as state_repo
    import graphvest_contracts.repositories.timeseries as ts_repo
    import graphvest_contracts.temporal as temporal_module

    assert issubclass(Model, object)
    state_methods = ("is_processed", "mark_processed", "get_checkpoint", "set_checkpoint")
    graph_methods = ("put_entity", "get_entity", "put_relationship", "neighbors")
    for protocol, methods in (
        (graph_repo.GraphRepository, graph_methods),
        (ts_repo.TimeSeriesRepository, ("put", "query")),
        (events_repo.EventRepository, ("put", "get")),
        (raw_repo.RawObjectStore, ("put", "get")),
        (state_repo.StateRepository, state_methods),
    ):
        for method in methods:
            assert hasattr(protocol, method), f"{protocol.__name__} missing {method}"
    assert hasattr(temporal_module, "latest_relationships")
    assert hasattr(temporal_module, "latest_observations")
    assert hasattr(ingestion_module, "Envelope")


def test_knowledge_available_at_is_conservative_max() -> None:
    knowledge = _knowledge(_utc(2025, 6, 30), _utc(2025, 7, 1), _utc(2025, 8, 3))
    assert knowledge.available_at == _utc(2025, 8, 3)


def test_june_quarter_report_invisible_before_publication() -> None:
    """A June-quarter report published Aug 3 cannot appear in a July 15 view."""
    knowledge = _knowledge(_utc(2025, 6, 30), _utc(2025, 8, 3), _utc(2025, 8, 3))
    assert knowledge.available_at > _utc(2025, 7, 15)


def test_knowledge_rejects_first_observed_after_ingest() -> None:
    with pytest.raises(PydanticValidationError):
        _knowledge(_utc(2025, 7, 2), _utc(2025, 7, 1))


def test_stable_id_is_deterministic_and_namespaced() -> None:
    assert stable_id("ns", "key") == stable_id("ns", "key")
    assert stable_id("ns-a", "key") != stable_id("ns-b", "key")


def test_ticker_identifier_requires_scope() -> None:
    with pytest.raises(PydanticValidationError):
        Identifier(scheme="ticker", value="AMD")
    scoped = Identifier(scheme="ticker", value="AMD", scope="XNAS")
    assert scoped.scope == "XNAS"


def test_identity_views_produce_typed_entities() -> None:
    company = Company(company_id="co-amd", name="Advanced Micro Devices", cik="2488")
    security = Security(security_id="sec-amd", issuer_company_id="co-amd")
    listing = Listing(listing_id="list-amd", security_id="sec-amd", ticker="AMD", exchange="XNAS")
    assert company.as_entity().identifiers[0].value == "0000002488"
    assert listing.as_entity().identifiers[0].scope == "XNAS"
    assert security.as_entity().kind == "Security"
    assert relation_id("HOLDS", "a", "b") == "rel:holds:a:b"


def test_decimal_precision_survives_json_round_trip() -> None:
    trade = EquityTrade(
        observation_id="obs-1",
        revision_id="v1",
        security_id="sec-amd",
        event_time=_utc(2025, 1, 2),
        knowledge=_knowledge(_utc(2025, 1, 2), _utc(2025, 1, 2)),
        provenance=_provenance(),
        price=Decimal("123.45"),
        size=Decimal("10"),
        venue="XNAS",
    )
    restored = EquityTrade.model_validate_json(trade.model_dump_json())
    assert restored == trade
    assert json.loads(trade.model_dump_json())["price"] == "123.45"


def test_bar_rejects_ohlc_outliers() -> None:
    with pytest.raises(PydanticValidationError):
        Bar(
            observation_id="obs-b",
            revision_id="v1",
            security_id="sec-amd",
            event_time=_utc(2025, 1, 2),
            knowledge=_knowledge(_utc(2025, 1, 2), _utc(2025, 1, 2)),
            provenance=_provenance(),
            interval="1d",
            open=Decimal("10"),
            high=Decimal("11"),
            low=Decimal("9"),
            close=Decimal("99"),
            volume=Decimal("100"),
        )


def test_corporate_action_payload_rules() -> None:
    knowledge = _knowledge(_utc(2025, 1, 2), _utc(2025, 1, 2))
    split = CorporateAction(
        action_id="a1",
        security_id="sec-amd",
        action_type="split",
        ex_time=_utc(2025, 1, 3),
        split_factor=Decimal("4"),
        knowledge=knowledge,
        evidence=(_provenance(),),
    )
    assert split.split_factor == Decimal("4")
    with pytest.raises(PydanticValidationError):
        CorporateAction(
            action_id="a2",
            security_id="sec-amd",
            action_type="dividend",
            ex_time=_utc(2025, 1, 3),
            split_factor=Decimal("4"),
            knowledge=knowledge,
            evidence=(_provenance(),),
        )


def _relationship(
    rel_id: str,
    rev_id: str,
    seq: int,
    change: str,
    available: datetime,
    effective_from: datetime,
) -> Relationship:
    return Relationship(
        relationship_id=rel_id,
        revision_id=rev_id,
        source_entity_id="co-amd",
        target_entity_id="co-intc",
        kind="SUPPLIES",
        effective_from=effective_from,
        knowledge=_knowledge(_utc(2025, 1, 1), available),
        evidence=(_provenance(),),
        previous_revision_id=None if seq == 1 else "r1",
        change_type=change,  # type: ignore[arg-type]
        revision_seq=seq,
        pipeline_version="p1",
    )


def test_latest_relationship_prefers_correction_over_assertion() -> None:
    available = _utc(2025, 2, 1)
    first = _relationship("rel-1", "r1", 1, "assert", available, _utc(2025, 1, 1))
    corrected = _relationship("rel-1", "r2", 2, "correct", available, _utc(2025, 1, 1))
    picked = latest_relationships(
        [first, corrected], "co-amd", effective_at=_utc(2025, 3, 1), as_of=_utc(2025, 3, 2)
    )
    assert [r.revision_id for r in picked] == ["r2"]
    assert CHANGE_RANK["correct"] > CHANGE_RANK["assert"]


def test_latest_relationship_hides_future_knowledge() -> None:
    rel = _relationship("rel-9", "r1", 1, "assert", _utc(2025, 5, 1), _utc(2025, 1, 1))
    as_of = _utc(2025, 2, 1)
    picked = latest_relationships([rel], "co-amd", effective_at=_utc(2025, 3, 1), as_of=as_of)
    assert picked == ()


def _bar(obs_id: str, rev: str, event: datetime, known: datetime) -> Bar:
    return Bar(
        observation_id=obs_id,
        revision_id=rev,
        security_id="sec-amd",
        event_time=event,
        knowledge=_knowledge(event, known),
        provenance=_provenance(),
        interval="1d",
        open=Decimal("10"),
        high=Decimal("12"),
        low=Decimal("9"),
        close=Decimal("11"),
        volume=Decimal("100"),
    )


def test_latest_observations_use_half_open_window_and_cutoff() -> None:
    window = Window(period_start=_utc(2025, 1, 2), period_end=_utc(2025, 1, 4))
    inside = _bar("o1", "v1", _utc(2025, 1, 2), _utc(2025, 1, 2))
    edge_end = _bar("o2", "v1", _utc(2025, 1, 4), _utc(2025, 1, 4))
    future_known = _bar("o3", "v1", _utc(2025, 1, 3), _utc(2025, 2, 1))
    picked = latest_observations(
        [inside, edge_end, future_known], "sec-amd", window, as_of=_utc(2025, 1, 5)
    )
    assert [o.observation_id for o in picked] == ["o1"]


def test_event_and_reported_observation_round_trip() -> None:
    knowledge = _knowledge(_utc(2025, 1, 2), _utc(2025, 1, 2))
    event = Event(
        event_id="ev-1",
        kind="earnings",
        entity_ids=("co-amd",),
        event_time=_utc(2025, 1, 2),
        knowledge=knowledge,
        evidence=(_provenance(),),
        description="Q4 earnings",
    )
    reported = ReportedObservation(
        observation_id="ro-1",
        revision_id="v1",
        entity_id="co-amd",
        metric="revenue",
        value=Decimal("6804000000"),
        unit="USD",
        window=Window(period_start=_utc(2024, 10, 1), period_end=_utc(2025, 1, 1)),
        knowledge=knowledge,
        evidence=(_provenance(),),
    )
    assert Event.model_validate(event.model_dump()) == event
    assert ReportedObservation.model_validate(reported.model_dump()) == reported


def test_fact_revision_chain_rules() -> None:
    knowledge = _knowledge(_utc(2025, 1, 2), _utc(2025, 1, 2))
    with pytest.raises(PydanticValidationError):
        FactRevision(
            revision_id="r1",
            subject_id="co-amd",
            key="ceo",
            value_type="string",
            value_string="A",
            effective_from=_utc(2025, 1, 1),
            knowledge=knowledge,
            evidence=(_provenance(),),
            revision_seq=2,
            previous_revision_id=None,
        )


def test_ingestion_envelope_preserves_context_across_payloads() -> None:
    knowledge = _knowledge(_utc(2025, 1, 2), _utc(2025, 1, 2))
    raw = RawArtifact(
        source="test",
        source_record_id="r1",
        source_version="1",
        content=b"hello",
        media_type="application/octet-stream",
        knowledge=knowledge,
    )
    context = Context(
        pipeline_run_id="run-1",
        source="test",
        source_record_id="r1",
        source_version="1",
        raw_artifact_id=raw.artifact_id,
        content_hash=raw.content_hash,
        pipeline_version="p1",
        knowledge=knowledge,
    )
    first: Envelope[Entity] = Envelope(
        context=context,
        payload=Entity(entity_id="e1", kind="Company", name="Example"),
    )
    second = first.with_payload(Attribute(name="n", value="v"))
    assert second.context == first.context
    assert second.payload == Attribute(name="n", value="v")


def test_source_artifact_rejects_tampered_content() -> None:
    import hashlib

    content = b"evidence-bytes"
    with pytest.raises(PydanticValidationError):
        SourceArtifact(
            artifact_id="art-1",
            source="s",
            source_record_id="r",
            source_version="1",
            media_type="application/octet-stream",
            sha256=hashlib.sha256(b"other").hexdigest(),
            fetched_at=_utc(2025, 1, 2),
            content=content,
        )


def test_operational_models_validate() -> None:
    cursor = IngestCursor(cursor_id="c1", source_id="s", updated_at=_utc(2025, 1, 2))
    run = IngestRun(run_id="r1", source_id="s", started_at=_utc(2025, 1, 2), status="running")
    assert cursor.cursor is None
    assert run.records_seen == 0


def test_option_contract_and_errors_validate() -> None:
    contract = OptionContract(
        option_id="opt-1",
        underlying_security_id="sec-amd",
        expiration=_utc(2025, 6, 20).date(),
        strike=Decimal("120"),
        put_call="call",
    )
    assert contract.put_call == "call"
    assert issubclass(TransientSourceError, DataPipeError)
    assert issubclass(PersistenceError, DataPipeError)
    err = TransientSourceError("throttled", retry_after_seconds=2.5)
    assert err.retry_after_seconds == 2.5
    staged = PipelineStageError("parse", "rec-1", "trace-1")
    assert staged.stage == "parse"
