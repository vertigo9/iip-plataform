"""Translate events into Knowledge models and optionally project them to Obsidian."""

from __future__ import annotations

from datetime import date, datetime

from .models import (
    Decision,
    DecisionChange,
    Evidence,
    PortfolioSnapshot,
    Position,
    Verdict,
)


class KnowledgeEventAdapter:
    """Adapt event payloads to Knowledge models and bridge projections.

    Persistence is the required bridge contract. Projection is optional so
    legacy bridge implementations/test doubles remain compatible while the
    real KnowledgeBridge can return the Obsidian synchronization result.
    """

    def register(self) -> None:
        """Register this adapter on the IIP EventBus."""
        from iip.events import EventBus

        EventBus.subscribe("iip.decision.created.v1", self.on_decision)
        EventBus.subscribe("iip.portfolio.snapshot_created.v1", self.on_snapshot)
        EventBus.subscribe("atlas.document.processed.v1", self.on_document)

    def unregister(self) -> None:
        """Remove this adapter from the IIP EventBus."""
        from iip.events import EventBus

        EventBus.unsubscribe("iip.decision.created.v1", self.on_decision)
        EventBus.unsubscribe("iip.portfolio.snapshot_created.v1", self.on_snapshot)
        EventBus.unsubscribe("atlas.document.processed.v1", self.on_document)

    def __init__(self, bridge) -> None:
        self.bridge = bridge

    @staticmethod
    def _optional_sync(bridge, method_name: str, model, persisted):
        method = getattr(bridge, method_name, None)
        if method is None:
            # Some legacy bridges persist by side effect and return None.
            # In that case the model itself is the adapter result.
            return model if persisted is None else persisted
        return method(model)

    async def on_decision(self, event):
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
        persisted = self.bridge.persist_decision(d)
        return self._optional_sync(
            self.bridge, "sync_decision_projection", d, persisted
        )

    async def on_snapshot(self, event):
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
        persisted = self.bridge.persist_snapshot(s)
        return self._optional_sync(
            self.bridge, "sync_snapshot_projection", s, persisted
        )

    async def on_document(self, event):
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
        persisted = self.bridge.persist_evidence(e)
        return self._optional_sync(
            self.bridge, "sync_evidence_projection", e, persisted
        )
