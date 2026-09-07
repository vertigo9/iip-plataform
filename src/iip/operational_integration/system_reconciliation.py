"""Cross-layer reconciliation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReconciliationSummary:
    expected: int
    observed: int
    missing: tuple[str, ...]
    unexpected: tuple[str, ...]

    @property
    def consistent(self) -> bool:
        return (
            not self.missing and not self.unexpected and self.expected == self.observed
        )


def reconcile(
    expected: tuple[str, ...], observed: tuple[str, ...]
) -> ReconciliationSummary:
    expected_set = set(expected)
    observed_set = set(observed)
    return ReconciliationSummary(
        expected=len(expected_set),
        observed=len(observed_set),
        missing=tuple(sorted(expected_set - observed_set)),
        unexpected=tuple(sorted(observed_set - expected_set)),
    )
