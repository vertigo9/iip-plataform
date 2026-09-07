"""Structured risk model for funds and market instruments."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RiskLevel(StrEnum):
    BAIXO = "Baixo"
    MEDIO = "Médio"
    ALTO = "Alto"


@dataclass(frozen=True)
class RiskFactors:
    credit: RiskLevel | None = None
    market: RiskLevel | None = None
    liquidity: RiskLevel | None = None
    leverage: RiskLevel | None = None
    concentration: RiskLevel | None = None


@dataclass(frozen=True)
class RiskAssessment:
    overall: RiskLevel
    factors: RiskFactors
    rationale: tuple[str, ...] = ()


def assess_overall(factors: RiskFactors) -> RiskLevel:
    levels = [
        f
        for f in (
            factors.credit,
            factors.market,
            factors.liquidity,
            factors.leverage,
            factors.concentration,
        )
        if f is not None
    ]
    if not levels:
        return RiskLevel.MEDIO
    if RiskLevel.ALTO in levels:
        return RiskLevel.ALTO
    if levels.count(RiskLevel.MEDIO) >= 2:
        return RiskLevel.MEDIO
    return RiskLevel.BAIXO
