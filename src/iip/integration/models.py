"""Integrated portfolio decision contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Action(StrEnum):
    APORTAR = "APORTAR"
    MANTER = "MANTER"
    AGUARDAR = "AGUARDAR"
    REDUZIR = "REDUZIR"
    VENDER = "VENDER"


@dataclass(frozen=True)
class AssetSignal:
    ticker: str
    asset_class: str
    decision_score: float
    confidence: float
    action: Action
    evidence_count: int = 0


@dataclass(frozen=True)
class PortfolioConstraint:
    name: str
    maximum: float | None = None
    minimum: float | None = None


@dataclass(frozen=True)
class PortfolioDecision:
    ticker: str
    action: Action
    allocation_score: float
    rationale: str
