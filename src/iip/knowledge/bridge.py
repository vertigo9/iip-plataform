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

    def sync_identity_projection(
        self, asset, ticker: str, asset_class: str
    ) -> ProjectionSyncResult:
        """Project the verified registry record (``iip.portfolio.registry.
        PortfolioAsset``) into the identity note -- already-real, already-
        verified fields (CNPJ, manager, structure...), just never
        surfaced into the vault before."""
        provenance = getattr(
            asset.classification_provenance, "value", asset.classification_provenance
        )
        lines = [
            f"Ticker: {asset.ticker}",
            f"Classe: {asset.asset_class}"
            + (f" ({asset.subtype})" if asset.subtype else ""),
            f"Estrutura: {asset.structure or 'não informado'}",
            f"Segmento: {asset.segment or 'não informado'}",
            f"Gestora/Administrador: {asset.manager or 'não informado'}",
            f"CNPJ: {asset.cnpj or 'não informado'}",
            f"Indexadores: {', '.join(asset.indexation) if asset.indexation else 'não informado'}",
            f"Perfil de risco: {asset.risk_profile or 'não informado'}",
            f"Estratégia: {asset.strategy or 'não informado'}",
            f"Fonte institucional: {asset.source_url or 'não informado'}",
            f"Procedência da classificação: {provenance}",
        ]
        return self.sync_asset_section(
            ticker, asset_class, "identity", "IIP:identity", "\n".join(lines)
        )

    def sync_portfolio_composition_projection(
        self, series, ticker: str, asset_class: str
    ) -> ProjectionSyncResult:
        """Project the latest patrimonio/cotistas snapshot from the
        persisted historical series -- real when the source reports it
        (CVM-backed series), honestly absent otherwise (e.g. B3 COTAHIST
        has no such fields). Individual credit holdings (CRIs/CRAs) are
        never shown here -- that requires a management report, which
        this session has no structured source for beyond CRAA11/Sparta."""
        if not series.observations:
            content = "Sem série histórica persistida para este ativo."
        else:
            latest = series.observations[-1]
            lines = []
            if latest.patrimonio_liquido is not None:
                lines.append(
                    f"Patrimônio líquido ({latest.period}): R$ {latest.patrimonio_liquido:,.2f}"
                )
            if latest.valor_ativo is not None:
                lines.append(f"Valor do ativo: R$ {latest.valor_ativo:,.2f}")
            if latest.total_numero_cotistas is not None:
                lines.append(f"Número de cotistas: {int(latest.total_numero_cotistas)}")
            if not lines:
                lines.append(
                    f"A fonte deste ativo ({series.provider}) não reporta patrimônio/cotistas."
                )
            lines.append("")
            lines.append(
                "Composição individual de créditos (CRIs/CRAs) não disponível -- "
                "exigiria relatório de gestão, sem fonte estruturada para este ativo."
            )
            content = "\n".join(lines)
        return self.sync_asset_section(
            ticker, asset_class, "portfolio", "IIP:portfolio_composition", content
        )

    def sync_distributions_projection(
        self,
        ticker: str,
        asset_class: str,
        *,
        series=None,
        snapshot_yield_pct: float | None = None,
    ) -> ProjectionSyncResult:
        """Project dividend/yield data -- monthly TTM from the CVM-backed
        series when available (FII only; CVM's other datasets and B3
        COTAHIST don't carry this field), else a point-in-time snapshot
        (bolsai, for equities) when that's all that's real."""
        lines: list[str] = []
        monthly = [
            (o.period, o.dividend_yield_mes)
            for o in (series.observations if series is not None else ())
            if o.dividend_yield_mes is not None
        ]
        if monthly:
            recent = monthly[-12:]
            ttm = sum(value for _, value in recent) * 100
            lines.append(
                f"Dividend yield TTM (CVM, soma dos últimos {len(recent)} mês(es) com dado): {ttm:.2f}%"
            )
            lines.append("")
            lines.extend(
                f"- {period}: {value * 100:.4f}%" for period, value in monthly[-6:]
            )
        if snapshot_yield_pct is not None:
            lines.append(
                f"Dividend yield (snapshot, bolsai): {snapshot_yield_pct:.2f}%"
            )
        if not lines:
            lines.append(
                "Sem dado de distribuição disponível para este ativo nas fontes atuais."
            )
        return self.sync_asset_section(
            ticker, asset_class, "distributions", "IIP:distributions", "\n".join(lines)
        )

    def sync_events_projection(
        self,
        series,
        ticker: str,
        asset_class: str,
        *,
        manual_events: tuple[str, ...] = (),
    ) -> ProjectionSyncResult:
        """Project corporate events -- detected quota splits/groupings
        (HistoricalSeries.adjustments, from normalize_quota_splits,
        the only kind this session computes automatically) plus
        ``manual_events``: facts the user confirmed directly (e.g. a
        ticker rename), never invented here. Manual events are listed
        first since they're the reason a series' pre-event history
        might not be directly comparable, even without a detected
        price-scale break."""
        lines = [f"- {event}" for event in manual_events]
        if series.adjustments:
            lines.extend(
                f"- {adj['period']}: {adj['field']} ajustado por fator {adj['factor']:.6f} "
                f"({adj['reason']})"
                for adj in series.adjustments
            )
        if lines:
            content = "\n".join(lines)
        else:
            content = "Nenhum desdobramento/grupamento de cotas detectado na série histórica persistida."
        return self.sync_asset_section(
            ticker, asset_class, "events", "IIP:events", content
        )

    def sync_performance_projection(
        self, series, ticker: str, asset_class: str
    ) -> ProjectionSyncResult:
        """Project the persisted series' real extent (period range,
        endpoints, observation count) -- full return/volatility stats
        live in IIP:quantitative on the scoring note already, not
        duplicated here. No benchmark comparison (IFIX/CDI): no index
        data source exists in this session."""
        if not series.observations:
            content = "Sem série histórica persistida para este ativo."
        else:
            first, last = series.observations[0], series.observations[-1]
            content = (
                f"Observações: {len(series.observations)}\n"
                f"Período: {first.period} a {last.period}\n"
                f"Valor inicial: {first.valor_patrimonial_cotas}\n"
                f"Valor final: {last.valor_patrimonial_cotas}\n"
                f"Fonte: {series.provider}\n\n"
                "Estatísticas completas de retorno/volatilidade: ver seção "
                "IIP:quantitative na nota Score e Ranking.\n\n"
                "Comparação com benchmark (IFIX/CDI) não disponível -- sem fonte "
                "de índice de referência nesta sessão."
            )
        return self.sync_asset_section(
            ticker, asset_class, "performance", "IIP:performance", content
        )

    def sync_sources_summary_projection(
        self, ticker: str, asset_class: str
    ) -> ProjectionSyncResult:
        """Project a real list of this ticker's Atlas evidence entries
        (04_Evidence/), reusing ObsidianRepository.list_evidence -- a
        plain enumeration of what's already persisted, not a new
        fetch."""
        paths = self.repository.list_evidence(ticker)
        entries = []
        for path in paths:
            fields, _ = self.projector._parse_frontmatter(
                path.read_text(encoding="utf-8")
            )
            entries.append(fields)
        if not entries:
            content = "Nenhuma evidência registrada no Atlas para este ativo ainda."
        else:
            shown = entries[:30]
            lines = [
                f"- {e.get('date', '?')} · {e.get('source_type', '?')} · "
                f"{e.get('title') or (e.get('document_hash', '') or '')[:12]} · {e.get('source_url', '')}"
                for e in shown
            ]
            content = f"Total de evidências no Atlas: {len(entries)}\n\n" + "\n".join(
                lines
            )
            if len(entries) > len(shown):
                content += f"\n... e mais {len(entries) - len(shown)} entrada(s)."
        return self.sync_asset_section(
            ticker, asset_class, "sources", "IIP:sources_summary", content
        )

    def assemble(self, ticker: str) -> KnowledgeContext:
        return self.context.assemble(ticker)

    @staticmethod
    def redundancy(exposures: list[Exposure], threshold: float = 0.20):
        return find_redundant_exposures(exposures, threshold)
