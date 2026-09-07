"""Health contract for IIP document providers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SourceHealth:
    """Current operational health state of a document provider."""

    provider: str
    enabled: bool = True
    available: bool = False
    last_success: datetime | None = None
    last_failure: datetime | None = None
    error_count: int = 0

    def __post_init__(self) -> None:
        provider = self.provider.strip().lower()

        if not provider:
            raise ValueError("provider must not be empty")

        if self.error_count < 0:
            raise ValueError("error_count must not be negative")

        object.__setattr__(self, "provider", provider)
