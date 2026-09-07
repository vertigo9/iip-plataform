"""Routing using explicit source-health signals."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RouteCandidate:
    provider: str
    certified: bool
    healthy: bool
    priority: float


def choose(candidates: tuple[RouteCandidate, ...]) -> RouteCandidate | None:
    eligible = [item for item in candidates if item.certified and item.healthy]
    return max(eligible, key=lambda item: (item.priority, item.provider), default=None)
