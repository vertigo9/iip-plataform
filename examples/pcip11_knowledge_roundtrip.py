from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path
import os

from iip.events import Event, EventBus
from iip.knowledge import KnowledgeBridge
from iip.knowledge.event_adapter import KnowledgeEventAdapter


async def main() -> None:
    vault = Path(os.environ.get("IIP_OBSIDIAN_VAULT", "./vault"))
    bridge = KnowledgeBridge(vault)
    adapter = KnowledgeEventAdapter(bridge)
    adapter.register()

    # Synthetic regression fixture: it validates the transport/round-trip only.
    await EventBus.publish(Event(
        type="atlas.document.processed.v1",
        source="pcip11-regression",
        payload={
            "evidence_id": "EV-PCIP11-ROUNDTRIP-TEST",
            "ticker": "PCIP11",
            "date": date.today().isoformat(),
            "source_type": "synthetic_regression_fixture",
            "title": "PCIP11 round-trip integration test",
            "relevant_facts": ["Transport test only; not financial evidence."],
        },
    ))

    ctx = bridge.assemble("PCIP11")
    print({
        "vault": str(vault.resolve()),
        "ticker": ctx.ticker,
        "evidence_records": len(ctx.evidence),
        "decision_records": len(ctx.decision_history),
        "snapshot_records": len(ctx.portfolio_snapshots),
        "exposure_records": len(ctx.exposures),
        "status": "PASS" if len(ctx.evidence) >= 1 else "FAIL",
    })


if __name__ == "__main__":
    asyncio.run(main())
