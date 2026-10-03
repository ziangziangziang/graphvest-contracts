# graphvest-contracts

Shared domain contracts and repository protocols for GraphVest (M1a extract).

This package is the single authoritative home for financial domain records
(identity, entities, market observations, events, relationships, revisions,
evidence, provenance), ingestion envelopes (`RawArtifact`, `Context`,
`Envelope`), shared revision-selection semantics (`temporal`), repository
protocols (graph, time-series, events, raw store, state) and pipeline errors.

It depends only on `pydantic`. It must not import datapipe, storage,
analytics, vendor or backend modules; `tests/unit/test_contracts_m1a.py`
enforces that boundary along with serialization and temporal compatibility.

See `docs/IMPLEMENTATION-STATUS.md` in the integration root for the M1a
checkpoint.
