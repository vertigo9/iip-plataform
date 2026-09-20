"""Decisão da carteira inteira numa rodada: análise + valuation + evidência real -> ``Decision``.

Junta o que os outros lotes fazem separado. ``analyze_portfolio`` produz o relatório dos
analisadores, ``value_portfolio`` o valor justo, e ``iip analyze --decide`` transforma os
dois numa decisão, mas um ativo por vez e com o ``--evidence-id`` na mão. Aqui o laço é o
mesmo para todas as posições, com UMA busca de template por posição: o mesmo template
alimenta o analisador e o valuation, em vez de gastar a cota do bolsai duas vezes.

Para isso o template é buscado com o plano "superconjunto" dos dois lotes (o que o valuation
pede a mais -- bolsai no FIAGRO, ``brapi_token`` no FI-Infra listado -- só acrescenta campos;
os insumos exclusivos do ``FIIAnalyzer`` ficam ligados).

Regras que não mudam, herdadas do resto do projeto:
  - nunca fabrica ``sector``/``industry`` nem evidência: a evidência citada é a mais recente
    que JÁ EXISTE no vault para o ativo (``iip.portfolio.evidence_lookup``); sem nenhuma, a
    posição é pulada com o motivo;
  - sem valor de valuation a nota fica neutra (5,0) e o aviso do analysis_bridge aparece;
  - o sinal de tese é ``Neutro`` (nenhum código julga a tese; é o padrão do ``analyze``);
  - isolamento por posição: uma falha vira ``erro`` daquela linha, nunca derruba a rodada.

A decisão só é gravada com ``persist=True``. O id é ``DEC-<TICKER>-<data>`` e o registro é
append-only: rodar de novo no mesmo dia não regrava (o resultado diz ``já existia hoje``).
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Callable
from dataclasses import dataclass, field

from iip.portfolio.batch_analyze import (
    _TEMPLATE_TYPE_TO_ANALYZER_TYPE,
    _sector_industry_for,
)
from iip.portfolio.batch_core import FetchPlan, fetch_template_for, resolve_fetchers
from iip.portfolio.batch_value import _default_fetch_rate, _valuation_class
from iip.portfolio.evidence_lookup import (
    find_evidence_ids,
    previous_decision_verdict,
)
from iip.portfolio.look_through_value import default_fetch_cda, look_through_inputs
from iip.portfolio.refresh import _template_type_for, missing_required_market_data
from iip.portfolio.registry import PortfolioAsset, assets_refreshable_now
from iip.portfolio_data.valuation_exceptions import (
    ValuationExceptions,
    exceptions_for,
)
from iip.sources.cvm_cda import CdaPortfolio
from iip.sources.shared_caches import with_shared_fetch_caches
from iip.sources.tesouro_direto import NtnbRate

THESIS_SIGNAL = "Neutro"

# o vault grava o vocabulário do conhecimento (ENCERRAR); o motor de decisão diz VENDER
_ENGINE_NAME = {"ENCERRAR": "VENDER"}


def engine_verdict_name(knowledge_verdict: str | None) -> str | None:
    """A decisão anterior lida do vault, no vocabulário do motor, para comparar com a de
    hoje sem tratar ENCERRAR -> VENDER como mudança."""
    if knowledge_verdict is None:
        return None
    return _ENGINE_NAME.get(knowledge_verdict, knowledge_verdict)


@dataclass(frozen=True)
class DecisionOutcome:
    ticker: str
    status: str  # "ok", "pulado", "erro"
    detail: str
    asset_class: str | None = None
    verdict: str | None = None
    score: float | None = None
    confidence: float | None = None
    previous_verdict: str | None = None
    analysis_score: float | None = None
    analysis_recommendation: str | None = None
    valuation_score: float | None = None
    valuation_note: str = ""
    thesis_exit_state: str | None = None
    evidence_ids: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    persisted: str = ""  # "gravada", "já existia hoje" ou "" (sem --persist)


@dataclass(frozen=True)
class DecisionRunResult:
    outcomes: tuple[DecisionOutcome, ...]
    ntnb_note: str
    decision_date: _dt.date

    @property
    def succeeded(self) -> tuple[DecisionOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "ok")

    @property
    def failed(self) -> tuple[DecisionOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "erro")

    @property
    def skipped(self) -> tuple[DecisionOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "pulado")

    @property
    def changed(self) -> tuple[DecisionOutcome, ...]:
        return tuple(
            o
            for o in self.succeeded
            if o.previous_verdict and o.previous_verdict != o.verdict
        )


@dataclass(frozen=True)
class _Deps:
    """Injetável por teste, como os demais lotes."""

    fetch_fii: object = None
    fetch_etf: object = None
    fetch_fixed_income: object = None
    fetch_equity: object = None
    fetch_fiagro: object = None
    fetch_rate: Callable[[], NtnbRate | None] | None = None
    fetch_cda: Callable[[str], CdaPortfolio] | None = None
    bridge_cls: Callable[[str], object] | None = None
    analyzers: dict = field(default_factory=dict)


def _ntnb(fetch_rate: Callable[[], NtnbRate | None]) -> tuple[NtnbRate | None, str]:
    try:
        rate = fetch_rate()
    # a taxa é consulta de mercado opcional; falhar aqui não derruba a rodada
    except Exception as exc:  # noqa: BLE001
        return (
            None,
            f"não consegui buscar a taxa da NTN-B: {exc} — Bazin fica sem valor.",
        )
    if rate is None:
        return None, "taxa real da NTN-B indisponível — Bazin fica sem valor."
    return rate, (
        f"NTN-B longa (venc. {rate.maturity:%d/%m/%Y}, ref. "
        f"{rate.reference_date:%d/%m/%Y}): IPCA + {rate.real_yield:.2%}"
    )


@with_shared_fetch_caches
def decide_portfolio(
    *,
    bolsai_api_key: str | None,
    brapi_token: str | None,
    vault_path: str,
    persist: bool = False,
    ano: int | None = None,
    positions: tuple[PortfolioAsset, ...] | None = None,
    today: _dt.date | None = None,
    deps: _Deps | None = None,
    exceptions: ValuationExceptions | None = None,
) -> DecisionRunResult:
    from iip.analysis import AssetData
    from iip.cli.main import ANALYZERS
    from iip.decision.analysis_bridge import analysis_to_intelligence_input
    from iip.decision.catalog_valuation import catalog_valuation_for_decision
    from iip.decision.decision_engine import decide
    from iip.decision.knowledge_bridge import to_knowledge_decision
    from iip.decision.models import EvidenceRef
    from iip.knowledge.bridge import KnowledgeBridge
    from iip.knowledge.models import Verdict as KnowledgeVerdict

    deps = deps or _Deps()
    # as exceções metodológicas do vault valem para a decisão como para o valuation; um
    # arquivo inválido levanta ValueError aqui, antes de decidir qualquer posição
    if exceptions is None:
        exceptions = exceptions_for(vault_path)
    fetchers = resolve_fetchers(
        fii=deps.fetch_fii,
        etf=deps.fetch_etf,
        fixed_income=deps.fetch_fixed_income,
        equity=deps.fetch_equity,
        fiagro=deps.fetch_fiagro,
    )
    analyzers = deps.analyzers or ANALYZERS
    rate, ntnb_note = _ntnb(deps.fetch_rate or _default_fetch_rate)
    market_inputs = {"ntnb_real_yield": rate.real_yield if rate else None}

    # data de calendário (a data da decisão e o mês do informe), não timestamp
    hoje = today or _dt.date.today()  # noqa: DTZ011
    plan = FetchPlan(
        ano=hoje.year,
        mes=hoje.month,
        ano_dfp=ano or (hoje.year - 1),
        bolsai_api_key=bolsai_api_key,
        brapi_token=brapi_token,
        fiagro_uses_bolsai=True,
    )
    bridge = (deps.bridge_cls or KnowledgeBridge)(vault_path)
    all_positions = positions if positions is not None else assets_refreshable_now()

    outcomes: list[DecisionOutcome] = []
    for position in all_positions:
        ticker = position.ticker
        analysis_type = _TEMPLATE_TYPE_TO_ANALYZER_TYPE.get(
            _template_type_for(position) or ""
        )
        catalog_class = _valuation_class(position)
        if analysis_type is None or catalog_class is None:
            outcomes.append(
                DecisionOutcome(
                    ticker,
                    "pulado",
                    "classe de ativo sem fetch automático ainda",
                )
            )
            continue

        sector, industry = _sector_industry_for(position)
        if not sector or not industry:
            outcomes.append(
                DecisionOutcome(
                    ticker,
                    "pulado",
                    "sem sector/industry reais no registro — preencha "
                    "PortfolioAsset.sector/.industry antes de decidir",
                    asset_class=catalog_class,
                )
            )
            continue

        evidence_ids = find_evidence_ids(vault_path, ticker)
        if not evidence_ids:
            outcomes.append(
                DecisionOutcome(
                    ticker,
                    "pulado",
                    "sem evidência real no vault (04_Evidence) para este ativo — a "
                    "decisão não fabrica evidência",
                    asset_class=catalog_class,
                )
            )
            continue

        try:
            template, _ = fetch_template_for(catalog_class, position, fetchers, plan)
            incomplete = missing_required_market_data(
                catalog_class,
                template,
                bolsai_api_key=bolsai_api_key,
                brapi_token=brapi_token,
            )
            if incomplete:
                outcomes.append(
                    DecisionOutcome(
                        ticker, "erro", incomplete, asset_class=catalog_class
                    )
                )
                continue

            price = template.get("price")
            financials = dict(template.get("financials", {}))
            look_through_note = ""
            if catalog_class == "fmp_fgts":
                # a cota não tem preço: compara-se com o próprio NAV (ver batch_value)
                price = financials.get("nav_per_share")
                look = look_through_inputs(
                    cnpj=position.cnpj,
                    fetch_cda=deps.fetch_cda or default_fetch_cda,
                    fetch_equity=fetchers.equity,
                    plan=plan,
                    market_inputs=market_inputs,
                    exceptions=exceptions,
                )
                financials.update(look.inputs)
                look_through_note = look.note

            data = AssetData(
                symbol=ticker,
                sector=sector,
                industry=industry,
                market_cap=template.get("market_cap"),
                price=template.get("price"),
                financials=template.get("financials", {}),
            )
            report = analyzers[analysis_type]().analyze(data)

            valuation = catalog_valuation_for_decision(
                ticker=ticker,
                asset_class=catalog_class,
                sector=sector,
                industry=industry,
                price=price,
                financials=financials,
                ntnb_real_yield=rate.real_yield if rate else None,
                exceptions=exceptions,
            )
            intelligence_input, bridge_warnings = analysis_to_intelligence_input(
                report,
                thesis_signal=THESIS_SIGNAL,
                evidence=tuple(EvidenceRef(eid) for eid in evidence_ids),
                valuation_score=valuation.score,
            )
            decision = decide(intelligence_input)
        # isolamento por posição, mesmo padrão dos outros lotes
        except Exception as exc:  # noqa: BLE001
            outcomes.append(
                DecisionOutcome(ticker, "erro", str(exc), asset_class=catalog_class)
            )
            continue

        previous = previous_decision_verdict(vault_path, ticker, before=hoje)
        persisted = ""
        if persist:
            try:
                knowledge_decision = to_knowledge_decision(
                    decision,
                    decision_id=f"DEC-{ticker}-{hoje.isoformat()}",
                    date=hoje,
                    previous_verdict=(KnowledgeVerdict(previous) if previous else None),
                )
                bridge.persist_decision(knowledge_decision)
                persisted = "gravada"
            except FileExistsError:
                persisted = "já existia hoje"
            # auditoria (evidência sumiu) ou verdict fora do enum: erro só desta posição
            except ValueError as exc:
                outcomes.append(
                    DecisionOutcome(ticker, "erro", str(exc), asset_class=catalog_class)
                )
                continue

        valuation_note = valuation.explanation
        if look_through_note:
            valuation_note += f" ({look_through_note})"
        outcomes.append(
            DecisionOutcome(
                ticker=ticker,
                status="ok",
                detail=f"{decision.verdict.value} (score {decision.score:.2f}/10)",
                asset_class=catalog_class,
                verdict=decision.verdict.value,
                score=decision.score,
                confidence=decision.confidence,
                previous_verdict=engine_verdict_name(previous),
                analysis_score=report.overall_score,
                analysis_recommendation=report.recommendation,
                valuation_score=valuation.score,
                valuation_note=valuation_note,
                thesis_exit_state=(
                    decision.thesis_exit.state.value
                    if decision.thesis_exit is not None
                    else None
                ),
                evidence_ids=evidence_ids,
                reasons=decision.reasons,
                warnings=bridge_warnings,
                persisted=persisted,
            )
        )

    return DecisionRunResult(tuple(outcomes), ntnb_note, hoje)
