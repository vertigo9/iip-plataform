"""Credit-intelligence snapshot contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CreditSnapshot:
    ticker: str
    rating: str | None = None
    spread: float | None = None
    duration_years: float | None = None
    leverage: float | None = None
    default_flag: bool = False
    reserve: float | None = None
    indexers: tuple[str, ...] = ()


def credit_risk_flags(snapshot: CreditSnapshot) -> tuple[str, ...]:
    flags = []
    if snapshot.default_flag:
        flags.append("default_radar")
    if snapshot.leverage is not None and snapshot.leverage > 2.0:
        flags.append("high_leverage")
    if snapshot.duration_years is not None and snapshot.duration_years > 5:
        flags.append("long_duration")
    return tuple(flags)
