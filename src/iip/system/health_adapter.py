"""Unified system health adapter."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ComponentHealth:
    name: str
    healthy: bool
    reason: str


@dataclass(frozen=True)
class SystemHealth:
    components: tuple[ComponentHealth, ...]

    @property
    def healthy(self) -> bool:
        return bool(self.components) and all(item.healthy for item in self.components)

    def degraded(self) -> tuple[ComponentHealth, ...]:
        return tuple(item for item in self.components if not item.healthy)
