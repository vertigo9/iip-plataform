"""Canonical reporting contract for IIP runs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportRow:
    ticker: str
    action: str
    score: float
    confidence: float
    evidence_count: int


@dataclass(frozen=True)
class PortfolioReport:
    generated_at: str
    rows: tuple[ReportRow, ...]

    def top(self, limit: int = 5) -> tuple[ReportRow, ...]:
        return tuple(
            sorted(self.rows, key=lambda row: (-row.score, row.ticker))[:limit]
        )
