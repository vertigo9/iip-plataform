"""Source governance policy at enterprise scope."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourcePolicy:
    minimum_evidence: int
    require_provider: bool
    allow_stale: bool


def approve(
    *,
    evidence_count: int,
    provider_available: bool,
    stale: bool,
    policy: SourcePolicy,
) -> bool:
    return (
        evidence_count >= policy.minimum_evidence
        and (provider_available or not policy.require_provider)
        and (not stale or policy.allow_stale)
    )
