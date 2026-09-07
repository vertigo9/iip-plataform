"""Regression tests for KnowledgeEventAdapter compatibility."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from iip.knowledge.event_adapter import KnowledgeEventAdapter
from iip.knowledge.models import DecisionChange, Verdict


class FakeBridge:
    def __init__(self):
        self.decisions = []
        self.snapshots = []
        self.evidence = []

    def persist_decision(self, value):
        self.decisions.append(value)

    def persist_snapshot(self, value):
        self.snapshots.append(value)

    def persist_evidence(self, value):
        self.evidence.append(value)


def make_event(payload):
    return SimpleNamespace(
        payload=payload,
        timestamp=datetime(2026, 1, 15, 10, 30, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_on_decision_persists_decision():
    bridge = FakeBridge()
    adapter = KnowledgeEventAdapter(bridge)
    verdict = next(iter(Verdict))
    change = next(iter(DecisionChange))
    event = make_event(
        {
            "decision_id": "D-001",
            "ticker": "PETR4",
            "new_verdict": verdict.value,
            "change_type": change.value,
            "confidence": 0.85,
            "reasons": ["resultado positivo"],
            "risks": ["mercado"],
            "evidence_ids": ["E-001"],
            "review_triggers": ["resultado trimestral"],
        }
    )
    result = await adapter.on_decision(event)
    assert result is bridge.decisions[0]
    assert result.decision_id == "D-001"


@pytest.mark.asyncio
async def test_on_snapshot_persists_snapshot():
    bridge = FakeBridge()
    adapter = KnowledgeEventAdapter(bridge)
    event = make_event(
        {
            "snapshot_id": "S-001",
            "portfolio_value": 100000.50,
        }
    )
    result = await adapter.on_snapshot(event)
    assert result is bridge.snapshots[0]
    assert result.snapshot_id == "S-001"


@pytest.mark.asyncio
async def test_on_document_persists_evidence():
    bridge = FakeBridge()
    adapter = KnowledgeEventAdapter(bridge)
    event = make_event(
        {
            "evidence_id": "E-001",
            "ticker": "VALE3",
            "source_type": "atlas",
            "source_url": "https://example.com/doc",
            "title": "Documento de teste",
            "document_hash": "abc123",
            "relevant_facts": ["fato 1", "fato 2"],
        }
    )
    result = await adapter.on_document(event)
    assert result is bridge.evidence[0]
    assert result.evidence_id == "E-001"
