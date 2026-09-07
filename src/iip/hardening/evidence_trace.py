"""Evidence traceability across decision layers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceTrace:
    decision_id: str
    source_ids: tuple[str, ...]
    document_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return bool(self.source_ids) and bool(self.evidence_ids)
