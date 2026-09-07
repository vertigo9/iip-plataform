"""Adaptive refresh policy based on source criticality and change frequency."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RefreshPolicy:
    criticality: int
    change_frequency: int
    max_age_hours: int


def build_policy(criticality: int, change_frequency: int) -> RefreshPolicy:
    criticality = max(1, min(5, int(criticality)))
    change_frequency = max(1, min(5, int(change_frequency)))
    max_age = max(1, 48 - (criticality * 6 + change_frequency * 3))
    return RefreshPolicy(criticality, change_frequency, max_age)
