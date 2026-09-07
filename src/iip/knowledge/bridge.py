from __future__ import annotations

from .audit import DecisionAuditor
from .context import ContextAssembler, KnowledgeContext
from .models import Decision, Evidence, Exposure, PortfolioSnapshot
from .projection import AssetNoteProjector
from .redundancy import find_redundant_exposures
from .repository import ObsidianRepository
from .sync import ProjectionSyncEngine, ProjectionSyncResult


class KnowledgeBridge:
    """Application service connecting IIP domain events/use-cases to the Obsidian projection."""

    def __init__(self, vault: str):
        self.repository = ObsidianRepository(vault)
        self.context = ContextAssembler(self.repository)
        self.auditor = DecisionAuditor(self.repository)
        self.projector = AssetNoteProjector(self.repository.vault)
        self.sync_engine = ProjectionSyncEngine(self.projector)

    def persist_evidence(self, evidence: Evidence):
        return self.repository.save_evidence(evidence)

    def persist_decision(self, decision: Decision):
        issues = self.auditor.audit(decision)
        if issues:
            raise ValueError(
                "Decision audit failed: " + "; ".join(i.message for i in issues)
            )
        return self.repository.save_decision(decision)

    def persist_snapshot(self, snapshot: PortfolioSnapshot):
        return self.repository.save_snapshot(snapshot)

    def persist_exposure(self, exposure: Exposure):
        return self.repository.save_exposure(exposure)

    def sync_asset_section(
        self,
        ticker: str,
        asset_class: str,
        role: str,
        section: str,
        content: str,
    ) -> ProjectionSyncResult:
        """Synchronize an IIP-owned section in the canonical asset note."""
        return self.sync_engine.sync_asset_section(
            ticker, asset_class, role, section, content
        )

    def sync_decision_projection(self, decision: Decision) -> ProjectionSyncResult:
        """Project the latest decision state into the asset index."""
        content = (
            f"Status: {decision.new_verdict.value}\n"
            f"Data: {decision.date.isoformat()}\n"
            f"Confiança: {decision.confidence:.2f}"
        )
        return self.sync_asset_section(
            decision.ticker, "FII", "index", "IIP:decision", content
        )

    def sync_evidence_projection(self, evidence: Evidence) -> ProjectionSyncResult:
        """Project evidence facts into the canonical sources note."""
        facts = "\n".join(f"- {fact}" for fact in evidence.relevant_facts)
        content = (
            f"Data: {evidence.date.isoformat()}\n"
            f"Tipo: {evidence.source_type}\n"
            f"Título: {evidence.title or ''}\n"
            f"Fonte: {evidence.source_url or ''}\n"
            f"{facts}"
        ).rstrip()
        return self.sync_asset_section(
            evidence.ticker, "FII", "sources", "IIP:evidence", content
        )

    def sync_snapshot_projection(
        self, snapshot: PortfolioSnapshot
    ) -> ProjectionSyncResult:
        """Project the positions of a portfolio snapshot into asset notes."""
        results = []
        for position in snapshot.positions:
            content = (
                f"Snapshot: {snapshot.snapshot_id}\n"
                f"Valor: {position.market_value:.2f}\n"
                f"Peso: {position.weight:.6f}"
            )
            results.append(
                self.sync_asset_section(
                    position.ticker,
                    position.asset_class,
                    "portfolio",
                    "IIP:snapshot",
                    content,
                )
            )
        if not results:
            raise ValueError("snapshot must contain at least one position")
        return results[-1]

    def assemble(self, ticker: str) -> KnowledgeContext:
        return self.context.assemble(ticker)

    @staticmethod
    def redundancy(exposures: list[Exposure], threshold: float = 0.20):
        return find_redundant_exposures(exposures, threshold)
