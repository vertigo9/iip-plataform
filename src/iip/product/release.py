"""Release gate and full product E2E."""

from __future__ import annotations

from dataclasses import dataclass

from .readiness import Readiness


@dataclass(frozen=True)
class ReleaseGate:
    version: str
    readiness: Readiness

    @property
    def releasable(self) -> bool:
        return self.readiness.ready


def evaluate_release(version: str, readiness: Readiness) -> ReleaseGate:
    return ReleaseGate(version, readiness)
