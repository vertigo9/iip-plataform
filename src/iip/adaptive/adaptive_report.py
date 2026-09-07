"""Adaptive operations summary."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdaptiveReport:
    run_id: str
    assets_processed: int
    anomalies: int
    alerts: int
    route_changes: int
    status: str

    @property
    def healthy(self) -> bool:
        return self.status == "ok"
