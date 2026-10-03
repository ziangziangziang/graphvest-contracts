"""Stable identity split: Company / Security / Listing as typed Entity views.

A company never changes identity when its data changes; securities are issued
by companies; listings attach tickers (scoped, temporal) to securities on a
venue. Tickers are never primary IDs. Each constructor returns the storage
level :class:`Entity` so repository protocols are unchanged.
"""

from __future__ import annotations

from pydantic import model_validator

from graphvest_contracts.domain.base import Model, NonEmpty
from graphvest_contracts.domain.entities import Entity
from graphvest_contracts.domain.identifiers import Identifier

#: Current-graph projection edge kinds owned by the identity layer.
ISSUES = "ISSUES"
LISTED_AS = "LISTED_AS"


def relation_id(kind: str, source_id: str, target_id: str) -> str:
    """Stable materialized-edge ID, e.g. ``rel:holds:soxx:amd``."""
    return f"rel:{kind.lower()}:{source_id}:{target_id}"


class Company(Model):
    company_id: NonEmpty
    name: NonEmpty
    country: str | None = None
    cik: str | None = None

    @model_validator(mode="after")
    def validate_cik(self) -> Company:
        if self.cik is not None and not self.cik.isdigit():
            raise ValueError("CIK must be digits")
        return self

    def as_entity(self) -> Entity:
        identifiers: list[Identifier] = []
        if self.cik is not None:
            identifiers.append(Identifier(scheme="cik", value=self.cik.zfill(10)))
        return Entity(
            entity_id=self.company_id,
            kind="Company",
            name=self.name,
            identifiers=tuple(identifiers),
        )


class Security(Model):
    security_id: NonEmpty
    issuer_company_id: NonEmpty
    security_type: NonEmpty = "common"
    figi: str | None = None
    isin: str | None = None
    cusip: str | None = None

    def as_entity(self) -> Entity:
        identifiers: list[Identifier] = []
        if self.figi is not None:
            identifiers.append(Identifier(scheme="figi", value=self.figi))
        if self.isin is not None:
            identifiers.append(Identifier(scheme="isin", value=self.isin))
        if self.cusip is not None:
            identifiers.append(Identifier(scheme="cusip", value=self.cusip))
        return Entity(
            entity_id=self.security_id,
            kind="Security",
            name=self.security_id,
            identifiers=tuple(identifiers),
        )


class Listing(Model):
    listing_id: NonEmpty
    security_id: NonEmpty
    ticker: NonEmpty
    exchange: NonEmpty

    def as_entity(self) -> Entity:
        return Entity(
            entity_id=self.listing_id,
            kind="Listing",
            name=self.ticker,
            identifiers=(Identifier(scheme="ticker", value=self.ticker, scope=self.exchange),),
        )
