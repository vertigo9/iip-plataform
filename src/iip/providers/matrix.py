"""Fund provider roadmap."""

from __future__ import annotations

from dataclasses import dataclass

from .registry import FUND_MANAGERS, ProviderStatus, manifest_map


@dataclass(frozen=True)
class ProviderRoadmapItem:
    provider: str
    status: ProviderStatus
    has_source_mapping: bool
    implementation: str | None
    next_step: str


def build_provider_roadmap():
    manifests = manifest_map()
    return tuple(
        ProviderRoadmapItem(
            name,
            manifests[name].status,
            True,
            manifests[name].implementation,
            "maintain_and_expand_tests"
            if manifests[name].status == ProviderStatus.READY
            else "validate_institutional_source_then_implement",
        )
        for name in FUND_MANAGERS
    )
