"""Immutable fact revisions: history is authoritative, series are projections.

A changing company fact (CEO, name, industry, headquarters, ticker) is never
overwritten. Each observation appends a ``FactRevision`` linked to its
predecessor via ``previous_revision_id`` (the ``PREVIOUS`` edge); restatements
use ``change_type="correct"`` and keep the original revision. Backtests read
revisions filtered by knowledge time, never series alone.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from graphvest_contracts.domain.base import Confidence, Knowledge, Model, NonEmpty
from graphvest_contracts.domain.provenance import Provenance

type ChangeType = Literal["assert", "correct", "retire"]

#: XBRL filing kind (ADR-012): 10-K/A and 10-Q/A are amendments, never
#: automatic restatements; restatement requires explicit issuer indication;
#: segment or presentation rewrites are recasts.
type FilingKind = Literal["initial", "amendment", "recast", "restatement"]

#: Correction precedence for equal knowledge times: retirements win over
#: corrections, corrections over first assertions. Lexical revision IDs never
#: decide semantics; they only break exact ties for bit-determinism.
CHANGE_RANK: dict[ChangeType, int] = {"assert": 0, "correct": 1, "retire": 2}


class FactRevision(Model):
    revision_id: NonEmpty
    subject_id: NonEmpty
    key: NonEmpty
    value_type: Literal["string", "decimal", "entity", "boolean"]
    value_string: str | None = None
    value_decimal: Decimal | None = None
    value_entity_id: str | None = None
    value_boolean: bool | None = None
    effective_from: AwareDatetime
    effective_to: AwareDatetime | None = None
    knowledge: Knowledge
    evidence: tuple[Provenance, ...] = Field(min_length=1)
    revision_seq: int = Field(ge=1)
    previous_revision_id: str | None = None
    change_type: ChangeType = "assert"
    filing_kind: FilingKind = "initial"
    confidence: Confidence = 1.0

    @model_validator(mode="after")
    def validate_value(self) -> FactRevision:
        expected = {
            "string": self.value_string,
            "decimal": self.value_decimal,
            "entity": self.value_entity_id,
            "boolean": self.value_boolean,
        }[self.value_type]
        if expected is None:
            raise ValueError(f"value for {self.value_type} must be set")
        others = sum(
            value is not None
            for value in (
                self.value_string,
                self.value_decimal,
                self.value_entity_id,
                self.value_boolean,
            )
        )
        if others != 1:
            raise ValueError("exactly one value variant must be set")
        if self.revision_seq == 1 and self.previous_revision_id is not None:
            raise ValueError("first revision must not link a predecessor")
        if self.revision_seq > 1 and self.previous_revision_id is None:
            raise ValueError("later revisions must link their predecessor")
        if self.effective_to and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must follow effective_from")
        return self
