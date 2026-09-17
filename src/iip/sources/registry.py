"""IIP source registry.

Maps assets to their classification and prioritized information sources.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SourceRef:
    provider: str
    role: str
    priority: int
    url: str
    active: bool = True


@dataclass(frozen=True)
class AssetRef:
    ticker: str
    asset_class: str
    asset_subtype: str
    segment: str | None = None
    manager: str | None = None
    administrator: str | None = None
    cnpj: str | None = None
    sources: tuple[SourceRef, ...] = field(default_factory=tuple)


class SourceRegistry:
    """In-memory registry for asset/source metadata."""

    def __init__(self) -> None:
        self._assets: dict[str, AssetRef] = {}

    def register(self, asset: AssetRef) -> None:
        ticker = asset.ticker.upper().strip()
        if not ticker:
            raise ValueError("ticker must not be empty")

        if not asset.sources:
            raise ValueError(f"{ticker}: at least one source is required")

        self._assets[ticker] = AssetRef(
            ticker=ticker,
            asset_class=asset.asset_class,
            asset_subtype=asset.asset_subtype,
            segment=asset.segment,
            manager=asset.manager,
            administrator=asset.administrator,
            cnpj=asset.cnpj,
            sources=tuple(
                sorted(
                    asset.sources,
                    key=lambda source: source.priority,
                )
            ),
        )

    def get(self, ticker: str) -> AssetRef | None:
        return self._assets.get(ticker.upper().strip())

    def sources_for(self, ticker: str) -> tuple[SourceRef, ...]:
        asset = self.get(ticker)
        return asset.sources if asset else ()

    def clear(self) -> None:
        self._assets.clear()

    def register_many(self, assets: tuple[AssetRef, ...]) -> None:
        """Register multiple assets using the same normalization rules."""
        for asset in assets:
            self.register(asset)

    @classmethod
    def from_assets(cls, assets: tuple[AssetRef, ...]) -> SourceRegistry:
        """Build a registry from a canonical asset collection."""
        registry = cls()
        registry.register_many(assets)
        return registry
