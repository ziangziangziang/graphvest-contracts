"""Typed envelopes preserve context as payload types change between stages."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from pydantic import AwareDatetime, Field

from graphvest_contracts.domain.base import Attribute, Knowledge, Model, NonEmpty
from graphvest_contracts.domain.identifiers import stable_id


class RawArtifact(Model):
    source: NonEmpty
    source_record_id: NonEmpty
    source_version: NonEmpty
    content: bytes
    media_type: NonEmpty
    source_url: str | None = None
    knowledge: Knowledge

    @property
    def content_hash(self) -> str:
        return sha256(self.content).hexdigest()

    @property
    def artifact_id(self) -> str:
        return stable_id(
            "raw",
            self.model_dump_json(include={"source", "source_record_id", "source_version"})
            + self.content_hash,
        )


class Context(Model):
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    pipeline_run_id: NonEmpty
    source: NonEmpty
    source_record_id: NonEmpty
    source_version: NonEmpty
    raw_artifact_id: NonEmpty
    content_hash: NonEmpty
    pipeline_version: NonEmpty
    event_time: AwareDatetime | None = None
    knowledge: Knowledge
    metadata: tuple[Attribute, ...] = ()

    @property
    def processing_key(self) -> str:
        return stable_id("processing", f"{self.raw_artifact_id}:{self.pipeline_version}")


class Envelope[T](Model):
    context: Context
    payload: T

    def with_payload[U](self, payload: U) -> Envelope[U]:
        return Envelope[U](context=self.context, payload=payload)


def utc_now() -> datetime:
    return datetime.now(UTC)
