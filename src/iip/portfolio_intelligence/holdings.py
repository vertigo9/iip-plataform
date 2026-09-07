"""Position and exposure intelligence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Holding:
    ticker: str
    weight: float
    asset_class: str
    manager: str | None = None
    segment: str | None = None
    risk_profile: str | None = None


def normalize_holdings(holdings: tuple[Holding, ...]) -> tuple[Holding, ...]:
    return tuple(
        Holding(
            ticker=h.ticker.upper(),
            weight=round(max(0.0, min(1.0, h.weight)), 12),
            asset_class=h.asset_class,
            manager=h.manager,
            segment=h.segment,
            risk_profile=h.risk_profile,
        )
        for h in holdings
    )
