from __future__ import annotations

from pathlib import Path

from .models import Decision, Evidence, Exposure, PortfolioSnapshot


class ObsidianRepository:
    """Filesystem-backed Obsidian repository. Historical records are append-only."""

    def __init__(self, vault: str | Path):
        self.vault = Path(vault).expanduser().resolve()
        self.vault.mkdir(parents=True, exist_ok=True)
        for folder in (
            "00_System",
            "01_Assets",
            "02_Portfolio/Snapshots",
            "03_Decisions",
            "04_Evidence",
            "05_Events",
            "06_Exposures",
            "07_Research",
            "08_Dashboards",
        ):
            (self.vault / folder).mkdir(parents=True, exist_ok=True)

    def _write_once(self, path: Path, content: str) -> Path:
        if path.exists():
            raise FileExistsError(f"append-only record already exists: {path.name}")
        path.write_text(content, encoding="utf-8")
        return path

    def save_decision(self, d: Decision) -> Path:
        path = self.vault / "03_Decisions" / f"{d.decision_id}.md"
        content = (
            f"""---\ntype: decision\ndecision_id: {d.decision_id}\nticker: {d.ticker}\ndate: {d.date.isoformat()}\nprevious_verdict: {d.previous_verdict.value if d.previous_verdict else ""}\nnew_verdict: {d.new_verdict.value}\nchange_type: {d.change_type.value}\nconfidence: {d.confidence:.4f}\n---\n\n# Decisão — {d.ticker}\n\n## Veredito anterior\n{d.previous_verdict.value if d.previous_verdict else "N/A"}\n\n## Novo veredito\n{d.new_verdict.value}\n\n## Motivos\n"""
            + "".join(f"- {x}\n" for x in d.reasons)
        )
        content += "\n## Riscos\n" + "".join(f"- {x}\n" for x in d.risks)
        content += "\n## Evidências\n" + "".join(f"- [[{x}]]\n" for x in d.evidence_ids)
        content += "\n## Gatilhos de revisão\n" + "".join(
            f"- {x}\n" for x in d.review_triggers
        )
        return self._write_once(path, content)

    def save_evidence(self, e: Evidence) -> Path:
        path = self.vault / "04_Evidence" / f"{e.evidence_id}.md"
        content = f"""---\ntype: evidence\nevidence_id: {e.evidence_id}\nticker: {e.ticker}\ndate: {e.date.isoformat()}\nsource_type: {e.source_type}\nsource_url: {e.source_url or ""}\ndocument_hash: {e.document_hash or ""}\n---\n\n# Evidência — {e.ticker}\n\n**Fonte:** {e.source_type}\n\n## Fatos relevantes\n"""
        content += "".join(f"- {x}\n" for x in e.relevant_facts)
        return self._write_once(path, content)

    def save_exposure(self, e: Exposure) -> Path:
        path = self.vault / "06_Exposures" / f"{e.ticker}__{e.factor}.md"
        content = f"---\ntype: exposure\nticker: {e.ticker}\nfactor: {e.factor}\nweight: {e.weight:.6f}\nconfidence: {e.confidence:.6f}\n---\n"
        return self._write_once(path, content)

    def save_snapshot(self, s: PortfolioSnapshot) -> Path:
        path = self.vault / "02_Portfolio" / "Snapshots" / f"{s.snapshot_id}.md"
        content = f"---\ntype: portfolio_snapshot\nsnapshot_id: {s.snapshot_id}\ncreated_at: {s.created_at.isoformat()}\nportfolio_value: {s.portfolio_value:.2f}\n---\n\n# Portfolio Snapshot\n\n| Ativo | Classe | Valor | Peso | Alvo |\n|---|---|---:|---:|---:|\n"
        for p in s.positions:
            target = "" if p.target_weight is None else f"{p.target_weight:.6f}"
            content += f"| {p.ticker} | {p.asset_class} | {p.market_value:.2f} | {p.weight:.6f} | {target} |\n"
        return self._write_once(path, content)

    def read_markdown(self, folder: str, stem: str) -> str:
        path = self.vault / folder / f"{stem}.md"
        return path.read_text(encoding="utf-8")

    def list_decisions(self, ticker: str) -> list[Path]:
        prefix = f"DEC-{ticker}-"
        return sorted(
            (p for p in (self.vault / "03_Decisions").glob(f"{prefix}*.md")),
            key=lambda p: p.name,
        )
