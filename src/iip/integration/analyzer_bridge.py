"""Adapters from existing analyzers into a normalized decision signal."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalyzerSnapshot:
    ticker: str
    valuation: float
    dividend: float
    quality: float
    risk: float
    opportunity: float
    thesis: str
    evidence_count: int


def normalize_analyzer_output(
    ticker: str,
    *,
    valuation: float,
    dividend: float,
    quality: float,
    risk: float,
    opportunity: float,
    thesis: str,
    evidence_count: int,
) -> AnalyzerSnapshot:
    values = {
        "valuation": valuation,
        "dividend": dividend,
        "quality": quality,
        "risk": risk,
        "opportunity": opportunity,
    }
    bounded = {key: max(0.0, min(10.0, float(value))) for key, value in values.items()}
    return AnalyzerSnapshot(
        ticker=ticker.upper(),
        valuation=bounded["valuation"],
        dividend=bounded["dividend"],
        quality=bounded["quality"],
        risk=bounded["risk"],
        opportunity=bounded["opportunity"],
        thesis=thesis.strip(),
        evidence_count=max(0, int(evidence_count)),
    )
