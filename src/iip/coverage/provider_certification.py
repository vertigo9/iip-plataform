"""Provider certification coverage."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderCertification:
    provider: str
    certified: bool
    supported_classes: tuple[str, ...]
    checks_passed: int
    checks_total: int

    @property
    def coverage(self) -> float:
        return self.checks_passed / self.checks_total if self.checks_total > 0 else 0.0

    @property
    def ready(self) -> bool:
        return self.certified and self.coverage >= 0.90
