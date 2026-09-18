from __future__ import annotations

from pathlib import Path

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

    def sync_asset_frontmatter(
        self, ticker: str, asset_class: str, role: str, updates: dict[str, object]
    ) -> Path:
        """Merge queryable fields into the canonical asset note's YAML
        frontmatter -- what Dataview/DataviewJS actually reads (it has
        no access to the ``IIP:BEGIN/END`` prose sections)."""
        return self.projector.project_asset_frontmatter(
            ticker, asset_class, role, updates
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

    def sync_analysis_projection(
        self, report, ticker: str, asset_class: str
    ) -> ProjectionSyncResult:
        """Project an ``iip.analysis`` framework report (from
        ``EquityAnalyzer``/``FIIAnalyzer``/``ETFAnalyzer``/etc.) into the
        canonical asset note — the piece that closes the loop between
        ``iip analyze`` and the vault. Overwrites the previous
        ``IIP:analysis`` section idempotently on every run (same
        managed-section mechanism as decisions/evidence), so re-running
        ``analyze`` after fetching fresh data keeps just the latest
        result in this section, not an ever-growing log — history lives
        in ``ProjectionFingerprint``/git, not duplicated inline here.
        """
        pilares = "\n".join(
            f"- {p.pillar.value}: {p.score:.1f} (peso {p.weight:.0%})"
            for p in report.pillar_scores
        )
        content = (
            f"Score geral: {report.overall_score:.1f}/100\n"
            f"Recomendação: {report.recommendation}\n"
            f"Risco: {report.risk_level}\n"
            f"{pilares}"
        )
        result = self.sync_asset_section(
            ticker, asset_class, "scoring", "IIP:analysis", content
        )
        self.sync_asset_frontmatter(
            ticker,
            asset_class,
            "scoring",
            {
                "score": round(report.overall_score, 1),
                "recommendation": report.recommendation,
                "risk": report.risk_level,
            },
        )
        return result

    def sync_valuation_projection(
        self, snapshot, ticker: str, asset_class: str
    ) -> ProjectionSyncResult:
        """Project a ``ValuationSnapshot`` (``iip.portfolio_data.valuation``)
        into the same scoring note as the fundamental analysis -- the
        stage AssetE2ERunner computed but never persisted before."""
        mos = snapshot.margin_of_safety
        content = (
            f"Método: {snapshot.method.value}\n"
            f"Valor justo: {snapshot.fair_value}\n"
            f"Preço de mercado: {snapshot.market_price}\n"
            + (
                f"Margem de segurança: {mos:.2%}"
                if mos is not None
                else "Margem de segurança: indisponível (preço de mercado ausente)"
            )
        )
        result = self.sync_asset_section(
            ticker, asset_class, "scoring", "IIP:valuation", content
        )
        self.sync_asset_frontmatter(
            ticker,
            asset_class,
            "scoring",
            {
                "fair_value": snapshot.fair_value,
                "market_price": snapshot.market_price,
                "margin_of_safety": mos,
                "valuation_method": snapshot.method.value,
            },
        )
        return result

    def sync_quantitative_projection(
        self, stats: dict, ticker: str, asset_class: str
    ) -> ProjectionSyncResult:
        """Project the quantitative stats dict AssetE2ERunner computes
        from a persisted historical series (observations, volatility,
        mean/total return) into the scoring note."""
        content = "\n".join(f"{key}: {value}" for key, value in stats.items())
        result = self.sync_asset_section(
            ticker, asset_class, "scoring", "IIP:quantitative", content
        )
        self.sync_asset_frontmatter(
            ticker,
            asset_class,
            "scoring",
            {
                "quantitative_observations": stats.get("observations"),
                "total_return": stats.get("total_return"),
                "return_volatility": stats.get("return_volatility"),
            },
        )
        return result

    def sync_cross_asset_projection(
        self,
        concentrations,
        ticker: str,
        asset_class: str,
        *,
        own_dimensions: tuple[str, ...] = (),
    ) -> ProjectionSyncResult:
        """Project the portfolio-wide concentration result into the
        scoring note -- filtered to the dimensions this asset actually
        belongs to (its own manager/segment/asset_class), not the full
        cross-portfolio table, which would be near-identical noise
        repeated across every asset's note. The full breakdown belongs
        in the portfolio dashboard, not duplicated per asset."""
        relevant = tuple(c for c in concentrations if c.value in own_dimensions)
        breached = [c for c in relevant if c.breached]
        if relevant:
            lines = "\n".join(
                f"- {c.dimension}={c.value}: peso {c.weight:.2%} "
                f"(limite {c.limit:.2%})" + (" ⚠️ EXCEDIDO" if c.breached else "")
                for c in relevant
            )
        else:
            lines = "(nenhuma dimensão de concentração própria identificada)"
        content = f"{lines}\nGrupos analisados na carteira: {len(concentrations)}"
        result = self.sync_asset_section(
            ticker, asset_class, "scoring", "IIP:cross_asset", content
        )
        self.sync_asset_frontmatter(
            ticker, asset_class, "scoring", {"concentration_breaches": len(breached)}
        )
        return result

    def assemble(self, ticker: str) -> KnowledgeContext:
        return self.context.assemble(ticker)

    @staticmethod
    def redundancy(exposures: list[Exposure], threshold: float = 0.20):
        return find_redundant_exposures(exposures, threshold)
