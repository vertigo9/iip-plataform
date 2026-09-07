from __future__ import annotations

from dataclasses import dataclass

from .repository import ObsidianRepository


@dataclass(frozen=True)
class KnowledgeContext:
    ticker: str
    decision_history: tuple[str, ...]
    evidence: tuple[str, ...]
    portfolio_snapshots: tuple[str, ...]
    exposures: tuple[str, ...]


class ContextAssembler:
    def __init__(self, repository: ObsidianRepository):
        self.repo = repository

    def assemble(self, ticker: str) -> KnowledgeContext:
        decisions = tuple(
            p.read_text(encoding="utf-8") for p in self.repo.list_decisions(ticker)
        )
        evidence = tuple(
            p.read_text(encoding="utf-8")
            for p in sorted((self.repo.vault / "04_Evidence").glob(f"*{ticker}*.md"))
        )
        snapshots = tuple(
            p.read_text(encoding="utf-8")
            for p in sorted((self.repo.vault / "02_Portfolio/Snapshots").glob("*.md"))
        )
        exposures = tuple(
            p.read_text(encoding="utf-8")
            for p in sorted((self.repo.vault / "06_Exposures").glob(f"{ticker}__*.md"))
        )
        return KnowledgeContext(ticker, decisions, evidence, snapshots, exposures)
