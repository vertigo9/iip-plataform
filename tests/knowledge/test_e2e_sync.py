from datetime import date
from pathlib import Path

from iip.knowledge import (
    Decision,
    DecisionChange,
    Evidence,
    KnowledgeBridge,
    Verdict,
)


def test_decision_event_projection_creates_canonical_asset_note(tmp_path: Path):
    bridge = KnowledgeBridge(tmp_path / "vault")
    decision = Decision(
        decision_id="DEC-PCIP11-E2E-001",
        ticker="PCIP11",
        date=date(2026, 8, 28),
        new_verdict=Verdict.MANTER,
        change_type=DecisionChange.NO_CHANGE,
        confidence=0.8,
    )
    result = bridge.sync_decision_projection(decision)
    assert result.status.value == "CREATED"
    assert result.path.exists()
    assert "Status: MANTER" in result.path.read_text(encoding="utf-8")


def test_repeating_projection_is_unchanged(tmp_path: Path):
    bridge = KnowledgeBridge(tmp_path / "vault")
    decision = Decision(
        "DEC-PCIP11-E2E-002",
        "PCIP11",
        date(2026, 8, 28),
        Verdict.AGUARDAR,
        confidence=0.7,
    )
    first = bridge.sync_decision_projection(decision)
    second = bridge.sync_decision_projection(decision)
    assert first.status.value == "CREATED"
    assert second.status.value == "UNCHANGED"


def test_changed_projection_updates_only_iip_block(tmp_path: Path):
    bridge = KnowledgeBridge(tmp_path / "vault")
    first = Decision(
        "DEC-PCIP11-E2E-003",
        "PCIP11",
        date(2026, 8, 28),
        Verdict.MANTER,
        confidence=0.7,
    )
    second = Decision(
        "DEC-PCIP11-E2E-004",
        "PCIP11",
        date(2026, 8, 29),
        Verdict.AUMENTAR,
        confidence=0.9,
    )
    result = bridge.sync_decision_projection(first)
    result.path.write_text(
        result.path.read_text(encoding="utf-8") + "\nMinha anotação manual.\n",
        encoding="utf-8",
    )
    result2 = bridge.sync_decision_projection(second)
    text = result2.path.read_text(encoding="utf-8")
    assert result2.status.value == "UPDATED"
    assert "Status: AUMENTAR" in text
    assert "Status: MANTER" not in text
    assert "Minha anotação manual." in text


def test_evidence_event_projects_into_sources_note(tmp_path: Path):
    bridge = KnowledgeBridge(tmp_path / "vault")
    evidence = Evidence(
        "EV-PCIP11-E2E-001",
        "PCIP11",
        date(2026, 8, 28),
        "test_fixture",
        title="Fixture",
        relevant_facts=("Fato de teste",),
    )
    result = bridge.sync_evidence_projection(evidence)
    assert result.status.value == "CREATED"
    assert "Fato de teste" in result.path.read_text(encoding="utf-8")


def test_event_adapter_persists_and_projects_decision(tmp_path: Path):
    from iip.events import Event
    from iip.knowledge.event_adapter import KnowledgeEventAdapter

    bridge = KnowledgeBridge(tmp_path / "vault")
    adapter = KnowledgeEventAdapter(bridge)
    import asyncio

    result = asyncio.run(
        adapter.on_decision(
            Event(
                "iip.decision.created.v1",
                {
                    "decision_id": "DEC-PCIP11-E2E-005",
                    "ticker": "PCIP11",
                    "new_verdict": "MANTER",
                    "confidence": 0.8,
                },
            )
        )
    )
    assert result.status.value == "CREATED"


def test_empty_projection_is_skipped_without_creating_a_file(tmp_path: Path):
    bridge = KnowledgeBridge(tmp_path / "vault")
    result = bridge.sync_asset_section("PCIP11", "FII", "index", "IIP:empty", "")
    assert result.status.value == "SKIPPED"
    assert not result.path.exists()
