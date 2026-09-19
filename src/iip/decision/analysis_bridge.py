"""Ponte entre analysis (AnalysisReport, os 5 analisadores) e decision
(IntelligenceInput, decision_engine.decide()) — achado real da segunda
rodada de auditoria em 12/09/2026: buscas por ``analysis.*decision`` e
``valuation.*decision`` em todo ``src/iip`` deram zero resultado. Os
dois sistemas são compatíveis em formato, mas nunca foram conectados
de verdade em código — cada `iip analyze --persist` real feito nesta
sessão nunca gerou uma `Decision` de verdade, só o `AnalysisReport`.

Duas conversões de escala genuínas, não arbitrárias:
    - Pillar scores são 0-100; ``IntelligenceInput`` espera 0-10
      (confirmado lendo ``decision/scoring.py``: ``composite_score``
      limita cada componente a ``max(0, min(10, valor))`` antes de
      somar).
    - ``AnalysisReport.risk_level`` usa 5 valores em inglês
      (Low/Low-Medium/Medium/Medium-High/High, derivados do próprio
      ``overall_score``); ``IntelligenceInput.risk_level`` só reconhece
      3 valores em português (Baixo/Médio/Alto) — qualquer outra string
      recebe uma penalidade de confiança padrão silenciosa (confirmado
      lendo ``confidence_score``). Mapear explicitamente evita cair
      nesse caso padrão sem perceber.

Lacuna real, não inventada: não existe pilar de "valuation" nos 9
pilares (confirmado: nenhum dos analisadores calcula valor
intrínseco, preço-alvo, DCF, Graham ou Bazin — a segunda auditoria
confirmou isso com busca exata, zero resultado no projeto inteiro).
``valuation_score`` não é derivado de nenhum pilar por proxy — isso
seria fabricar um número que parece medir algo que a análise não mede.
Quando não fornecido, fica em 5.0 (neutro, meio da escala) com aviso
explícito, nunca emprestado de outro pilar disfarçado de valuation.
"""

from __future__ import annotations

from iip.analysis import AnalysisReport, Pillar
from iip.decision.models import EvidenceRef, IntelligenceInput
from iip.decision.thesis_exit_gate import assess_thesis_exit
from iip.decision.thesis_semantic_adapter import (
    adapt_analysis_report_to_thesis_gates,
)

_RISK_LEVEL_MAP = {
    "Low": "Baixo",
    "Low-Medium": "Baixo",
    "Medium": "Médio",
    "Medium-High": "Alto",
    "High": "Alto",
}

_QUALITY_PILLARS = (
    Pillar.BUSINESS_MODEL,
    Pillar.MOAT,
    Pillar.MANAGEMENT,
    Pillar.GOVERNANCE,
    Pillar.CAPITAL_ALLOCATION,
)

_NEUTRO_SEM_VALUATION = 5.0


def analysis_to_intelligence_input(
    report: AnalysisReport,
    *,
    thesis_signal: str,
    evidence: tuple[EvidenceRef, ...],
    valuation_score: float | None = None,
) -> tuple[IntelligenceInput, tuple[str, ...]]:
    """Converte um ``AnalysisReport`` real (de qualquer um dos 5
    analisadores) num ``IntelligenceInput`` pronto pra
    ``decision_engine.decide()``.

    ``valuation_score`` (0-10) precisa ser fornecido explicitamente
    quando existir julgamento de valuation de verdade (preço-alvo,
    margem de segurança calculada à mão, etc.) — se omitido, fica
    neutro (5.0) com aviso, nunca derivado de outro pilar por engano.
    """
    warnings: list[str] = []

    pillar_scores = {p.pillar: p.score for p in report.pillar_scores}

    dividend_score = round(pillar_scores.get(Pillar.DIVIDENDS, 0.0) / 10, 2)

    quality_values = [pillar_scores[p] for p in _QUALITY_PILLARS if p in pillar_scores]
    quality_score = (
        round(sum(quality_values) / len(quality_values) / 10, 2)
        if quality_values
        else 0.0
    )

    opportunity_score = round(report.overall_score / 10, 2)

    if valuation_score is None:
        valuation_score = _NEUTRO_SEM_VALUATION
        warnings.append(
            "valuation_score não fornecido — nenhum dos 5 analisadores calcula "
            "valor intrínseco, preço-alvo ou margem de segurança (para ações, "
            "`--auto-valuation` usa o catálogo de valuation por setor: "
            "Graham/Bazin). Usando neutro (5.0) em vez de emprestar outro "
            "pilar disfarçado de valuation."
        )

    mapped_risk = _RISK_LEVEL_MAP.get(report.risk_level)
    if mapped_risk is None:
        mapped_risk = "Médio"
        warnings.append(
            f"risk_level '{report.risk_level}' não reconhecido — usando 'Médio' "
            "como padrão explícito (sem isso, decision_engine aplicaria uma "
            "penalidade de confiança de 0.15 silenciosamente para qualquer "
            "valor não mapeado)."
        )

    thesis_gates = adapt_analysis_report_to_thesis_gates(report)

    thesis_exit = assess_thesis_exit(
        fundamentals=thesis_gates["fundamentals"],
        balance_sheet=thesis_gates["balance_sheet"],
        valuation=thesis_gates["valuation"],
        dividends=thesis_gates["dividends"],
        governance=thesis_gates["governance"],
        opportunity_cost=thesis_gates["opportunity_cost"],
    )

    intelligence_input = IntelligenceInput(
        ticker=report.asset_symbol,
        thesis_signal=thesis_signal,
        risk_level=mapped_risk,
        valuation_score=valuation_score,
        dividend_score=dividend_score,
        quality_score=quality_score,
        opportunity_score=opportunity_score,
        evidence=evidence,
        thesis_exit=thesis_exit,
    )
    return intelligence_input, tuple(warnings)
