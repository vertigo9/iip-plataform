from __future__ import annotations

from datetime import date, datetime

from iip.events import Event, EventBus

from .bridge import KnowledgeBridge
from .models import (
    Decision,
    DecisionChange,
    Evidence,
    PortfolioSnapshot,
    Position,
    Verdict,
)


class KnowledgeEventAdapter:
    """Maps IIP event contracts into persistent knowledge projections."""

    def __init__(self, bridge: KnowledgeBridge):
        self.bridge = bridge

    def register(self) -> None:
        self.unregister()
        EventBus.subscribe("iip.decision.created.v1", self.on_decision)
        EventBus.subscribe("iip.portfolio.snapshot_created.v1", self.on_snapshot)
        EventBus.subscribe("atlas.document.processed.v1", self.on_document)

    def unregister(self) -> None:
        EventBus.unsubscribe("iip.decision.created.v1", self.on_decision)
        EventBus.unsubscribe("iip.portfolio.snapshot_created.v1", self.on_snapshot)
        EventBus.unsubscribe("atlas.document.processed.v1", self.on_document)

    async def on_decision(self, event: Event):
        p = event.payload
        d = Decision(
            decision_id=str(p["decision_id"]),
            ticker=str(p["ticker"]),
            date=date.fromisoformat(
                str(p.get("date", event.timestamp.date().isoformat()))
            ),
            previous_verdict=Verdict(p["previous_verdict"])
            if p.get("previous_verdict")
            else None,
            new_verdict=Verdict(p["new_verdict"]),
            change_type=DecisionChange(p.get("change_type", "NO_CHANGE")),
            confidence=float(p.get("confidence", 0.0)),
            reasons=tuple(p.get("reasons", ())),
            risks=tuple(p.get("risks", ())),
            evidence_ids=tuple(p.get("evidence_ids", ())),
            review_triggers=tuple(p.get("review_triggers", ())),
        )
        self.bridge.persist_decision(d)
        return self.bridge.sync_decision_projection(d)

    async def on_snapshot(self, event: Event):
        p = event.payload
        positions = tuple(Position(**item) for item in p.get("positions", ()))
        s = PortfolioSnapshot(
            snapshot_id=str(p["snapshot_id"]),
            created_at=datetime.fromisoformat(
                str(p.get("created_at", event.timestamp.isoformat()))
            ),
            portfolio_value=float(p["portfolio_value"]),
            positions=positions,
        )
        self.bridge.persist_snapshot(s)
        return self.bridge.sync_snapshot_projection(s)

    async def on_document(self, event: Event):
        p = event.payload
        e = Evidence(
            evidence_id=str(p["evidence_id"]),
            ticker=str(p["ticker"]),
            date=date.fromisoformat(
                str(p.get("date", event.timestamp.date().isoformat()))
            ),
            source_type=str(p.get("source_type", "atlas")),
            source_url=p.get("source_url"),
            title=p.get("title"),
            document_hash=p.get("document_hash"),
            relevant_facts=tuple(p.get("relevant_facts", ())),
        )
        self.bridge.persist_evidence(e)
        return self.bridge.sync_evidence_projection(e)
