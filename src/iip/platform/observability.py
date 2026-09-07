"""Minimal deterministic runtime metrics without external dependencies."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RuntimeMetrics:
    executions: int = 0
    successes: int = 0
    failures: int = 0
    skipped: int = 0

    def record(self, state: str) -> None:
        self.executions += 1
        if state == "ready":
            self.successes += 1
        elif state == "failed":
            self.failures += 1
        elif state == "skipped":
            self.skipped += 1

    @property
    def success_rate(self) -> float:
        return self.successes / self.executions if self.executions else 0.0
