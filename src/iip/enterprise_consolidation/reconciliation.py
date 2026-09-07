"""Enterprise cross-layer reconciliation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReconciliationResult:
    matched: int
    missing: int
    unexpected: int

    @property
    def consistent(self) -> bool:
        return self.missing == 0 and self.unexpected == 0


def compare(
    expected: tuple[str, ...],
    observed: tuple[str, ...],
) -> ReconciliationResult:
    expected_set = {x.upper() for x in expected}
    observed_set = {x.upper() for x in observed}
    return ReconciliationResult(
        len(expected_set & observed_set),
        len(expected_set - observed_set),
        len(observed_set - expected_set),
    )
