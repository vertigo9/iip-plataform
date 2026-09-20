"""Contrato dos indicadores macroeconômicos: o que é cada série, de onde vem e o que se sabe
(e não se sabe) sobre ela.

A macro do IIP é CONTEXTO, cenário e premissa de valuation; não decide aporte nem peso-alvo
(decisão do usuário, 20/09/2026). Este módulo só define o contrato e o catálogo dos
indicadores; a persistência está em ``iip.macro.store`` e a coleta em ``iip.macro.collector``.

Cada observação guarda: qual indicador, a COMPETÊNCIA (o período a que o valor se refere), o
valor, a unidade (vem do indicador), a DATA DE COLETA e se o valor é provisório. A data de
PUBLICAÇÃO pela fonte NÃO é guardada porque as duas fontes não a expõem: o BACEN SGS devolve
só data e valor, e o IBGE SIDRA só período e valor. O que dá para afirmar é "conhecido em tal
data" a partir da primeira coleta; o que se coletou antes não existe, e um valor revisado pela
fonte depois aparece como uma nova observação, sem apagar a anterior. Por isso um dado macro
coletado hoje NÃO serve para reconstruir o que se sabia numa decisão do passado.

Competência, por frequência: diária ``AAAA-MM-DD``, mensal ``AAAA-MM``, trimestral
``AAAA-Tn``.

Verificação dos indicadores (20/09/2026), registrada em ``verified_by``:
  - "catálogo BCB": o título, a periodicidade e a unidade conferem com o catálogo de dados
    abertos do BCB (dadosabertos.bcb.gov.br) para o código SGS;
  - "IBGE = BACEN": o mesmo indicador existe nas duas fontes e os últimos valores batem
    (IPCA mensal: 0,07 e -0,32 nas duas; desocupação PNAD: 5,4 no 2º trimestre de 2026);
  - "documentação BCB": o código é o documentado para o indicador, sem registro no catálogo
    aberto; o valor é coerente com outra série verificada (o CDI diário é igual à Selic diária).
"""

from __future__ import annotations

from dataclasses import dataclass

DAILY, MONTHLY, QUARTERLY = "daily", "monthly", "quarterly"

BACEN_SGS = "bacen_sgs"
IBGE_SIDRA = "ibge_sidra"

# categorias e os rótulos que a nota usa
CATEGORY_LABELS = {
    "juros": "Juros",
    "inflacao": "Inflação",
    "cambio": "Câmbio",
    "atividade": "Atividade e emprego",
    "credito": "Crédito",
}


@dataclass(frozen=True)
class MacroIndicator:
    id: str
    name: str
    source: str  # BACEN_SGS | IBGE_SIDRA
    source_ref: str  # código SGS, ou "agregado/variável" do SIDRA
    unit: str
    frequency: str
    category: str
    description: str
    verified_by: str
    # os valores do mês em curso ainda mudam até o mês fechar (Selic e CDI acumulados no mês)
    accumulates_in_month: bool = False
    # a série mais velha que isto (dias depois do FIM da competência) está defasada: a fonte
    # normalmente já publicou algo mais novo
    stale_after_days: int = 60
    # as classes de ativo em que o indicador é relevante; é um mapa de LEITURA, não uma
    # relação causal: dizer que a Selic importa para os FIIs não diz o que ela fará com eles
    relevant_for: tuple[str, ...] = ()
    # o mesmo indicador em outra fonte, para conferir as duas
    cross_check_with: str | None = None
    # como comparar com 12 meses antes: "pp" (diferença na própria unidade, para taxas),
    # "pct" (variação percentual, para níveis como índice e câmbio) ou "none" (fluxos
    # mensais, em que a variação de uma taxa mensal em 12 meses não significa nada)
    change_kind: str = "none"


@dataclass(frozen=True)
class MacroObservation:
    indicator_id: str
    reference: str  # a competência, no formato da frequência do indicador
    value: float | None
    collected_at: str  # AAAA-MM-DD da coleta
    provisional: bool = False


