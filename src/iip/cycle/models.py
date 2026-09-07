"""Closed-loop portfolio cycle contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CycleStatus(StrEnum):
    READY = "ready"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass(frozen=True)
class PortfolioAssetInput:
    ticker: str
    asset_class: str
    market_value: float
    weight: float
    score: float | None = None
    confidence: float | None = None
    action: str | None = None
    annual_income: float | None = None
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CycleObservation:
    ticker: str
    score: float | None
    confidence: float | None
    action: str | None
    weight: float
    annual_income: float
    evidence_count: int


@dataclass(frozen=True)
class PortfolioCycle:
    cycle_id: str
    as_of: str
    observations: tuple[CycleObservation, ...]
    status: CycleStatus
