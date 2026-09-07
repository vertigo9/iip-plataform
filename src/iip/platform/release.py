"""Release checkpoint metadata for accelerated development blocks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReleaseCheckpoint:
    milestone: str
    tests_expected: int
    coverage_target: int
    notes: tuple[str, ...] = ()

    def summary(self) -> str:
        return f"{self.milestone}: tests>={self.tests_expected}, coverage>={self.coverage_target}%"
