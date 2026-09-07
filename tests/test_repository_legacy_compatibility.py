from datetime import UTC, date, datetime
from pathlib import Path

from iip.knowledge.models import (
    Decision,
    DecisionChange,
    Evidence,
    PortfolioSnapshot,
    Position,
    Verdict,
)
from iip.knowledge.repository import AssetDirectory, ObsidianRepository


def make_decision(number):
    return Decision(
        decision_id=f"DEC-PCIP11-20260827-{number:03d}",
        ticker="PCIP11",
        date=date(2026, 8, 27),
        new_verdict=Verdict.AGUARDAR if number == 1 else Verdict.AUMENTAR,
        change_type=DecisionChange.NO_CHANGE if number == 1 else DecisionChange.UPGRADE,
        confidence=0.8,
        evidence_ids=("EV-PCIP11-TEST-001",),
    )


def make_snapshot():
    return PortfolioSnapshot(
        snapshot_id="SNAP-20260827-001",
        created_at=datetime(2026, 8, 27, tzinfo=UTC),
        portfolio_value=100000,
        positions=(
            Position("PCIP11", "FII", 5000, 0.05),
            Position("VGIP11", "FII", 3000, 0.03),
        ),
    )


def test_legacy_vault_contract(tmp_path: Path):
    repo = ObsidianRepository(tmp_path / "vault")
    assert repo.vault == tmp_path / "vault"


def test_legacy_asset_directory_contract(tmp_path: Path):
    repo = ObsidianRepository(tmp_path / "vault")
    location = repo.ensure_asset_directory("pcip11", "FII")
    assert isinstance(location, AssetDirectory)
    assert location.path.is_dir()


def test_decisions_can_be_listed(tmp_path: Path):
    repo = ObsidianRepository(tmp_path / "vault")
    repo.save_decision(make_decision(1))
    repo.save_decision(make_decision(2))
    paths = repo.list_decisions("PCIP11")
    assert len(paths) == 2
    assert paths[0].name.endswith("001.md")
    assert paths[1].name.endswith("002.md")


def test_snapshot_keeps_legacy_path(tmp_path: Path):
    repo = ObsidianRepository(tmp_path / "vault")
    path = repo.save_snapshot(make_snapshot())
    assert (
        path
        == tmp_path / "vault" / "02_Portfolio" / "Snapshots" / "SNAP-20260827-001.md"
    )
    assert path.exists()


def test_snapshot_can_be_listed(tmp_path: Path):
    repo = ObsidianRepository(tmp_path / "vault")
    repo.save_snapshot(make_snapshot())
    assert len(repo.list_snapshots()) == 1


def test_evidence_filename_is_safe_but_semantic_id_is_preserved(tmp_path: Path):
    repo = ObsidianRepository(tmp_path / "vault")
    ev = Evidence(
        evidence_id="xp_asset:XPML11:2026:abcdef",
        ticker="XPML11",
        date=date(2026, 12, 31),
        source_type="atlas",
        source_url="https://example.com",
        relevant_facts=("document_id=xp_asset:XPML11:2026:abcdef",),
    )
    path = repo.save_evidence(ev)
    assert ":" not in path.name
    assert "evidence_id: xp_asset:XPML11:2026:abcdef" in path.read_text("utf-8")
