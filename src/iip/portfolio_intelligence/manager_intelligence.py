"""Manager-level intelligence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ManagerExposure:
    manager: str
    weight: float
    asset_count: int


def aggregate_manager(holdings) -> tuple[ManagerExposure, ...]:
    grouped = {}
    for holding in holdings:
        if not holding.manager:
            continue
        key = holding.manager
        weight, count = grouped.get(key, (0.0, 0))
        grouped[key] = (weight + holding.weight, count + 1)
    return tuple(
        ManagerExposure(manager, round(weight, 12), count)
        for manager, (weight, count) in sorted(
            grouped.items(), key=lambda item: (-item[1][0], item[0])
        )
    )
