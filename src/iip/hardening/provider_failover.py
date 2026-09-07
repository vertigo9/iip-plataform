"""Multi-provider failover policy."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderState:
    name: str
    healthy: bool
    priority: int


def choose_provider(states: tuple[ProviderState, ...]) -> ProviderState | None:
    eligible = [state for state in states if state.healthy]
    return min(eligible, key=lambda x: (x.priority, x.name), default=None)
