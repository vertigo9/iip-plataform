"""Drawdown diagnostics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DrawdownDiagnostic:
    peak_value: float
    trough_value: float
    drawdown: float


def worst_drawdown(values: tuple[float, ...]) -> DrawdownDiagnostic:
    if not values:
        return DrawdownDiagnostic(0.0, 0.0, 0.0)
    peak = values[0]
    peak_value = peak
    trough_value = peak
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        current = (value / peak) - 1.0 if peak else 0.0
        if current < worst:
            worst = current
            peak_value = peak
            trough_value = value
    return DrawdownDiagnostic(
        peak_value=peak_value,
        trough_value=trough_value,
        drawdown=round(abs(worst), 12),
    )
