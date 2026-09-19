"""Gerador de alertas de rebalanceamento por desvio de alocação-alvo."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RebalanceAlert:
    asset_or_class: str
    current_weight: float
    target_weight: float
    drift: float
    action: str  # "APORTAR", "REDUZIR", "MANTER"


def generate_rebalancing_alerts(
    current_allocations: dict[str, float],
    target_allocations: dict[str, float],
    tolerance: float = 0.05,
) -> list[RebalanceAlert]:
    """Calcula desvios entre alocação atual e alvo e gera alertas de rebalanceamento."""
    alerts = []
    all_keys = set(current_allocations.keys()) | set(target_allocations.keys())

    for key in sorted(all_keys):
        curr = current_allocations.get(key, 0.0)
        target = target_allocations.get(key, 0.0)
        drift = curr - target

        if drift < -tolerance:
            action = "APORTAR"
        elif drift > tolerance:
            action = "REDUZIR"
        else:
            action = "MANTER"

        alerts.append(
            RebalanceAlert(
                asset_or_class=key,
                current_weight=round(curr, 4),
                target_weight=round(target, 4),
                drift=round(drift, 4),
                action=action,
            )
        )

    return alerts
