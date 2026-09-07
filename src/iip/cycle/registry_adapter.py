"""Safe adapter from existing Portfolio Registry records."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegistryAsset:
    ticker: str
    asset_class: str
    manager: str | None = None
    segment: str | None = None
    structure: str | None = None


def normalize_registry_asset(asset) -> RegistryAsset:
    return RegistryAsset(
        ticker=str(asset.ticker).upper(),
        asset_class=str(asset.asset_class),
        manager=getattr(asset, "manager", None),
        segment=getattr(asset, "segment", None),
        structure=getattr(asset, "structure", None),
    )
