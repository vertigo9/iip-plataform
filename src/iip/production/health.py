"""Production health summary."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HealthSnapshot:
    suite_green: bool
    source_registry_healthy: bool
    knowledge_healthy: bool
    atlas_healthy: bool
    decision_engine_healthy: bool

    @property
    def production_healthy(self) -> bool:
        return all(
            (
                self.suite_green,
                self.source_registry_healthy,
                self.knowledge_healthy,
                self.atlas_healthy,
                self.decision_engine_healthy,
            )
        )
