"""Determinism checks for repeated executions."""

from __future__ import annotations


def equivalent(first, second) -> bool:
    return first == second


def stable_results(runs: tuple[object, ...]) -> bool:
    return bool(runs) and all(run == runs[0] for run in runs)
