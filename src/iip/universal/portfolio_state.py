"""Portfolio-wide asset state and exposure contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PositionState:
    ticker: str
    quantity: float
    market_value: float
    weight: float
    asset_class: str
    structure: str | None = None
    segment: str | None = None
    manager: str | None = None
    risk_profile: str | None = None


@dataclass(frozen=True)
class PortfolioState:
    as_of: str
    positions: tuple[PositionState, ...]
    total_value: float

    def by_asset_class(self, asset_class: str) -> tuple[PositionState, ...]:
        return tuple(item for item in self.positions if item.asset_class == asset_class)

    def by_manager(self, manager: str) -> tuple[PositionState, ...]:
        return tuple(
            item
            for item in self.positions
            if item.manager and item.manager.casefold() == manager.casefold()
        )
