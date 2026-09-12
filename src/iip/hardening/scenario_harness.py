"""Realistic end-to-end scenario harness."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioCase:
    name: str
    inputs: dict[str, object]


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    passed: bool
    detail: str = ""


def run(
    cases: tuple[ScenarioCase, ...],
    executor: Callable[[ScenarioCase], bool],
) -> tuple[ScenarioResult, ...]:
    results = []
    for case in cases:
        try:
            ok = bool(executor(case))
            results.append(ScenarioResult(case.name, ok))
        except Exception as exc:  # noqa: BLE001 — isola falha do executor num ScenarioResult, nao deixa propagar
            results.append(
                ScenarioResult(case.name, False, f"{type(exc).__name__}:{exc}")
            )
    return tuple(results)
