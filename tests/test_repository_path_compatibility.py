from pathlib import Path

from iip.knowledge.repository import AssetDirectory, ObsidianRepository


def test_asset_directory_behaves_like_legacy_path(tmp_path: Path):
    repo = ObsidianRepository(tmp_path / "vault")

    location = repo.ensure_asset_directory("pcip11", "FII")

    assert isinstance(location, AssetDirectory)
    assert location == tmp_path / "vault" / "FII" / "PCIP11"
    assert location.exists()
    assert location.is_dir()
