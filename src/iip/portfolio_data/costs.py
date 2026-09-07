"""Cost and fee models for portfolio assets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CostType(StrEnum):
    TRANSACTION = "TRANSACTION"
    BROKERAGE = "BROKERAGE"
    EXCHANGE = "EXCHANGE"
    CUSTODY = "CUSTODY"
    MANAGEMENT = "MANAGEMENT"
    ADMINISTRATION = "ADMINISTRATION"
    PERFORMANCE = "PERFORMANCE"
    OTHER = "OTHER"


@dataclass(frozen=True)
class CostItem:
    cost_type: CostType
    amount: float | None = None
    rate: float | None = None
    description: str | None = None


@dataclass(frozen=True)
class CostSnapshot:
    ticker: str
    items: tuple[CostItem, ...] = ()
    as_of: str | None = None

    @property
    def known_amount(self) -> float | None:
        amounts = [item.amount for item in self.items if item.amount is not None]
        if not amounts:
            return None
        return round(sum(amounts), 12)

    @property
    def known_rate(self) -> float | None:
        rates = [item.rate for item in self.items if item.rate is not None]
        if not rates:
            return None
        return round(sum(rates), 12)
