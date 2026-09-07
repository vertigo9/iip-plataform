"""Evidence normalization and deduplication."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .contracts import Evidence


def content_hash(content: bytes) -> str:
    return sha256(content).hexdigest()


@dataclass
class EvidenceStore:
    _items: dict[str, Evidence]

    def __init__(self) -> None:
        self._items = {}

    def put(self, evidence: Evidence) -> str:
        previous = self._items.get(evidence.evidence_id)
        if previous == evidence:
            return "UNCHANGED"
        self._items[evidence.evidence_id] = evidence
        return "UPDATED" if previous is not None else "CREATED"

    def get(self, evidence_id: str) -> Evidence | None:
        return self._items.get(evidence_id)

    def all(self) -> tuple[Evidence, ...]:
        return tuple(self._items.values())
