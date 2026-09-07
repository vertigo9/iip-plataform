from pathlib import Path

import pytest

from iip.knowledge import (
    AssetVaultLocator,
    ObsidianRepository,
    normalize_asset_class,
    normalize_ticker,
)


def test_locator_maps_fii_to_canonical_asset_folder(tmp_path: Path):
    location = AssetVaultLocator(tmp_path / "vault").locate("pcip11", "FII")

    assert location.ticker == "PCIP11"
    assert location.category_folder == "FIIs"
    assert (
        location.path
        == (tmp_path / "vault" / "01_Assets" / "FIIs" / "PCIP11").resolve()
    )


def test_locator_maps_supported_asset_classes(tmp_path: Path):
    locator = AssetVaultLocator(tmp_path / "vault")

    assert locator.locate("ITUB4", "equity").category_folder == "Equities"
    assert locator.locate("CDII11", "FI-Infra").category_folder == "FIInfra"
    assert locator.locate("CRAA11", "FI-Agro").category_folder == "FIAgro"


def test_locator_normalizes_ticker_and_class():
    assert normalize_ticker("  Xp_Asset ") == "XP_ASSET"
    assert normalize_asset_class(" FI-Infra ") == "fi-infra"


def test_locator_rejects_unsafe_or_unknown_values(tmp_path: Path):
    locator = AssetVaultLocator(tmp_path / "vault")

    with pytest.raises(ValueError):
        locator.locate("../PCIP11", "FII")

    with pytest.raises(ValueError):
        locator.locate("PCIP11", "unknown")


def test_repository_exposes_canonical_asset_location(tmp_path: Path):
    repo = ObsidianRepository(tmp_path / "vault")

    location = repo.ensure_asset_directory("pcip11", "FII")

    assert location.path.is_dir()
    assert location.path == repo.asset_location("PCIP11", "fii").path
