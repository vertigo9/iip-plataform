"""FII Metric Adapter -- dado financeiro real de CVM/Bolsai convertido
em evidência de métrica com proveniência documental completa.

Escopo desta primeira versão (deliberadamente estreito, conforme
TRACE 15.12/15.13): só ``Patrimonio_Liquido``, o metric mais simples e
mais defensável -- first-party, obrigatório por regulação, sem
ambiguidade de ``source_locator``.

Correção de um erro real do trace (achado ao vivo em 13/09/2026, com
dado real do BTLG11): os traces 15.12/15.13 atribuíram
``Patrimonio_Liquido`` a ``FiiAtivoPassivo`` -- mas testando com o ZIP
real da CVM, esse campo não existe nas colunas de ``ativo_passivo``
nenhuma (confirmado: lista completa de colunas não o contém). O código
já existente e testado desta sessão (``iip.cli.fetch_template``,
validado com dado real desde muito antes deste trace) sempre leu esse
campo de ``FiiComplemento``, não de ``FiiAtivoPassivo`` -- confirmado
de novo agora com BTLG11 real (``Patrimonio_Liquido=5.494.118.561,27``
em ``complemento``, ausente em ``ativo_passivo``). Este módulo segue o
código já verificado, não o trace.

Os demais candidatos confirmados no trace (``Valor_Patrimonial_Cotas``,
``Cotas_Emitidas`` -- também em ``FiiComplemento``, mesma correção;
``pvp``, ``dividend_yield_ttm``, ``net_asset_value``,
``shares_outstanding``, ``book_value_per_share`` do bolsai) ficam para
extensões futuras deste mesmo módulo -- cada um exige pensar de novo o
``source_role``/``source_locator`` certo, não é um "só copiar o
padrão".

Nunca fabrica ``confidence``, ``lineage`` ou ``document_id``/
``document_hash`` a partir de suposição -- a proveniência documental
vem de um ``AtlasDocument`` JÁ CONSTRUÍDO a partir da resposta HTTP
real (ver ``iip.atlas.adapter.AtlasDocumentAdapter``), nunca inventada
aqui. Quando o campo simplesmente não existe nesse registro, a função
retorna ``None`` -- "não aplicável", não um erro nem um valor
fabricado.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from iip.atlas.models import AtlasDocument
from iip.intelligence.metric_evidence import (
    EvidenceSourceRole,
    HistoricalMetricEvidence,
    LineageStatus,
    MetricObservation,
    PeriodStatus,
    PromotionStatus,
    TickerLineage,
    UnitStatus,
    assess_promotion,
)
from iip.intelligence.metric_identity import MetricObservationIdentity
from iip.intelligence.metric_persistence import build_knowledge_evidence
from iip.knowledge.bridge import KnowledgeBridge
from iip.knowledge.models import Evidence
from iip.sources.cvm_fii import FiiComplemento

# Decisão deliberada e documentada, não ajustada por fundo/período: as
# 4 (na verdade 5, incluindo enterprise_consolidation.decision_consistency)
# implementações de "reconciliation" já existentes no projeto são todas
# baseadas em CONJUNTOS de strings (matched/missing/unexpected) --
# nenhuma faz comparação numérica com tolerância. Confirmado por busca
# direta antes de escrever isto (TRACE 15.15). Este limiar reflete
# arredondamento normal de disclosure financeiro, não um ajuste por
# caso -- 0.5% é generoso o bastante pra não mascarar discrepância
# real, mas tolera o arredondamento típico de casas decimais da CVM.
NAV_CONSISTENCY_TOLERANCE_PCT = 0.5


@dataclass(frozen=True)
class NavConsistencyCheck:
    """Validação independente -- NUNCA substitui o
    ``Valor_Patrimonial_Cotas`` declarado pela CVM. Só confirma (ou
    aponta divergência) entre o valor declarado e o mesmo valor
    recalculado a partir de ``Patrimonio_Liquido`` / ``Cotas_Emitidas``
    do MESMO período/fundo. Uma divergência aqui é um sinal de
    auditoria (dado possivelmente inconsistente, período desalinhado,
    ou erro de transcrição) -- nunca motivo pra silenciosamente usar o
    valor calculado no lugar do declarado."""

    ticker: str
    period: str
    declared_nav_per_share: float
    calculated_nav_per_share: float
    absolute_difference: float
    relative_difference_pct: float
    consistent: bool


def check_nav_consistency(
    patrimonio_liquido: HistoricalMetricEvidence,
    cotas_emitidas: HistoricalMetricEvidence,
    valor_patrimonial_cotas: HistoricalMetricEvidence,
) -> NavConsistencyCheck:
    """Confere ``Patrimonio_Liquido / Cotas_Emitidas`` contra
    ``Valor_Patrimonial_Cotas`` declarado -- as três evidências
    precisam ser do MESMO ticker e do MESMO período; caso contrário a
    comparação não teria sentido nenhum, e a função lança
    ``ValueError`` em vez de comparar valores de contextos diferentes
    silenciosamente.
    """
    tickers = {
        patrimonio_liquido.canonical_ticker,
        cotas_emitidas.canonical_ticker,
        valor_patrimonial_cotas.canonical_ticker,
    }
    if len(tickers) > 1:
        raise ValueError(
            f"as três evidências precisam ser do mesmo ticker, recebido: {tickers}"
        )

    periods = {
        patrimonio_liquido.observation.period,
        cotas_emitidas.observation.period,
        valor_patrimonial_cotas.observation.period,
    }
    if len(periods) > 1:
        raise ValueError(
            f"as três evidências precisam ser do mesmo período, recebido: {periods}"
        )

    calculado = patrimonio_liquido.observation.value / cotas_emitidas.observation.value
    declarado = valor_patrimonial_cotas.observation.value

    diferenca_absoluta = abs(calculado - declarado)
    diferenca_relativa_pct = (
        (diferenca_absoluta / declarado) * 100 if declarado != 0 else float("inf")
    )

    return NavConsistencyCheck(
        ticker=patrimonio_liquido.canonical_ticker,
        period=patrimonio_liquido.observation.period,
        declared_nav_per_share=declarado,
        calculated_nav_per_share=calculado,
        absolute_difference=diferenca_absoluta,
        relative_difference_pct=diferenca_relativa_pct,
        consistent=diferenca_relativa_pct <= NAV_CONSISTENCY_TOLERANCE_PCT,
    )

# Decisão deliberada e documentada, não uma suposição por métrica: o
# Informe Mensal FII é disclosure regulatório obrigatório de primeira
# mão (dados.cvm.gov.br), categoricamente diferente de uma página
# raspada ou de um número derivado por um agregador. Essa confiança
# reflete esse NÍVEL de proveniência, aplicada de forma consistente a
# toda métrica vinda por este caminho -- nunca ajustada individualmente
# por métrica ou por fundo.
CVM_REGULATORY_CONFIDENCE = 0.95


def persist_if_eligible(
    evidence: HistoricalMetricEvidence,
    bridge: KnowledgeBridge,
) -> tuple[bool, str]:
    """Persiste ``evidence`` de verdade no vault -- só se
    ``assess_promotion()`` disser ``ELIGIBLE``. Reutiliza o mecanismo
    de persistência JÁ EXISTENTE (``KnowledgeBridge.persist_evidence``,
    o mesmo do comando ``iip persist-evidence``) -- nenhum mecanismo
    novo de persistência é criado aqui, conforme a restrição do trace.

    Retorna ``(persistiu, caminho_ou_motivo)`` -- nunca lança por causa
    de inelegibilidade, isso é um resultado esperado, não um erro.
    Quando persiste, o segundo valor é o caminho REAL do arquivo (já
    sanitizado por ``_safe_filename`` -- ``evidence_id`` pode ter
    caracteres como ``:`` que não sobrevivem intactos no nome do
    arquivo, mesmo achado que motivou a correção do ``DecisionAuditor``
    nesta mesma sessão).

    Achado real corrigido aqui: ``KnowledgeMetricEvidence.relevant_facts``
    é um ``dict[str, str]``, mas ``knowledge.models.Evidence.relevant_facts``
    (o que ``save_evidence()`` de fato grava) espera uma
    ``tuple[str, ...]``. Passar o dict direto NÃO quebra (Python itera
    um dict pelas chaves silenciosamente), mas perde todos os valores
    -- confirmado ao vivo antes de escrever esta função. A conversão
    abaixo é explícita, não um duck-type acidental.
    """
    assessment = assess_promotion(evidence)
    if assessment.status is not PromotionStatus.ELIGIBLE:
        return False, f"não elegível: {', '.join(assessment.reasons)}"

    # metric_persistence.month_date() espera periodo no formato
    # "YYYY-MM" (granularidade mensal, condizente com o informe ser
    # mensal) -- CVM's data_referencia vem como "YYYY-MM-DD" (o dia e'
    # sempre um placeholder de "primeiro do mes", nao dado real).
    # Truncar aqui, so' para esta camada -- o period completo continua
    # preservado em evidence.observation.period.
    period_yyyy_mm = evidence.observation.period[:7]

    identity = MetricObservationIdentity(
        canonical_ticker=evidence.canonical_ticker,
        original_ticker=evidence.original_ticker,
        metric_name=evidence.observation.metric_name,
        value=str(evidence.observation.value),
        unit=evidence.observation.unit,
        scale=evidence.observation.scale,
        period=period_yyyy_mm,
        # Deliberadamente None, nao uma lacuna (TRACE 15.16, investigado
        # antes de mudar por intuicao): semantic_dimension existe pra
        # desambiguar um VALOR EXTRAIDO DE TEXTO LIVRE (confirmado lendo
        # resolve_value_dimension() -- busca janela de contexto textual
        # ao redor do numero, tipo "P/VP=0,92 / NAV=R$100 / Preco=R$92"
        # no mesmo documento). Nossos tres metrics vem de COLUNAS
        # NOMEADAS E ESTRUTURADAS do CSV da CVM (Patrimonio_Liquido,
        # Valor_Patrimonial_Cotas, Cotas_Emitidas) -- zero ambiguidade
        # pra resolver, o nome da coluna ja diz o que e. Confirmado
        # tambem que IDENTITY_READY (sem dimensao) e
        # IDENTITY_READY_WITH_DIMENSION sao status PARES em
        # PersistenceBatch.ready, nao um hierarquico sobre o outro, e
        # que assess_promotion() (nosso Promotion Gate real) nem
        # referencia esse campo. Forcar NAV aqui seria usar o contrato
        # errado, nao completar um incompleto.
        semantic_dimension=None,
        document_hash=evidence.document_hash or "",
        document_id=evidence.document_id,
        source_locator=evidence.source_locator,
        lineage=evidence.lineage.status.value,
    )

    knowledge_evidence = build_knowledge_evidence(
        identity,
        title=evidence.source_title,
        source_type=evidence.source_role.value.lower(),
    )

    # Conversao explicita dict -> tupla "chave: valor", nao um
    # duck-type acidental que perderia os valores silenciosamente.
    relevant_facts = tuple(
        f"{key}: {value}" for key, value in knowledge_evidence.relevant_facts.items()
    )

    real_evidence = Evidence(
        evidence_id=knowledge_evidence.evidence_id,
        ticker=knowledge_evidence.ticker,
        date=knowledge_evidence.date,
        source_type=knowledge_evidence.source_type,
        source_url=knowledge_evidence.source_url,
        title=knowledge_evidence.title,
        document_hash=knowledge_evidence.document_hash,
        relevant_facts=relevant_facts,
    )

    try:
        saved_path = bridge.persist_evidence(real_evidence)
    except FileExistsError:
        return False, f"evidência já persistida antes: {real_evidence.evidence_id}"

    return True, str(saved_path)


def _cvm_complemento_field_to_evidence(
    complemento: FiiComplemento,
    field_name: str,
    metric_name: str,
    unit: str,
    ticker: str,
    document: AtlasDocument,
    *,
    evidence_id: str,
) -> HistoricalMetricEvidence | None:
    """Helper interno compartilhado -- os três campos da Fase A/B
    (``Patrimonio_Liquido``, ``Valor_Patrimonial_Cotas``,
    ``Cotas_Emitidas``) têm exatamente a mesma forma de proveniência
    (mesmo ``FiiComplemento``, mesmo ``source_role`` NAV_PL, mesma
    política de confiança) -- só o campo/nome/unidade mudam. Extensões
    futuras que tiverem uma forma GENUINAMENTE diferente (ex:
    ``market_cap`` derivado, ou qualquer coisa do bolsai) não devem
    tentar encaixar aqui só para reaproveitar código.
    """
    valor = complemento.valores.get(field_name)
    if valor is None:
        return None

    lineage = TickerLineage(
        original_ticker=ticker,
        canonical_ticker=ticker,
        status=LineageStatus.CURRENT,
    )

    observation = MetricObservation(
        metric_name=metric_name,
        value=float(valor),
        unit=unit,
        scale=None,
        period=complemento.data_referencia,
        period_status=PeriodStatus.EXPLICIT,
        unit_status=UnitStatus.EXPLICIT,
    )

    return HistoricalMetricEvidence(
        evidence_id=evidence_id,
        document_id=document.document_id,
        document_hash=document.content_hash,
        original_ticker=ticker,
        canonical_ticker=ticker,
        lineage=lineage,
        source_role=EvidenceSourceRole.NAV_PL,
        source_title=f"CVM Informe Mensal FII — {complemento.data_referencia}",
        source_date=date.fromisoformat(complemento.data_referencia),
        observation=observation,
        confidence=CVM_REGULATORY_CONFIDENCE,
        source_locator=f"complemento[{complemento.cnpj_fundo_classe}].{field_name}",
    )


def cvm_patrimonio_liquido_to_evidence(
    complemento: FiiComplemento,
    ticker: str,
    document: AtlasDocument,
    *,
    evidence_id: str,
) -> HistoricalMetricEvidence | None:
    """Converte um ``Patrimonio_Liquido`` real de um ``FiiComplemento``
    (linha já parseada do ZIP da CVM) numa ``HistoricalMetricEvidence``
    completa e promovível.

    ``document`` precisa ser o ``AtlasDocument`` real construído a
    partir da MESMA resposta HTTP que originou ``complemento`` --
    ``document_id``/``document_hash`` vêm de lá, nunca calculados aqui
    de novo (evita a proveniência divergir do documento real).
    """
    return _cvm_complemento_field_to_evidence(
        complemento,
        "Patrimonio_Liquido",
        "patrimonio_liquido",
        "BRL",
        ticker,
        document,
        evidence_id=evidence_id,
    )


def cvm_valor_patrimonial_cotas_to_evidence(
    complemento: FiiComplemento,
    ticker: str,
    document: AtlasDocument,
    *,
    evidence_id: str,
) -> HistoricalMetricEvidence | None:
    """Converte um ``Valor_Patrimonial_Cotas`` (NAV por cota) real de um
    ``FiiComplemento`` numa ``HistoricalMetricEvidence`` completa e
    promovível.

    Fase B -- confirmado com dado real do BTLG11 antes de escrever esta
    função: ``Valor_Patrimonial_Cotas`` (106,86346) é internamente
    consistente com ``Patrimonio_Liquido / Cotas_Emitidas``
    (7.580.921.710,93 / 70.940.261 = 106,8635) -- mesmo mês, mesmo
    fundo, mesmo ``FiiComplemento``.
    """
    return _cvm_complemento_field_to_evidence(
        complemento,
        "Valor_Patrimonial_Cotas",
        "valor_patrimonial_cotas",
        "BRL",
        ticker,
        document,
        evidence_id=evidence_id,
    )


def cvm_cotas_emitidas_to_evidence(
    complemento: FiiComplemento,
    ticker: str,
    document: AtlasDocument,
    *,
    evidence_id: str,
) -> HistoricalMetricEvidence | None:
    """Converte um ``Cotas_Emitidas`` (quantidade de cotas em
    circulação) real de um ``FiiComplemento`` numa
    ``HistoricalMetricEvidence`` completa e promovível.

    Fase B. Diferente de ``Patrimonio_Liquido``/``Valor_Patrimonial_Cotas``
    (valores monetários em BRL), este é uma contagem -- unidade
    explícita ``"cotas"``, não ``"BRL"``. Ainda assim classificado como
    ``NAV_PL`` (mesmo ``source_role``): não é um "resultado" nem uma
    "distribuição", é dado estrutural do mesmo informe de patrimônio,
    usado junto com ``Patrimonio_Liquido`` para calcular
    ``Valor_Patrimonial_Cotas`` por conta própria quando necessário.
    """
    return _cvm_complemento_field_to_evidence(
        complemento,
        "Cotas_Emitidas",
        "cotas_emitidas",
        "cotas",
        ticker,
        document,
        evidence_id=evidence_id,
    )

