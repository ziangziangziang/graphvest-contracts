"""Shared revision selection; filter corrected identity/time only after selection.

Precedence for equal knowledge times is explicit, never lexical: higher
``revision_seq`` (chain position) wins, then change rank
(``retire > correct > assert``), then ``pipeline_version``. Lexical IDs only
break exact ties so repeated queries are bit-deterministic.
"""

from collections.abc import Iterable
from datetime import datetime

from graphvest_contracts.domain.base import Window
from graphvest_contracts.domain.market import Observation
from graphvest_contracts.domain.relationships import Relationship
from graphvest_contracts.domain.revisions import CHANGE_RANK


def latest_relationships(
    records: Iterable[Relationship], entity_id: str, *, effective_at: datetime, as_of: datetime
) -> tuple[Relationship, ...]:
    latest: dict[str, Relationship] = {}
    for relation in sorted(
        records,
        key=lambda r: (
            r.knowledge.available_at,
            r.revision_seq,
            CHANGE_RANK[r.change_type],
            r.pipeline_version,
            r.relationship_id,
            r.revision_id,
        ),
    ):
        if relation.knowledge.available_at <= as_of:
            latest[relation.relationship_id] = relation
    return tuple(
        r
        for r in latest.values()
        if (
            entity_id in (r.source_entity_id, r.target_entity_id)
            and r.effective_from <= effective_at
            and (r.effective_to is None or effective_at < r.effective_to)
        )
    )


def latest_observations(
    records: Iterable[Observation], security_id: str, window: Window, *, as_of: datetime
) -> tuple[Observation, ...]:
    latest: dict[str, Observation] = {}
    for observation in sorted(
        records,
        key=lambda r: (
            r.knowledge.available_at,
            r.revision_seq,
            r.observation_id,
            r.revision_id,
        ),
    ):
        if observation.knowledge.available_at <= as_of:
            latest[observation.observation_id] = observation
    return tuple(
        sorted(
            (
                r
                for r in latest.values()
                if (
                    r.security_id == security_id
                    and window.period_start <= r.event_time < window.period_end
                    and r.event_time <= as_of
                )
            ),
            key=lambda r: (r.event_time, r.observation_id),
        )
    )
