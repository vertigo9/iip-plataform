"""Runtime matrix for manager/provider readiness."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderRuntimeState:
    provider: str
    certified: bool
    healthy: bool
    supported_assets: tuple[str, ...]


@dataclass(frozen=True)
class ProviderRuntimeMatrix:
    states: tuple[ProviderRuntimeState, ...]

    def ready(self) -> tuple[ProviderRuntimeState, ...]:
        return tuple(
            state for state in self.states if state.certified and state.healthy
        )
