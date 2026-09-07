from pathlib import Path

from .models import Decision, Evidence, Exposure, PortfolioSnapshot


def _yaml(data: dict) -> str:
    lines = ["---"]
    for k, v in data.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            lines.extend([f"  - {x}" for x in v])
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


class ObsidianRepository:
    """Filesystem repository for an Obsidian vault; decisions/snapshots are append-only."""

    def __init__(self, vault: str | Path):
        self.vault = Path(vault)
        self.vault.mkdir(parents=True, exist_ok=True)

    def save_decision(self, decision: Decision) -> Path:
        folder = self.vault / "03_Decisions"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{decision.decision_id}.md"
        content = _yaml(
            {
                "type": "decision",
                "decision_id": decision.decision_id,
                "ticker": decision.ticker,
                "date": decision.date.isoformat(),
                "previous_verdict": str(decision.previous_verdict)
                if decision.previous_verdict
                else "",
                "new_verdict": str(decision.new_verdict),
                "change_type": str(decision.change_type),
                "confidence": decision.confidence,
            }
        )
        content += f"\n# Decisão — {decision.ticker}\n\n## Veredito anterior\n{str(decision.previous_verdict) if decision.previous_verdict else 'N/A'}\n\n## Novo veredito\n{decision.new_verdict!s}\n\n## Motivos\n"
        content += "".join(f"- {x}\n" for x in decision.reasons)
        content += "\n## Riscos\n" + "".join(f"- {x}\n" for x in decision.risks)
        content += "\n## Evidências\n" + "".join(
            f"- [[{x}]]\n" for x in decision.evidence_ids
        )
        content += "\n## Gatilhos de revisão\n" + "".join(
            f"- {x}\n" for x in decision.review_triggers
        )
        path.write_text(content, encoding="utf-8")
        return path

    def save_evidence(self, evidence: Evidence) -> Path:
        folder = self.vault / "04_Evidence"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{evidence.evidence_id}.md"
        content = (
            _yaml(evidence.model_dump(mode="json"))
            + f"\n# Evidência — {evidence.ticker}\n\n**Fonte:** {evidence.source_type}\n"
        )
        if evidence.source_url:
            content += f"\n**URL:** {evidence.source_url}\n"
        content += "\n## Fatos relevantes\n" + "".join(
            f"- {x}\n" for x in evidence.relevant_facts
        )
        path.write_text(content, encoding="utf-8")
        return path

    def save_exposure(self, exposure: Exposure) -> Path:
        folder = self.vault / "06_Exposures"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{exposure.ticker}__{exposure.factor}.md"
        path.write_text(
            _yaml(exposure.model_dump(mode="json"))
            + f"\n# {exposure.ticker} → {exposure.factor}\n",
            encoding="utf-8",
        )
        return path

    def save_snapshot(self, snapshot: PortfolioSnapshot) -> Path:
        folder = self.vault / "02_Portfolio" / "Snapshots"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{snapshot.snapshot_id}.md"
        content = _yaml(
            {
                "type": "portfolio_snapshot",
                "snapshot_id": snapshot.snapshot_id,
                "created_at": snapshot.created_at.isoformat(),
                "portfolio_value": snapshot.portfolio_value,
            }
        )
        content += "\n# Portfolio Snapshot\n\n| Ativo | Classe | Valor | Peso | Alvo |\n|---|---|---:|---:|---:|\n"
        for p in snapshot.positions:
            content += f"| {p.ticker} | {p.asset_class} | {p.market_value:.2f} | {p.weight:.4f} | {p.target_weight if p.target_weight is not None else ''} |\n"
        path.write_text(content, encoding="utf-8")
        return path
