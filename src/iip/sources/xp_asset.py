"""XP Asset institutional document discovery.

D-OBSIDIAN-06.2-02

This increment converts canonical XP Asset source metadata into deterministic
discovery targets. It does not perform HTTP requests.
"""

from __future__ import annotations

from dataclasses import dataclass

from .provider import DocumentProvider
from .registry import AssetRef, SourceRef


@dataclass(frozen=True)
class DocumentTarget:
    """A deterministic institutional discovery target."""

    ticker: str
    provider: str
    role: str
    url: str
    year: int | None = None


class XPAssetProvider(DocumentProvider):
    """Document provider for assets managed by XP Asset."""

    provider_name = "xp_asset"

    @staticmethod
    def _normalize(value: str | None) -> str:
        return (value or "").strip().casefold()

    def supports(self, asset: AssetRef) -> bool:
        """Return True when the asset is clearly associated with XP Asset."""
        if self._normalize(asset.manager) == "xp asset":
            return True

        return any(
            self._normalize(source.provider) == self.provider_name and source.active
            for source in asset.sources
        )

    def _institutional_sources(self, asset: AssetRef) -> tuple[SourceRef, ...]:
        """Return active XP Asset sources ordered by registry priority."""
        return tuple(
            sorted(
                (
                    source
                    for source in asset.sources
                    if source.active
                    and self._normalize(source.provider) == self.provider_name
                ),
                key=lambda source: source.priority,
            )
        )

    def discover(
        self,
        asset: AssetRef,
        years: range,
    ) -> tuple[DocumentTarget, ...]:
        """Build deterministic discovery targets for the requested years."""
        if not isinstance(years, range):
            raise TypeError("years must be a range")

        # If the asset is explicitly classified as XP Asset, it is supported
        # even when its source list is temporarily inactive/missing.
        # Conversely, an explicit inactive XP Asset source is an identifiable
        # routing case and deserves a precise diagnostic instead of the more
        # generic "unsupported asset" error.
        manager_is_xp = self._normalize(asset.manager) == "xp asset"
        has_xp_source = any(
            self._normalize(source.provider) == self.provider_name
            for source in asset.sources
        )

        if not self.supports(asset):
            if has_xp_source and not manager_is_xp:
                raise ValueError(
                    f"{asset.ticker}: no active XP Asset institutional source"
                )
            raise ValueError(
                f"{asset.ticker}: asset is not supported by {self.provider_name}"
            )

        sources = self._institutional_sources(asset)

        if not sources:
            raise ValueError(f"{asset.ticker}: no active XP Asset institutional source")

        requested_years = tuple(years)
        targets: list[DocumentTarget] = []

        for source in sources:
            if not requested_years:
                targets.append(
                    DocumentTarget(
                        ticker=asset.ticker,
                        provider=self.provider_name,
                        role=source.role,
                        url=source.url.strip(),
                        year=None,
                    )
                )
                continue

            targets.extend(
                DocumentTarget(
                    ticker=asset.ticker,
                    provider=self.provider_name,
                    role=source.role,
                    url=source.url.strip(),
                    year=year,
                )
                for year in requested_years
            )

        return tuple(targets)
