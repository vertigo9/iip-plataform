"""Enterprise portfolio registry."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioEntry:
    portfolio_id: str
    name: str
    enabled: bool = True


class PortfolioRegistry:
    def __init__(self) -> None:
        self._items: dict[str, PortfolioEntry] = {}

    def register(self, entry: PortfolioEntry) -> PortfolioEntry:
        self._items[entry.portfolio_id] = entry
        return entry

    def get(self, portfolio_id: str) -> PortfolioEntry | None:
        return self._items.get(portfolio_id)

    def enabled(self) -> tuple[PortfolioEntry, ...]:
        return tuple(
            item
            for item in sorted(self._items.values(), key=lambda x: x.portfolio_id)
            if item.enabled
        )
