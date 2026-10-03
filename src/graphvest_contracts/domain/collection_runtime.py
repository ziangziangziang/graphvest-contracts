"""Durable single-writer collection operations and SEC metadata candidates."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, model_validator

from graphvest_contracts.domain.base import Model, NonEmpty
from graphvest_contracts.domain.collection import Sha256, SourceReceipt


class CollectionJobState(Model):
    job_id: NonEmpty
    definition_hash: Sha256
    status: Literal["ready", "running", "backoff", "blocked", "partial", "succeeded"] = "ready"
    attempt: int = Field(default=0, ge=0)
    updated_at: AwareDatetime
    next_due_at: AwareDatetime
    last_success_at: AwareDatetime | None = None
    last_result_id: str | None = None
    error_code: str | None = None
    repair_required: bool = False

    @model_validator(mode="after")
    def validate_state(self) -> CollectionJobState:
        if self.last_success_at is not None and self.last_success_at > self.updated_at:
            raise ValueError("success time must not exceed state time")
        if self.status in {"backoff", "blocked"} and self.error_code is None:
            raise ValueError("failed job must carry a safe error code")
        return self


class FilingMetadata(Model):
    """An accession is evidence of a filing, not a classified business event."""

    issuer_id: NonEmpty
    cik: Annotated[str, Field(pattern=r"^\d{10}$")]
    accession: Annotated[str, Field(pattern=r"^\d{10}-\d{2}-\d{6}$")]
    form: Annotated[str, Field(min_length=1, max_length=32)]
    filing_date: date
    report_date: date | None
    primary_document: Annotated[str, Field(min_length=1, max_length=256)]
    published_at: AwareDatetime | None
    publication_precision: Literal["source_timestamp", "unknown"]
    acceptance_raw: Annotated[str, Field(max_length=128)]
    items: Annotated[str, Field(max_length=256)] = ""
    occurred_at: None = None
    classification: Literal["filing_metadata_candidate"] = "filing_metadata_candidate"

    @model_validator(mode="after")
    def validate_publication(self) -> FilingMetadata:
        if (self.published_at is None) != (self.publication_precision == "unknown"):
            raise ValueError("publication precision must reflect the source timestamp")
        if "/" in self.primary_document or "\\" in self.primary_document:
            raise ValueError("primary document must be a filename")
        return self


class FilingMetadataRevision(Model):
    event_id: NonEmpty
    revision_id: NonEmpty
    predecessor_id: str | None
    sequence: int = Field(ge=1)
    first_seen_at: AwareDatetime
    recorded_at: AwareDatetime
    metadata: FilingMetadata
    content_hash: Sha256
    receipt_id: NonEmpty

    @model_validator(mode="after")
    def validate_times(self) -> FilingMetadataRevision:
        if (self.predecessor_id is None) != (self.sequence == 1):
            raise ValueError("revision sequence must reflect its predecessor")
        if self.recorded_at < self.first_seen_at:
            raise ValueError("revision must not precede first seen")
        if self.metadata.published_at and self.metadata.published_at > self.recorded_at:
            raise ValueError("future publication cannot become a visible event")
        return self


class FilingPollReceipt(Model):
    receipt_id: NonEmpty
    issuer_id: NonEmpty
    receipt: SourceReceipt
    supported_start: date
    supported_end: date
    selected_count: int = Field(ge=0, le=4096)
    historical_files_available: bool
    committed_at: AwareDatetime | None = None
    scope: Literal["recent_submissions_metadata"] = "recent_submissions_metadata"

    @model_validator(mode="after")
    def validate_commit(self) -> FilingPollReceipt:
        if self.committed_at is not None and self.committed_at < self.receipt.received_at:
            raise ValueError("filing poll commit must not precede receipt")
        if self.supported_end < self.supported_start:
            raise ValueError("filing poll coverage must be ordered")
        return self
