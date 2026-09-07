"""Backward compatibility checks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CompatibilityResult:
    compatible: bool
    missing: tuple[str, ...]
    extra: tuple[str, ...]


def compare_keys(
    expected: tuple[str, ...],
    actual: tuple[str, ...],
) -> CompatibilityResult:
    expected_set = set(expected)
    actual_set = set(actual)
    return CompatibilityResult(
        compatible=expected_set <= actual_set,
        missing=tuple(sorted(expected_set - actual_set)),
        extra=tuple(sorted(actual_set - expected_set)),
    )
