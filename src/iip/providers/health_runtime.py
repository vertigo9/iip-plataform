"""Runtime health aggregation for provider certification."""

from __future__ import annotations

from dataclasses import dataclass

from .certification import CertificationStatus, ProviderCertifier


@dataclass(frozen=True)
class RuntimeHealth:
    provider: str
    healthy: bool
    status: CertificationStatus | None
    reason: str


class RuntimeHealthService:
    def __init__(self, certifier: ProviderCertifier | None = None) -> None:
        self.certifier = certifier or ProviderCertifier()

    def check(self, provider: str) -> RuntimeHealth:
        item = self.certifier.certify(provider)
        if item is None:
            return RuntimeHealth(provider, False, None, "unknown_provider")

        return RuntimeHealth(
            provider=provider,
            healthy=item.status == CertificationStatus.CERTIFIED,
            status=item.status,
            reason=(
                "certified"
                if item.status == CertificationStatus.CERTIFIED
                else ";".join(item.notes) or item.status.value
            ),
        )
