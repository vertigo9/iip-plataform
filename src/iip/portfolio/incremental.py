"""Incremental document synchronization primitives."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True)
class IncrementalDocument:
    document_id: str
    content_hash: str


class IncrementalTracker:
    """Track canonical document hashes without touching Knowledge storage."""

    def __init__(self) -> None:
        self._hashes: dict[str, str] = {}

    @staticmethod
    def hash_content(content: bytes) -> str:
        return sha256(content).hexdigest()

    def classify(self, document: IncrementalDocument) -> str:
        previous = self._hashes.get(document.document_id)
        if previous is None:
            return "CREATED"
        if previous == document.content_hash:
            return "UNCHANGED"
        return "UPDATED"

    def remember(self, document: IncrementalDocument) -> str:
        status = self.classify(document)
        self._hashes[document.document_id] = document.content_hash
        return status
