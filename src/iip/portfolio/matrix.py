"""Provider implementation matrix used by the IIP roadmap."""

from __future__ import annotations

from dataclasses import dataclass

from iip.providers.registry import (
    FUND_MANAGERS,
    ProviderStatus,
    manifest_map,
)


@dataclass(frozen=True)
class ProviderRoadmapItem:
    provider: str
    status: ProviderStatus
    has_source_mapping: bool
    implementation: str | None
    next_step: str


def build_provider_roadmap() -> tuple[ProviderRoadmapItem, ...]:
    manifests = manifest_map()
    return tuple(
        ProviderRoadmapItem(
            provider=name,
            status=manifests[name].status,
            has_source_mapping=True,
            implementation=manifests[name].implementation,
            next_step=(
                "maintain_and_expand_tests"
                if manifests[name].status == ProviderStatus.READY
                else "validate_institutional_source_then_implement"
            ),
        )
        for name in FUND_MANAGERS
    )
