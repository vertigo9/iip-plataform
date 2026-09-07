"""Adapter from decision outputs to cycle observations."""

from __future__ import annotations


def normalize_decision(
    ticker: str,
    *,
    score: float | None,
    confidence: float | None,
    action: str | None,
) -> tuple[str, float | None, float | None, str | None]:
    normalized_score = max(0.0, min(10.0, float(score))) if score is not None else None
    normalized_confidence = (
        max(0.0, min(1.0, float(confidence))) if confidence is not None else None
    )
    return ticker.upper(), normalized_score, normalized_confidence, action
