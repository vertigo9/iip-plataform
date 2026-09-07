"""Audit/evidence traceability."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    operation: str
    actor: str
    evidence_ids: tuple[str, ...]
    timestamp: str


class AuditLog:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def record(self, event: AuditEvent) -> AuditEvent:
        self._events.append(event)
        return event

    def for_operation(self, operation: str) -> tuple[AuditEvent, ...]:
        return tuple(event for event in self._events if event.operation == operation)
