"""Production configuration with fail-closed defaults."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProductionConfig:
    environment: str = "development"
    automation_enabled: bool = False
    live_execution_enabled: bool = False
    require_source_certification: bool = True
    require_evidence: bool = True


def can_execute_live(config: ProductionConfig) -> bool:
    return (
        config.environment.lower() == "production"
        and config.automation_enabled
        and config.live_execution_enabled
        and config.require_source_certification
        and config.require_evidence
    )
