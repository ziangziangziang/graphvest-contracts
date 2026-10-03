"""Extensible entity categories; source schemas do not enter the domain."""

from __future__ import annotations

from graphvest_contracts.domain.base import Attribute, Model, NonEmpty
from graphvest_contracts.domain.identifiers import Identifier

ENTITY_KINDS = frozenset(
    {
        "Company",
        "LegalEntity",
        "Security",
        "Listing",
        "Fund",
        "ETF",
        "Index",
        "OptionContract",
        "Person",
        "Product",
        "ProductFamily",
        "Technology",
        "Industry",
        "GovernmentAgency",
        "Document",
        "Event",
        "EconomicSeries",
    }
)


class Entity(Model):
    entity_id: NonEmpty
    kind: NonEmpty
    name: NonEmpty
    identifiers: tuple[Identifier, ...] = ()
    attributes: tuple[Attribute, ...] = ()
