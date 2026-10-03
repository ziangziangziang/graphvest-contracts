"""Fact revisions: effective time and knowledge time are independent."""

from __future__ import annotations

from pydantic import AwareDatetime, Field, model_validator

from graphvest_contracts.domain.base import Attribute, Confidence, Knowledge, Model, NonEmpty
from graphvest_contracts.domain.provenance import Provenance
from graphvest_contracts.domain.revisions import ChangeType


class Relationship(Model):
    relationship_id: NonEmpty
    revision_id: NonEmpty
    source_entity_id: NonEmpty
    target_entity_id: NonEmpty
    kind: NonEmpty
    effective_from: AwareDatetime
    effective_to: AwareDatetime | None = None
    knowledge: Knowledge
    evidence: tuple[Provenance, ...] = Field(min_length=1)
    confidence: Confidence = 1.0
    attributes: tuple[Attribute, ...] = ()
    previous_revision_id: str | None = None
    change_type: ChangeType = "assert"
    revision_seq: int = Field(ge=1, default=1)
    pipeline_version: str = ""

    @model_validator(mode="after")
    def validate_interval(self) -> Relationship:
        if self.effective_to and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must follow effective_from")
        return self

    @model_validator(mode="after")
    def validate_chain(self) -> Relationship:
        if self.revision_seq == 1 and self.previous_revision_id is not None:
            raise ValueError("first revision must not link a predecessor")
        if self.revision_seq > 1 and self.previous_revision_id is None:
            raise ValueError("later revisions must link their predecessor")
        return self
