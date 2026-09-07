"""Operational monitoring counters for the enterprise pipeline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PipelineMonitor:
    runs: int = 0
    successes: int = 0
    failures: int = 0
    degraded: int = 0

    def record(self, status: str) -> None:
        self.runs += 1
        if status == "success":
            self.successes += 1
        elif status == "failed":
            self.failures += 1
        elif status == "degraded":
            self.degraded += 1

    @property
    def success_rate(self) -> float:
        return self.successes / self.runs if self.runs else 0.0
