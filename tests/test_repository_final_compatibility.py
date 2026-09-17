from datetime import UTC, date, datetime
from pathlib import Path

from iip.decision.thesis_exit_gate import GateStatus, assess_thesis_exit
from iip.knowledge.models import Decision, Evidence, PortfolioSnapshot, Position, Verdict
from iip.knowledge.repository import AssetDirectory, ObsidianRepository


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


def test_asset_location_has_legacy_wrapper_and_canonical_path(tmp_path: Path):
    repo = ObsidianRepository(tmp_path / "vault")

    location = repo.ensure_asset_directory("pcip11", "FII")

    assert isinstance(location, AssetDirectory)
    assert location.path.is_dir()
    assert location.path == tmp_path / "vault" / "FII" / "PCIP11"
    assert location == repo.asset_location("PCIP11", "fii")


def test_snapshot_uses_legacy_portfolio_path_and_serializes_positions(tmp_path: Path):
    repo = ObsidianRepository(tmp_path / "vault")

    path = repo.save_snapshot(make_snapshot())

    expected = (
        tmp_path / "vault" / "02_Portfolio" / "Snapshots" / "SNAP-20260827-001.md"
    )
    assert path == expected
    text = path.read_text("utf-8")
    assert "snapshot_id: SNAP-20260827-001" in text
    assert "ticker: PCIP11" in text


def test_snapshot_is_listed(tmp_path: Path):
    repo = ObsidianRepository(tmp_path / "vault")
    repo.save_snapshot(make_snapshot())

    assert len(repo.list_snapshots()) == 1


def test_windows_safe_evidence_name_keeps_semantic_id_in_body(tmp_path: Path):
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


def test_decision_persists_thesis_exit_fields(tmp_path: Path):
    thesis_exit = assess_thesis_exit(
        fundamentals=GateStatus.FAIL,
        balance_sheet=GateStatus.PASS,
        valuation=GateStatus.ATTENTION,
        dividends=GateStatus.ATTENTION,
        governance=GateStatus.PASS,
        opportunity_cost=GateStatus.UNKNOWN,
    )

    decision = Decision(
        decision_id="DEC-PCIP11-THESIS-001",
        ticker="PCIP11",
        date=date(2026, 9, 14),
        new_verdict=Verdict.ENCERRAR,
        confidence=0.90,
        thesis_exit_state=thesis_exit.state.value,
        thesis_exit_failed_gates=tuple(thesis_exit.failed_gates),
        thesis_exit_attention_gates=tuple(thesis_exit.attention_gates),
        thesis_exit_unknown_gates=tuple(thesis_exit.unknown_gates),
        thesis_exit_critical_failure=thesis_exit.critical_failure,
    )

    repo = ObsidianRepository(tmp_path / "vault")
    path = repo.save_decision(decision)

    text = path.read_text("utf-8")

    assert "thesis_exit_state: BREAK" in text
    assert "thesis_exit_failed_gates:" in text
    assert "- fundamentals" in text
    assert "thesis_exit_attention_gates:" in text
    assert "- valuation" in text
    assert "- dividends" in text
    assert "thesis_exit_unknown_gates:" in text
    assert "- opportunity_cost" in text
    assert "thesis_exit_critical_failure: True" in text


def test_decision_without_thesis_exit_keeps_legacy_persistence_shape(
    tmp_path: Path,
):
    decision = Decision(
        decision_id="DEC-PCIP11-LEGACY-001",
        ticker="PCIP11",
        date=date(2026, 9, 14),
        new_verdict=Verdict.MANTER,
        confidence=0.70,
    )

    repo = ObsidianRepository(tmp_path / "vault")
    path = repo.save_decision(decision)

    text = path.read_text("utf-8")

    assert "type: decision" in text
    assert "decision_id: DEC-PCIP11-LEGACY-001" in text
    assert "ticker: PCIP11" in text
    assert "new_verdict: MANTER" in text
    assert "confidence: 0.7" in text

    assert "thesis_exit_state:" not in text
    assert "thesis_exit_failed_gates:" not in text
    assert "thesis_exit_attention_gates:" not in text
    assert "thesis_exit_unknown_gates:" not in text
    assert "thesis_exit_critical_failure:" not in text
