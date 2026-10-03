"""Evidence references connect normalized records to immutable source artifacts."""

from __future__ import annotations

from pydantic import AwareDatetime

from graphvest_contracts.domain.base import Confidence, Model, NonEmpty


class Provenance(Model):
    source: NonEmpty
    source_record_id: NonEmpty
    source_version: NonEmpty
    raw_artifact_id: NonEmpty
    content_hash: NonEmpty
    source_url: str | None = None
    document_id: str | None = None
    filing_accession: str | None = None
    extraction_location: str | None = None
    published_at: AwareDatetime | None = None
    extracted_at: AwareDatetime
    extractor_version: NonEmpty
    confidence: Confidence = 1.0
