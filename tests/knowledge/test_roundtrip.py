from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from iip.knowledge import *


def test_pcip11_roundtrip_and_history(tmp_path: Path):
    bridge = KnowledgeBridge(str(tmp_path / "vault"))
    ev = Evidence(
        evidence_id="EV-PCIP11-TEST-001",
        ticker="PCIP11",
        date=date(2026, 8, 27),
        source_type="test_fixture",
        relevant_facts=("fixture only; no financial claim",),
    )
    bridge.persist_evidence(ev)
    first = Decision(
        decision_id="DEC-PCIP11-20260827-001",
        ticker="PCIP11",
        date=date(2026, 8, 27),
        new_verdict=Verdict.AGUARDAR,
        change_type=DecisionChange.NO_CHANGE,
        confidence=0.80,
        evidence_ids=(ev.evidence_id,),
    )
    second = Decision(
        decision_id="DEC-PCIP11-20260827-002",
        ticker="PCIP11",
        date=date(2026, 8, 27),
        previous_verdict=Verdict.AGUARDAR,
        new_verdict=Verdict.AUMENTAR,
        change_type=DecisionChange.UPGRADE,
        confidence=0.85,
        evidence_ids=(ev.evidence_id,),
    )
    bridge.persist_decision(first)
    bridge.persist_decision(second)
    ctx = bridge.assemble("PCIP11")
    assert len(ctx.decision_history) == 2
    assert "AGUARDAR" in ctx.decision_history[0]
    assert "AUMENTAR" in ctx.decision_history[1]


def test_append_only_and_audit(tmp_path: Path):
    bridge = KnowledgeBridge(str(tmp_path / "vault"))
    with pytest.raises(ValueError):
        bridge.persist_decision(
            Decision(
                decision_id="DEC-PCIP11-INVALID",
                ticker="PCIP11",
                date=date(2026, 8, 27),
                new_verdict=Verdict.AUMENTAR,
                evidence_ids=("MISSING",),
                confidence=0.9,
            )
        )
    e = Evidence("EV-1", "PCIP11", date(2026, 8, 27), "test_fixture")
    bridge.persist_evidence(e)
    d = Decision(
        "DEC-PCIP11-UNIQUE",
        "PCIP11",
        date(2026, 8, 27),
        Verdict.MANTER,
        evidence_ids=("EV-1",),
        confidence=0.7,
    )
    bridge.persist_decision(d)
    with pytest.raises(FileExistsError):
        bridge.persist_decision(d)


def test_snapshot_and_redundancy(tmp_path: Path):
    bridge = KnowledgeBridge(str(tmp_path / "vault"))
    snap = PortfolioSnapshot(
        snapshot_id="SNAP-20260827-001",
        created_at=datetime(2026, 8, 27, tzinfo=UTC),
        portfolio_value=100000,
        positions=(
            Position("PCIP11", "FII", 5000, 0.05),
            Position("VGIP11", "FII", 3000, 0.03),
        ),
    )
    bridge.persist_snapshot(snap)
    result = bridge.redundancy(
        [
            Exposure("PCIP11", "credito_imobiliario", 0.12),
            Exposure("VGIP11", "credito_imobiliario", 0.11),
        ],
        threshold=0.20,
    )
    assert result == [
        {
            "factor": "credito_imobiliario",
            "aggregate_weight": 0.23,
            "assets": ["PCIP11", "VGIP11"],
        }
    ]
    assert (tmp_path / "vault/02_Portfolio/Snapshots/SNAP-20260827-001.md").exists()
