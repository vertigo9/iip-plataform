"""Analisa e persiste TODA a carteira de uma vez — reaproveita as
mesmas funções de busca do ``refresh_portfolio`` e o mesmo caminho de
persistência do comando ``iip analyze --persist`` (via
``KnowledgeBridge.sync_analysis_projection``). Nenhuma lógica nova de
busca ou análise é criada aqui, só o laço com isolamento por posição.

Nunca fabrica ``sector``/``industry``. Só analisa uma posição quando
esses dois campos existem de verdade — confirmados pelo usuário no
registro (``PortfolioAsset.sector``/``.industry``, preenchido a mão
para as 14 ações) ou, para fundos, derivados de ``structure``/
``segment`` (também dado real do registro, nunca adivinhado a partir
do ticker). Posições sem nenhum dos dois são puladas com motivo
claro, nunca gravadas com um placeholder tipo "REPLACE_WITH_SECTOR"
como se fosse uma análise de verdade.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from iip.portfolio.refresh import PositionOutcome, _template_type_for
from iip.portfolio.registry import PortfolioAsset, assets_refreshable_now
from iip.sources.shared_caches import with_shared_fetch_caches

# _template_type_for() usa "fiagro" (nome do dataset CVM); ANALYZERS
# (iip.cli.main) usa "agro" (nome do analisador) -- mesma distinção já
# feita na CLI de fetch-template, repetida aqui pelo mesmo motivo.
_TEMPLATE_TYPE_TO_ANALYZER_TYPE = {
    "fii": "fii",
    "etf": "etf",
    "equity": "equity",
    "fixed_income": "fixed_income",
    "fiagro": "agro",
}


@dataclass(frozen=True)
class AnalysisRunResult:
    outcomes: tuple[PositionOutcome, ...]

    @property
    def succeeded(self) -> tuple[PositionOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "ok")

    @property
    def failed(self) -> tuple[PositionOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "erro")

    @property
    def skipped(self) -> tuple[PositionOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "pulado")


def _sector_industry_for(position: PortfolioAsset) -> tuple[str | None, str | None]:
    """Só retorna algo quando existe dado real no registro -- nunca
    fabrica um placeholder aqui."""
    if position.sector and position.industry:
        return position.sector, position.industry
    if position.structure and position.segment:
        return position.structure, position.segment
    return None, None


@dataclass(frozen=True)
class _BatchDeps:
    """Injetável por teste -- mesmo padrão de ``fetch_fii``/etc em
    ``refresh_portfolio``."""

    fetch_fii: object = None
    fetch_etf: object = None
    fetch_fixed_income: object = None
    fetch_equity: object = None
    fetch_fiagro: object = None
    analyzers: dict = field(default_factory=dict)
    knowledge_bridge_cls: object = None


@with_shared_fetch_caches
def analyze_portfolio(
    *,
    bolsai_api_key: str | None,
    brapi_token: str | None,
    vault_path: str,
    ano: int | None = None,
    mes: int | None = None,
    positions: tuple[PortfolioAsset, ...] | None = None,
    deps: _BatchDeps | None = None,
) -> AnalysisRunResult:
    """Busca dado real, roda o analisador certo, e persiste no vault --
    para toda posição que tem sector/industry reais disponíveis.
    """
    import datetime as _dt

    from iip.analysis import AssetData
    from iip.cli.fetch_template import (
        fetch_equity_template_live,
        fetch_etf_template_live,
        fetch_fiagro_template_live,
        fetch_fii_template_live,
        fetch_fixed_income_template_live,
    )
    from iip.cli.main import ANALYZERS
    from iip.knowledge.bridge import KnowledgeBridge

    deps = deps or _BatchDeps()
    fetch_fii = deps.fetch_fii or fetch_fii_template_live
    fetch_etf = deps.fetch_etf or fetch_etf_template_live
    fetch_fixed_income = deps.fetch_fixed_income or fetch_fixed_income_template_live
    fetch_equity = deps.fetch_equity or fetch_equity_template_live
    fetch_fiagro = deps.fetch_fiagro or fetch_fiagro_template_live
    analyzers = deps.analyzers or ANALYZERS
    knowledge_bridge_cls = deps.knowledge_bridge_cls or KnowledgeBridge

    hoje = _dt.date.today()  # noqa: DTZ011 — data de calendário (referência CVM), não timestamp
    ano_efetivo = ano or hoje.year
    mes_efetivo = mes or hoje.month
    # DFP de um ano fiscal só sai meses depois do fim desse ano -- ver
    # mesmo comentário em iip.cli.main's fetch-template equity branch.
    ano_dfp_efetivo = ano or (hoje.year - 1)

    all_positions = positions if positions is not None else assets_refreshable_now()
    bridge = knowledge_bridge_cls(vault_path)

    outcomes: list[PositionOutcome] = []
    for position in all_positions:
        template_type = _template_type_for(position)
        if template_type is None:
            outcomes.append(
                PositionOutcome(
                    ticker=position.ticker,
                    status="pulado",
                    detail="classe de ativo sem fetch automático ainda",
                )
            )
            continue

        sector, industry = _sector_industry_for(position)
        if not sector or not industry:
            outcomes.append(
                PositionOutcome(
                    ticker=position.ticker,
                    status="pulado",
                    detail=(
                        "sem sector/industry reais no registro — preencha "
                        "PortfolioAsset.sector/.industry (ou "
                        ".structure/.segment pra fundos) antes de analisar"
                    ),
                )
            )
            continue

        try:
            if template_type == "fii":
                template, _ = fetch_fii(
                    position.ticker, position.cnpj, ano_efetivo, bolsai_api_key
                )
            elif template_type == "etf":
                template, _ = fetch_etf(
                    position.ticker, position.cnpj, ano_efetivo, mes_efetivo, brapi_token
                )
            elif template_type == "equity":
                template, _ = fetch_equity(
                    position.ticker,
                    position.cnpj,
                    ano_dfp_efetivo,
                    bolsai_api_key,
                    brapi_token,
                )
            elif template_type == "fiagro":
                template, _ = fetch_fiagro(
                    position.ticker, position.cnpj, ano_efetivo, mes_efetivo, brapi_token
                )
            else:  # fixed_income
                template, _ = fetch_fixed_income(
                    position.ticker, position.cnpj, ano_efetivo, mes_efetivo
                )
        except Exception as exc:  # noqa: BLE001 — isolamento por posição, mesmo padrão de refresh_portfolio
            outcomes.append(
                PositionOutcome(ticker=position.ticker, status="erro", detail=str(exc))
            )
            continue

        analyzer_type = _TEMPLATE_TYPE_TO_ANALYZER_TYPE[template_type]
        data = AssetData(
            symbol=position.ticker,
            sector=sector,
            industry=industry,
            market_cap=template.get("market_cap"),
            price=template.get("price"),
            financials=template.get("financials", {}),
        )

        try:
            report = analyzers[analyzer_type]().analyze(data)
            resultado_persist = bridge.sync_analysis_projection(
                report, position.ticker, analyzer_type
            )
        except Exception as exc:  # noqa: BLE001 — isolamento por posição, mesmo padrão de refresh_portfolio
            outcomes.append(
                PositionOutcome(ticker=position.ticker, status="erro", detail=str(exc))
            )
            continue

        outcomes.append(
            PositionOutcome(
                ticker=position.ticker,
                status="ok",
                detail=f"{resultado_persist.status.value} — {resultado_persist.path}",
            )
        )

    return AnalysisRunResult(outcomes=tuple(outcomes))
