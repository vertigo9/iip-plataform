"""Production simulation gate: no live execution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SimulationGate:
    system_e2e_green: bool
    regression_green: bool
    health_green: bool
    live_execution_enabled: bool = False

    @property
    def pass_gate(self) -> bool:
        return (
            self.system_e2e_green
            and self.regression_green
            and self.health_green
            and not self.live_execution_enabled
        )