INDICATORS: dict[str, MacroIndicator] = {
    i.id: i
    for i in (
        MacroIndicator(
            "selic_meta",
            "Meta Selic definida pelo Copom",
            BACEN_SGS,
            "432",
            "% ao ano",
            DAILY,
            "juros",
            "A meta da taxa básica, definida nas reuniões do Copom; muda por decisão, não "
            "todo dia.",
            "catálogo BCB",
            stale_after_days=10,
            relevant_for=("Renda fixa bancária", "FI-Infra", "FI-Agro", "FII", "Ações"),
            change_kind="pp",
        ),
        MacroIndicator(
            "selic_diaria",
            "Taxa Selic",
            BACEN_SGS,
            "11",
            "% ao dia",
            DAILY,
            "juros",
            "A taxa média do dia das operações compromissadas (a Selic efetiva).",
            "catálogo BCB",
            stale_after_days=10,
            relevant_for=("Renda fixa bancária", "ETF"),
        ),
        MacroIndicator(
            "selic_mes",
            "Selic acumulada no mês",
            BACEN_SGS,
            "4390",
            "% ao mês",
            MONTHLY,
            "juros",
            "A Selic acumulada no mês; o mês em curso é parcial.",
            "catálogo BCB",
            accumulates_in_month=True,
            stale_after_days=45,
            relevant_for=("Renda fixa bancária", "ETF"),
        ),
        MacroIndicator(
            "cdi_diario",
            "Taxa DI (CDI)",
            BACEN_SGS,
            "12",
            "% ao dia",
            DAILY,
            "juros",
            "A taxa DI do dia, referência de boa parte da renda fixa e dos fundos de crédito.",
            "documentação BCB",
            stale_after_days=10,
            relevant_for=("Renda fixa bancária", "FI-Infra", "FI-Agro", "FII"),
        ),
        MacroIndicator(
            "cdi_mes",
            "CDI acumulado no mês",
            BACEN_SGS,
            "4391",
            "% ao mês",
            MONTHLY,
            "juros",
            "O CDI acumulado no mês; o mês em curso é parcial.",
            "documentação BCB",
            accumulates_in_month=True,
            stale_after_days=45,
            relevant_for=("Renda fixa bancária", "FI-Infra", "FI-Agro"),
        ),
        MacroIndicator(
            "ipca_mensal",
            "IPCA, variação mensal",
            BACEN_SGS,
            "433",
            "% ao mês",
            MONTHLY,
            "inflacao",
            "A inflação oficial do mês.",
            "IBGE = BACEN",
            stale_after_days=60,
            relevant_for=("Renda fixa bancária", "FII", "FI-Infra", "FI-Agro", "Ações"),
            cross_check_with="ipca_mensal_ibge",
        ),
        MacroIndicator(
            "ipca_mensal_ibge",
            "IPCA, variação mensal (IBGE)",
            IBGE_SIDRA,
            "1737/63",
            "% ao mês",
            MONTHLY,
            "inflacao",
            "O mesmo IPCA mensal, direto da fonte (IBGE), para conferir com o do BACEN.",
            "IBGE = BACEN",
            stale_after_days=60,
            relevant_for=("Renda fixa bancária", "FII", "FI-Infra", "FI-Agro"),
            cross_check_with="ipca_mensal",
        ),
        MacroIndicator(
            "ipca_12m",
            "IPCA acumulado em 12 meses",
            BACEN_SGS,
            "13522",
            "% em 12 meses",
            MONTHLY,
            "inflacao",
            "A inflação dos últimos 12 meses, a que reajusta contratos anuais.",
            "documentação BCB",
            stale_after_days=60,
            relevant_for=("FII", "FI-Infra", "FI-Agro", "Renda fixa bancária"),
            change_kind="pp",
        ),
        MacroIndicator(
            "igpm_mensal",
            "IGP-M, variação mensal",
            BACEN_SGS,
            "189",
            "% ao mês",
            MONTHLY,
            "inflacao",
            "O índice que reajusta muitos contratos de aluguel.",
            "documentação BCB",
            stale_after_days=60,
            relevant_for=("FII",),
        ),
        MacroIndicator(
            "usd_venda",
            "Dólar americano (venda), câmbio livre",
            BACEN_SGS,
            "1",
            "R$ por US$",
            DAILY,
            "cambio",
            "A cotação diária de venda do dólar.",
            "catálogo BCB",
            stale_after_days=10,
            relevant_for=("Ações", "ETF"),
            change_kind="pct",
        ),
        MacroIndicator(
            "ibc_br",
            "Índice de Atividade Econômica do Banco Central (IBC-Br)",
            BACEN_SGS,
            "24363",
            "índice",
            MONTHLY,
            "atividade",
            "A aproximação mensal do PIB feita pelo BCB.",
            "catálogo BCB",
            stale_after_days=110,
            relevant_for=("Ações", "FII"),
            change_kind="pct",
        ),
        MacroIndicator(
            "desocupacao_mensal",
            "Taxa de desocupação (PNAD Contínua, trimestre móvel)",
            BACEN_SGS,
            "24369",
            "%",
            MONTHLY,
            "atividade",
            "A desocupação do trimestre móvel, publicada pelo IBGE e replicada no SGS.",
            "IBGE = BACEN",
            stale_after_days=110,
            relevant_for=("Ações", "FII"),
            change_kind="pp",
        ),
        MacroIndicator(
            "desocupacao_ibge",
            "Taxa de desocupação (PNAD Contínua trimestral, IBGE)",
            IBGE_SIDRA,
            "4099/4099",
            "%",
            QUARTERLY,
            "atividade",
            "A desocupação do trimestre, direto do IBGE.",
            "IBGE = BACEN",
            stale_after_days=160,
            relevant_for=("Ações", "FII"),
            change_kind="pp",
        ),
        MacroIndicator(
            "inadimplencia_total",
            "Inadimplência da carteira de crédito, total",
            BACEN_SGS,
            "21082",
            "%",
            MONTHLY,
            "credito",
            "O percentual da carteira de crédito do sistema financeiro com atraso relevante.",
            "catálogo BCB",
            stale_after_days=110,
            relevant_for=("FII", "FI-Infra", "FI-Agro", "Renda fixa bancária"),
            change_kind="pp",
        ),
    )
}


def indicator(indicator_id: str) -> MacroIndicator:
    try:
        return INDICATORS[indicator_id]
    except KeyError:
        raise KeyError(
            f"indicador macro desconhecido: {indicator_id!r} "
            f"(catálogo: {', '.join(sorted(INDICATORS))})"
        ) from None
