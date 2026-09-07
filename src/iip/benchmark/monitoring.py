"""Historical monitoring and service-level observations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ObservationCounter:
    observations: int = 0
    successful: int = 0
    failures: int = 0
    stale: int = 0

    def record(self, *, success: bool, stale: bool = False) -> None:
        self.observations += 1
        self.successful += int(success)
        self.failures += int(not success)
        self.stale += int(stale)

    @property
    def success_rate(self) -> float:
        return self.successful / self.observations if self.observations else 0.0

    @property
    def stale_rate(self) -> float:
        return self.stale / self.observations if self.observations else 0.0
