"""Deterministic scoring engine."""

from __future__ import annotations

from .models import IntelligenceInput


def composite_score(item: IntelligenceInput) -> float:
    parts = (
        item.valuation_score,
        item.dividend_score,
        item.quality_score,
        item.opportunity_score,
    )
    bounded = tuple(max(0.0, min(10.0, value)) for value in parts)
    return round(sum(bounded) / len(bounded), 2)


def confidence_score(item: IntelligenceInput) -> float:
    base = min(1.0, len(item.evidence) / 3.0)
    risk_penalty = {
        "Baixo": 0.0,
        "Médio": 0.10,
        "Alto": 0.20,
    }.get(item.risk_level, 0.15)
    return round(max(0.0, min(1.0, base - risk_penalty)), 2)
