"""Reconciliation between generated decisions and persisted state."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReconciliationResult:
    consistent: bool
    missing: tuple[str, ...] = ()
    unexpected: tuple[str, ...] = ()


def reconcile(
    expected: tuple[str, ...], actual: tuple[str, ...]
) -> ReconciliationResult:
    expected_set = set(expected)
    actual_set = set(actual)
    return ReconciliationResult(
        consistent=expected_set == actual_set,
        missing=tuple(sorted(expected_set - actual_set)),
        unexpected=tuple(sorted(actual_set - expected_set)),
    )
