"""Quality radar combining explicit dimensions without inventing data."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QualityRadar:
    ticker: str
    fundamentals: float
    management: float
    governance: float
    balance_sheet: float

    @property
    def composite(self) -> float:
        values = (
            self.fundamentals,
            self.management,
            self.governance,
            self.balance_sheet,
        )
        bounded = [max(0.0, min(10.0, float(v))) for v in values]
        return round(sum(bounded) / len(bounded), 12)
