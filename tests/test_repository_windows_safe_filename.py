from datetime import date

from iip.knowledge.models import Evidence
from iip.knowledge.repository import ObsidianRepository


def make_evidence():
    return Evidence(
        evidence_id="xp_asset:XPML11:2026:abcdef1234567890",
        ticker="XPML11",
        date=date(2026, 12, 31),
        source_type="atlas",
        source_url="https://www.xpasset.com.br/fundos/xp-malls/",
        title="XPML11",
        document_hash="abcdef1234567890",
        relevant_facts=("provider=xp_asset",),
    )


def test_vault_alias_is_available(tmp_path):
    repo = ObsidianRepository(tmp_path / "vault")
    assert repo.vault == tmp_path / "vault"


def test_asset_directory_contract_is_preserved(tmp_path):
    repo = ObsidianRepository(tmp_path / "vault")
    path = repo.ensure_asset_directory("pcip11", "FII")
    assert path == tmp_path / "vault" / "FII" / "PCIP11"
    assert path.exists()


def test_evidence_filename_is_windows_safe(tmp_path):
    repo = ObsidianRepository(tmp_path / "vault")
    path = repo.save_evidence(make_evidence())
    assert path.name == "xp_asset_XPML11_2026_abcdef1234567890.md"
    assert ":" not in path.name


def test_semantic_id_survives_inside_markdown(tmp_path):
    repo = ObsidianRepository(tmp_path / "vault")
    path = repo.save_evidence(make_evidence())
    assert "evidence_id: xp_asset:XPML11:2026:abcdef1234567890" in path.read_text(
        "utf-8"
    )
