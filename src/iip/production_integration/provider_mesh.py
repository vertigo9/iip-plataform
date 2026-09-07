"""Multi-provider capability mesh for production routing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderCapability:
    provider: str
    asset_classes: tuple[str, ...]
    healthy: bool
    priority: int


def candidates(
    capabilities: tuple[ProviderCapability, ...],
    asset_class: str,
) -> tuple[ProviderCapability, ...]:
    target = asset_class.casefold()
    return tuple(
        sorted(
            (
                item
                for item in capabilities
                if item.healthy and target in {x.casefold() for x in item.asset_classes}
            ),
            key=lambda item: (item.priority, item.provider),
        )
    )
