"""Núcleo compartilhado dos lotes da carteira: ``refresh_portfolio``,
``analyze_portfolio`` e ``value_portfolio``.

Os três repetiam o mesmo bloco de resolução dos buscadores de template (com
injeção para teste) e o mesmo despacho por tipo de ativo. Aqui ele existe uma vez
só: adicionar uma classe de ativo passa a ser um ponto (``fetch_template_for``, mais
``iip.portfolio.refresh._template_type_for``), não três arquivos.

O que continua em cada lote é o que é deles: a decisão de pular uma posição, o que
se faz com o template depois de buscado (gravar snapshot, analisar, avaliar) e o
isolamento de falha por posição. As diferenças de propósito entre os lotes viram
campos explícitos do ``FetchPlan`` -- o valuation usa o ano corrente para FII e
FIAGRO (informe mensal) e passa ``bolsai_api_key`` ao FIAGRO; o FI-Infra listado
(``"fi_infra"``, só o valuation o distingue de ``"fixed_income"``) recebe o
``brapi_token`` -- e nada muda de comportamento
(``tests/test_portfolio_batch_dispatch.py`` congela os argumentos de cada chamada).
"""

from __future__ import annotations

import datetime as _dt
import functools
from collections.abc import Callable
from dataclasses import dataclass

# (template, resultado): o par que todo ``fetch_*_template_live`` devolve
TemplateFetcher = Callable[..., tuple[dict, object]]


@dataclass(frozen=True)
class BatchFetchers:
    fii: TemplateFetcher
    etf: TemplateFetcher
    fixed_income: TemplateFetcher
    equity: TemplateFetcher
    fiagro: TemplateFetcher


def resolve_fetchers(
    *,
    fii: TemplateFetcher | None = None,
    etf: TemplateFetcher | None = None,
    fixed_income: TemplateFetcher | None = None,
    equity: TemplateFetcher | None = None,
    fiagro: TemplateFetcher | None = None,
    fii_analysis_inputs: bool = True,
) -> BatchFetchers:
    """Os buscadores reais, salvo os injetados (só para teste, como o ``opener`` dos
    harvesters).

    A importação é feita aqui, a cada chamada, e não no topo: ``iip.cli`` importa este
    pacote, e assim um teste que troque ``iip.cli.fetch_template.fetch_*_live`` é
    respeitado. ``fii_analysis_inputs=False`` pede o template de FII sem os insumos
    que só o ``FIIAnalyzer`` lê (planilha da Pátria, CVM do ano anterior, tendência do
    VP) -- o valuation não os usa e assim gasta menos downloads e menos cota.
    """
    from iip.cli.fetch_template import (
        fetch_equity_template_live,
        fetch_etf_template_live,
        fetch_fiagro_template_live,
        fetch_fii_template_live,
        fetch_fixed_income_template_live,
    )

    default_fii = (
        fetch_fii_template_live
        if fii_analysis_inputs
        else functools.partial(fetch_fii_template_live, analysis_inputs=False)
    )
    return BatchFetchers(
        fii=fii or default_fii,
        etf=etf or fetch_etf_template_live,
        fixed_income=fixed_income or fetch_fixed_income_template_live,
        equity=equity or fetch_equity_template_live,
        fiagro=fiagro or fetch_fiagro_template_live,
    )


@dataclass(frozen=True)
class FetchPlan:
    """Os anos/mês e credenciais de uma rodada, como os buscadores os recebem."""

    ano: int  # ano de referência dos fundos (informes CVM)
    mes: int
    ano_dfp: int  # ano fiscal da DFP anual (ações)
    bolsai_api_key: str | None
    brapi_token: str | None
    # o valuation de FIAGRO também precisa do registro do bolsai (ver batch_value);
    # refresh e análise nunca passaram isso e continuam sem passar
    fiagro_uses_bolsai: bool = False

    @classmethod
    def for_run(
        cls,
        *,
        ano: int | None,
        mes: int | None,
        bolsai_api_key: str | None,
        brapi_token: str | None,
        today: _dt.date | None = None,
    ) -> FetchPlan:
        """Padrão do refresh e da análise: ``ano``/``mes`` explícitos, senão o corrente;
        a DFP de um ano fiscal só sai meses depois do fim dele, então o padrão é o ano
        anterior (mesmo comentário no ramo equity do ``fetch-template``)."""
        # data de calendário (referência CVM), não timestamp
        hoje = today or _dt.date.today()  # noqa: DTZ011
        return cls(
            ano=ano or hoje.year,
            mes=mes or hoje.month,
            ano_dfp=ano or (hoje.year - 1),
            bolsai_api_key=bolsai_api_key,
            brapi_token=brapi_token,
        )


def fetch_template_for(
    template_type: str,
    position,
    fetchers: BatchFetchers,
    plan: FetchPlan,
) -> tuple[dict, object]:
    """Busca o template de ``position`` com o buscador do seu tipo. Levanta
    ``ValueError`` para um tipo desconhecido (antes o último ``else`` de cada lote
    engolia qualquer coisa como renda fixa ou ação)."""
    ticker, cnpj = position.ticker, position.cnpj
    if template_type == "fii":
        return fetchers.fii(ticker, cnpj, plan.ano, plan.bolsai_api_key)
    if template_type == "etf":
        return fetchers.etf(ticker, cnpj, plan.ano, plan.mes, plan.brapi_token)
    if template_type == "equity":
        return fetchers.equity(
            ticker, cnpj, plan.ano_dfp, plan.bolsai_api_key, plan.brapi_token
        )
    if template_type == "fiagro":
        if plan.fiagro_uses_bolsai:
            return fetchers.fiagro(
                ticker,
                cnpj,
                plan.ano,
                plan.mes,
                plan.brapi_token,
                bolsai_api_key=plan.bolsai_api_key,
            )
        return fetchers.fiagro(ticker, cnpj, plan.ano, plan.mes, plan.brapi_token)
    if template_type == "fixed_income":
        return fetchers.fixed_income(ticker, cnpj, plan.ano, plan.mes)
    if template_type == "fi_infra":
        # só o FI-Infra listado chega aqui, então o símbolo é o ticker B3 do próprio
        # fundo e a busca de preço é segura (ao contrário da do AXIA3)
        return fetchers.fixed_income(
            ticker, cnpj, plan.ano, plan.mes, brapi_token=plan.brapi_token
        )
    raise ValueError(f"tipo de template desconhecido: {template_type!r}")
