"""Schedule contracts with explicit cadence and safe enablement."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScheduleSpec:
    name: str
    cadence: str
    timezone: str = "America/Sao_Paulo"
    enabled: bool = False


def validate_schedule(spec: ScheduleSpec) -> tuple[bool, tuple[str, ...]]:
    errors = []
    if not spec.name.strip():
        errors.append("missing_name")
    if not spec.cadence.strip():
        errors.append("missing_cadence")
    if not spec.timezone.strip():
        errors.append("missing_timezone")
    return (not errors, tuple(errors))
