"""E2E simulation helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class E2ECheck:
    name: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class E2EReport:
    checks: tuple[E2ECheck, ...]

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(item.passed for item in self.checks)


def run_checks(checks: tuple[tuple[str, Callable[[], Any]], ...]) -> E2EReport:
    results = []
    for name, check in checks:
        try:
            value = check()
            results.append(E2ECheck(name, bool(value), str(value)))
        except Exception as exc:  # noqa: BLE001 — isola falha de um check e2e, permite os demais rodarem
            results.append(E2ECheck(name, False, f"{type(exc).__name__}:{exc}"))
    return E2EReport(tuple(results))
