"""Multi-dimensional portfolio concentration analysis."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .portfolio_state import PositionState


@dataclass(frozen=True)
class ConcentrationItem:
    dimension: str
    value: str
    weight: float
    limit: float
    breached: bool = False


def concentration(
    positions: tuple[PositionState, ...],
    dimension: str,
    limit: float,
    *,
    include_below_limit: bool = False,
) -> tuple[ConcentrationItem, ...]:
    grouped = defaultdict(float)
    for position in positions:
        value = getattr(position, dimension, None)
        if value:
            grouped[str(value)] += position.weight

    items = []
    for value, weight in sorted(grouped.items()):
        breached = weight > limit
        if breached or include_below_limit:
            items.append(
                ConcentrationItem(
                    dimension=dimension,
                    value=value,
                    weight=round(weight, 12),
                    limit=limit,
                    breached=breached,
                )
            )
    return tuple(items)


def all_concentrations(
    positions: tuple[PositionState, ...],
    *,
    manager_limit: float = 0.20,
    segment_limit: float = 0.25,
    class_limit: float = 0.50,
) -> tuple[ConcentrationItem, ...]:
    # This is a portfolio exposure report, not only an alert list. Therefore
    # each dimension is represented even when no threshold is breached.
    return (
        concentration(positions, "manager", manager_limit, include_below_limit=True)
        + concentration(positions, "segment", segment_limit, include_below_limit=True)
        + concentration(positions, "asset_class", class_limit, include_below_limit=True)
    )


def concentration_alerts(
    positions: tuple[PositionState, ...],
    *,
    manager_limit: float = 0.20,
    segment_limit: float = 0.25,
    class_limit: float = 0.50,
) -> tuple[ConcentrationItem, ...]:
    return (
        concentration(positions, "manager", manager_limit)
        + concentration(positions, "segment", segment_limit)
        + concentration(positions, "asset_class", class_limit)
    )
