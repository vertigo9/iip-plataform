"""Adaptador genérico de colheita -> evidência, reaproveitando os
MESMOS contratos reais de ``iip.intelligence.metric_evidence`` que
``fii_metric_adapter.py`` já usa e prova em produção.

Contexto (14/09/2026): encontrado em ``decision_engine.py`` um conjunto
de 4 funções (``ingest_fii_harvest``, ``ingest_equity_harvest``,
``ingest_etf_harvest``, ``ingest_fixed_income_harvest``) escritas em
paralelo, sem passar pela disciplina "descobrir -> reutilizar ->
estender -> criar" desta sessão. Elas criaram uma SEGUNDA classe
``MetricObservationIdentity`` do zero em ``decision/models.py``,
colidindo de nome com a real (``intelligence.metric_identity``), com
campos completamente diferentes e incompatíveis. Além disso:
fabricavam ``confidence_score`` só a partir do HTTP status (0.95/0.0),
usavam ``semantic_dimension`` como rótulo de categoria por lista fixa
de nomes de métrica (exatamente o uso incorreto descartado no
TRACE 15.16), e tinham um bug real de extração de ticker
(``isinstance(fetched.fii, dict)`` nunca é verdadeiro, já que ``fii``
é um dataclass, não um dict -- ticker sempre virava "UNKNOWN").

Este módulo substitui essas 4 funções por uma generalização honesta do
padrão já provado: exige ``AtlasDocument`` real (não inventa
document_id/hash), exige ``ticker`` já resolvido por quem chama (nunca
adivinha via isinstance de dict), exige ``source_locator`` por métrica
(não um dict genérico de floats sem proveniência de campo), e usa uma
política de confiança documentada por provedor -- não fabricada a
partir do status HTTP.

Limitação honesta, não escondida: hoje só FII (bolsai + CVM) tem o
transporte fechado com Atlas (``body``/``content_type``/``final_url``
em ``FetchedFii``/``FetchedFiiReport``). Equity (``FetchedFundamentals``)
e ETF ainda não têm essa extensão -- portanto ``harvest_metrics_to_evidence``
pode ser chamada para qualquer classe de ativo, mas só é honesta quando
o ``AtlasDocument`` de entrada foi construído a partir de um transporte
genuinamente fechado. Chamar isto para equity/ETF hoje exigiria
primeiro fechar o transporte deles, do mesmo jeito que fizemos pra FII
(TRACE 15.13).
"""

from __future__ import annotations

from datetime import date

from iip.atlas.models import AtlasDocument
from iip.intelligence.metric_evidence import (
    EvidenceSourceRole,
    HistoricalMetricEvidence,
    LineageStatus,
    MetricObservation,
    PeriodStatus,
    TickerLineage,
    UnitStatus,
)

# Política documentada por provedor -- não fabricada por chamada nem
# derivada do HTTP status (achado real: a versão anterior usava
# "0.95 se status==200 senão 0.0", o que trata qualquer 200 como
# igualmente confiável independente da natureza da fonte). CVM é
# disclosure regulatório obrigatório; bolsai é fornecedor de dado de
# mercado, não regulador -- reflete uma tier de proveniência mais
# baixa que a CVM, mas ainda alta o bastante pra ser ELIGIBLE (>0.80).
PROVIDER_CONFIDENCE_POLICY: dict[str, float] = {
    "cvm": 0.95,
    "b3": 0.85,
}


class MetricField:
    """Um campo de métrica com proveniência própria -- nunca um float
    solto num dict genérico. ``source_locator`` é obrigatório: sem ele
    não dá pra rastrear de onde veio o número dentro do documento."""

    __slots__ = ("metric_name", "value", "unit", "source_locator")

    def __init__(
        self, metric_name: str, value: float, unit: str, source_locator: str
    ) -> None:
        self.metric_name = metric_name
        self.value = value
        self.unit = unit
        self.source_locator = source_locator


def harvest_metrics_to_evidence(
    *,
    ticker: str,
    period: str,
    document: AtlasDocument,
    provider: str,
    source_role: EvidenceSourceRole,
    fields: list[MetricField],
    evidence_id_prefix: str,
) -> list[HistoricalMetricEvidence]:
    """Converte uma lista de campos de métrica já identificados (com
    locator próprio) em ``HistoricalMetricEvidence`` reais.

    ``ticker`` precisa já vir resolvido por quem chama -- esta função
    nunca tenta adivinhar de dict/objeto de fetch (era exatamente o bug
    real da versão anterior). ``provider`` precisa estar em
    ``PROVIDER_CONFIDENCE_POLICY``; caso contrário levanta ``ValueError``
    em vez de silenciosamente inventar uma confiança.
    """
    if provider not in PROVIDER_CONFIDENCE_POLICY:
        raise ValueError(
            f"provider '{provider}' sem política de confiança documentada "
            f"(conhecidos: {sorted(PROVIDER_CONFIDENCE_POLICY)}) -- "
            "adicione a PROVIDER_CONFIDENCE_POLICY explicitamente, não "
            "fabrique uma confiança aqui."
        )
    confidence = PROVIDER_CONFIDENCE_POLICY[provider]

    lineage = TickerLineage(
        original_ticker=ticker,
        canonical_ticker=ticker,
        status=LineageStatus.CURRENT,
    )

    evidences = []
    for field in fields:
        observation = MetricObservation(
            metric_name=field.metric_name,
            value=field.value,
            unit=field.unit,
            scale=None,
            period=period,
            period_status=PeriodStatus.EXPLICIT,
            unit_status=UnitStatus.EXPLICIT,
        )
        evidences.append(
            HistoricalMetricEvidence(
                evidence_id=f"{evidence_id_prefix}-{field.metric_name}",
                document_id=document.document_id,
                document_hash=document.content_hash,
                original_ticker=ticker,
                canonical_ticker=ticker,
                lineage=lineage,
                source_role=source_role,
                source_title=f"{provider.upper()} — {period}",
                source_date=date.fromisoformat(period[:10]),
                observation=observation,
                confidence=confidence,
                source_locator=field.source_locator,
            )
        )
    return evidences
