"""Portfolio reconciliation across holdings and snapshots."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Reconciliation:
    matched: tuple[str, ...]
    missing: tuple[str, ...]
    unexpected: tuple[str, ...]

    @property
    def consistent(self) -> bool:
        return not self.missing and not self.unexpected


def reconcile(
    expected: tuple[str, ...],
    observed: tuple[str, ...],
) -> Reconciliation:
    expected_set = {item.upper() for item in expected}
    observed_set = {item.upper() for item in observed}
    return Reconciliation(
        tuple(sorted(expected_set & observed_set)),
        tuple(sorted(expected_set - observed_set)),
        tuple(sorted(observed_set - expected_set)),
    )
