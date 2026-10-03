"""Evidence and operational models: artifacts prove, cursors resume.

``SourceArtifact`` is the immutable evidence root: original source bytes with a
sha256 integrity hash. Payloads above the single-property comfort limit split
into ``ArtifactChunk`` vertices (ordered by ``chunk_index``). ``IngestCursor``
and ``IngestRun`` replace the transitional SQLite checkpoint store so all
persistent state lives in GraphFin (ADR-010).
"""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import AwareDatetime, Field, field_validator, model_validator

from graphvest_contracts.domain.base import Model, NonEmpty

#: Maximum raw bytes kept in one ``SourceArtifact.content`` BLOB. Live probes
#: stored 8 MB; stay well clear of wire/server limits and chunk above this.
ARTIFACT_INLINE_LIMIT = 4 * 1024 * 1024


class SourceArtifact(Model):
    artifact_id: NonEmpty
    source: NonEmpty
    source_record_id: NonEmpty
    source_version: NonEmpty
    media_type: NonEmpty
    source_url: str | None = None
    sha256: str
    published_at: AwareDatetime | None = None
    fetched_at: AwareDatetime
    content: bytes = Field(repr=False)
    chunked: bool = False

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value.lower()):
            raise ValueError("sha256 must be 64 hex characters")
        return value.lower()

    @model_validator(mode="after")
    def validate_integrity(self) -> SourceArtifact:
        if not self.chunked and hashlib.sha256(self.content).hexdigest() != self.sha256:
            raise ValueError("content does not match sha256")
        if not self.chunked and len(self.content) > ARTIFACT_INLINE_LIMIT:
            raise ValueError("content exceeds inline limit; use ArtifactChunk vertices")
        return self


class ArtifactChunk(Model):
    artifact_id: NonEmpty
    chunk_index: int = Field(ge=0)
    sha256: str
    content: bytes = Field(repr=False)


class DataSource(Model):
    source_id: NonEmpty
    description: str = ""


class IngestCursor(Model):
    cursor_id: NonEmpty
    source_id: NonEmpty
    cursor: str | None = None
    updated_at: AwareDatetime


class IngestRun(Model):
    run_id: NonEmpty
    source_id: NonEmpty
    started_at: AwareDatetime
    completed_at: AwareDatetime | None = None
    status: Literal["running", "succeeded", "failed"]
    records_seen: int = Field(ge=0, default=0)
    records_written: int = Field(ge=0, default=0)
