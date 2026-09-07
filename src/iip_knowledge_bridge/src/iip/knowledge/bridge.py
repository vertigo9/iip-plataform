from __future__ import annotations

from .audit import DecisionAuditor
from .context import ContextAssembler, KnowledgeContext
from .models import Decision, Evidence, Exposure, PortfolioSnapshot
from .redundancy import find_redundant_exposures
from .repository import ObsidianRepository


class KnowledgeBridge:
    """Application service connecting IIP domain events/use-cases to the Obsidian projection."""

    def __init__(self, vault: str):
        self.repository = ObsidianRepository(vault)
        self.context = ContextAssembler(self.repository)
        self.auditor = DecisionAuditor(self.repository)

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

    def assemble(self, ticker: str) -> KnowledgeContext:
        return self.context.assemble(ticker)

    @staticmethod
    def redundancy(exposures: list[Exposure], threshold: float = 0.20):
        return find_redundant_exposures(exposures, threshold)
