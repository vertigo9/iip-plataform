"""Evidence readiness for portfolio decisions."""

from __future__ import annotations


def evidence_ready(evidence_ids: tuple[str, ...]) -> bool:
    return bool(tuple(dict.fromkeys(evidence_ids)))
