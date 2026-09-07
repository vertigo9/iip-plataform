"""Thesis and quality consolidation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThesisQuality:
    ticker: str
    thesis_state: str
    thesis_confidence: float
    quality_score: float
    evidence_count: int


def readiness(item: ThesisQuality) -> float:
    evidence = min(1.0, max(0, item.evidence_count) / 3.0)
    thesis = max(0.0, min(1.0, item.thesis_confidence))
    quality = max(0.0, min(10.0, item.quality_score)) / 10.0
    return round((evidence + thesis + quality) / 3.0, 12)
