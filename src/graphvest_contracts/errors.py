"""Adapter errors remain distinguishable; pipeline failures retain their cause."""

from __future__ import annotations


class DataPipeError(Exception):
    """Base error for expected pipeline failures."""


class TransientSourceError(DataPipeError):
    """Retryable transport or throttling error."""

    def __init__(self, message: str, *, retry_after_seconds: float | None = None) -> None:
        if retry_after_seconds is not None and retry_after_seconds < 0:
            raise ValueError("retry_after_seconds must not be negative")
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message)


class PermanentSourceError(DataPipeError):
    """Non-retryable source request failure."""


class ParseError(DataPipeError):
    """Source bytes could not be parsed."""


class ValidationError(DataPipeError):
    """A business invariant failed after parsing."""


class EntityResolutionError(DataPipeError):
    """No unambiguous entity match was available."""


class PersistenceError(DataPipeError):
    """Storage rejected a write or could not complete it."""


class AnalyticsError(DataPipeError):
    """Calculation inputs or execution were invalid."""


class PipelineStageError(DataPipeError):
    def __init__(self, stage: str, record_id: str, trace_id: str) -> None:
        self.stage = stage
        self.record_id = record_id
        self.trace_id = trace_id
        super().__init__(f"stage={stage} record={record_id} trace={trace_id}")
