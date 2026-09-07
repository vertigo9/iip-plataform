"""RMG/dashboard generation contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RMGSection:
    title: str
    metrics: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class RMGReport:
    as_of: str
    sections: tuple[RMGSection, ...]

    @property
    def metric_count(self) -> int:
        return sum(len(section.metrics) for section in self.sections)


def build(as_of: str, sections: tuple[RMGSection, ...]) -> RMGReport:
    return RMGReport(as_of, sections)
