"""Enterprise audit trail."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditRecord:
    event_id: str
    portfolio_id: str
    operation: str
    evidence_ids: tuple[str, ...]


class AuditTrail:
    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    def append(self, record: AuditRecord) -> AuditRecord:
        self._records.append(record)
        return record

    def portfolio(self, portfolio_id: str) -> tuple[AuditRecord, ...]:
        return tuple(
            record for record in self._records if record.portfolio_id == portfolio_id
        )
