"""Canonical mapping between IIP assets and the Obsidian vault."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_ASSET_CLASS_FOLDERS: dict[str, str] = {
    "equity": "Equities",
    "equities": "Equities",
    "ação": "Equities",
    "acoes": "Equities",
    "ações": "Equities",
    "fii": "FIIs",
    "fiis": "FIIs",
    "fi-infra": "FIInfra",
    "fiinfra": "FIInfra",
    "fi infra": "FIInfra",
    "fi-agro": "FIAgro",
    "fiagro": "FIAgro",
    "fi agro": "FIAgro",
}


def normalize_ticker(ticker: str) -> str:
    """Return the canonical ticker used by the vault."""
    normalized = str(ticker).strip().upper()
    if not normalized:
        raise ValueError("ticker must not be empty")
    if "/" in normalized or "\\" in normalized or ".." in normalized:
        raise ValueError("ticker contains unsafe path characters")
    return normalized


def normalize_asset_class(asset_class: str) -> str:
    """Return a normalized asset-class key for vault mapping."""
    normalized = str(asset_class).strip().lower()
    if not normalized:
        raise ValueError("asset_class must not be empty")
    return normalized


@dataclass(frozen=True)
class AssetVaultLocation:
    """Canonical location of an asset inside the IIP Obsidian vault."""

    ticker: str
    asset_class: str
    category_folder: str
    path: Path


class AssetVaultLocator:
    """Resolve deterministic asset folders without creating files."""

    def __init__(self, vault: str | Path):
        self.vault = Path(vault).expanduser().resolve()

    @staticmethod
    def category_folder(asset_class: str) -> str:
        key = normalize_asset_class(asset_class)
        try:
            return _ASSET_CLASS_FOLDERS[key]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported asset_class for Obsidian vault: {asset_class}"
            ) from exc

    def locate(self, ticker: str, asset_class: str) -> AssetVaultLocation:
        canonical_ticker = normalize_ticker(ticker)
        category = self.category_folder(asset_class)
        path = self.vault / "01_Assets" / category / canonical_ticker
        return AssetVaultLocation(
            ticker=canonical_ticker,
            asset_class=normalize_asset_class(asset_class),
            category_folder=category,
            path=path,
        )

    def ensure(self, ticker: str, asset_class: str) -> AssetVaultLocation:
        """Create the canonical asset directory and return its location."""
        location = self.locate(ticker, asset_class)
        location.path.mkdir(parents=True, exist_ok=True)
        return location
