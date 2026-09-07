"""Enterprise consolidation contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioRef:
    portfolio_id: str
    version: int


@dataclass(frozen=True)
class ConsolidationInput:
    portfolios: tuple[PortfolioRef, ...]
    provider_count: int
    evidence_count: int
    decision_count: int


@dataclass(frozen=True)
class ConsolidationResult:
    portfolio_count: int
    unique_portfolios: int
    provider_count: int
    evidence_count: int
    decision_count: int
    consistent: bool
