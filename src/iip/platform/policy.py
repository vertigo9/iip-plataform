"""Operational policy for safe source selection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REVIEW = "review"


@dataclass(frozen=True)
class SourcePolicyDecision:
    provider: str
    decision: PolicyDecision
    reason: str


class SafeSourcePolicy:
    """Fail closed for providers not certified by the caller."""

    def evaluate(
        self, provider: str, *, certified: bool, healthy: bool
    ) -> SourcePolicyDecision:
        if not certified:
            return SourcePolicyDecision(provider, PolicyDecision.DENY, "not_certified")
        if not healthy:
            return SourcePolicyDecision(provider, PolicyDecision.REVIEW, "unhealthy")
        return SourcePolicyDecision(
            provider, PolicyDecision.ALLOW, "certified_and_healthy"
        )
