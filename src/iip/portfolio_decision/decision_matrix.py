"""Multi-asset decision matrix."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionCell:
    ticker: str
    asset_class: str
    score: float
    confidence: float
    risk: float
    action: str


@dataclass(frozen=True)
class DecisionMatrix:
    cells: tuple[DecisionCell, ...]

    def actionable(self) -> tuple[DecisionCell, ...]:
        return tuple(
            item
            for item in self.cells
            if item.action.upper() in {"APORTAR", "COMPRAR", "REDUZIR", "VENDER"}
        )
