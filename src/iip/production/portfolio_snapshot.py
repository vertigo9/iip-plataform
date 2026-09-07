"""Immutable portfolio snapshot contract."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioSnapshot:
    as_of: str
    positions: tuple[tuple[str, float], ...]
    total_value: float

    def weight(self, ticker: str) -> float:
        for item, value in self.positions:
            if item.upper() == ticker.upper():
                return value / self.total_value if self.total_value > 0 else 0.0
        return 0.0
