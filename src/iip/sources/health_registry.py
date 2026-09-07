"""Registry for provider health state."""

from __future__ import annotations

from .health import SourceHealth


class SourceHealthRegistry:
    """In-memory registry for normalized provider health state."""

    def __init__(self) -> None:
        self._health: dict[str, SourceHealth] = {}

    def register(self, health: SourceHealth) -> None:
        """Register or replace the health state for a provider."""
        self._health[health.provider] = health

    def get(self, provider: str) -> SourceHealth | None:
        """Return health state for a normalized provider name."""
        name = provider.strip().lower()

        if not name:
            return None

        return self._health.get(name)

    def clear(self) -> None:
        """Remove all registered health states."""
        self._health.clear()
