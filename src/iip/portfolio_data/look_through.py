"""Valuation por transparência (look-through) de um fundo que só carrega ações.

Serve ao FMP-FGTS Daycoval Eletrobras (registro AXIA3): um fundo aberto, acessado só pelo
FGTS, sem ticker nem preço de mercado, então não há um preço com que comparar o NAV. Mas a
CDA da CVM (``iip.sources.cvm_cda``) diz o que ele tem: em 31/08/2026, 99,8% do patrimônio
em ações da Axia Energia (a antiga Eletrobras, renomeada em nov/2025; AXIA3 ON e AXIA7 PN),
pelas quais a cota é marcada todo dia. Então o que dá para avaliar é o que o fundo carrega:

    cota justa = NAV x (1 + soma, sobre as ações subjacentes, de peso x margem de segurança)

  - o PESO de cada empresa é o valor de mercado da posição sobre o patrimônio líquido, na
    data da CDA (as classes ON e PN da mesma empresa somam);
  - a MARGEM de segurança de cada empresa vem do catálogo de ações que o projeto já tem
    (Graham, Bazin...), aplicado à ação no mesmo caminho do ``value-portfolio`` (DFP da
    CVM e bolsai), sobre a ação ON (AXIA3): a ordinária e a preferencial cotam quase iguais
    (R$ 53,12 e R$ 53,14 implícitos na CDA de agosto), então a margem da ON vale para as
    duas. É uma simplificação declarada;
  - o resto do patrimônio (títulos públicos, caixa, valores a pagar: 0,2% aqui) fica ao NAV,
    ou seja, margem zero;
  - o "preço" com que se compara é o próprio NAV, porque a cota não tem preço de mercado e
    só se sai dela ao valor patrimonial.

Portões, para não afirmar o que não se sabe: só se avalia se pelo menos
``LOOK_THROUGH_MIN_COVERAGE`` do patrimônio (90%, o mínimo que o regulamento exige em
ações) está em ações cuja margem foi de fato calculada; uma ação sem empresa mapeada em
``UNDERLYINGS`` não entra (e baixa a cobertura). O peso é o do FIM do mês da CDA (~3
semanas atrás): é proporção aproximada, não a posição de hoje.

O que isto NÃO diz: que a cota "vale" o valor justo. É a margem de segurança da empresa
subjacente (a mesma que o ``value-portfolio`` mostra para uma ação), traduzida para a cota.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from iip.sources.cvm_cda import CdaPortfolio


@dataclass(frozen=True)
class Underlying:
    issuer_code: str  # as 4 letras de emissor do ticker B3 (AXIA3, AXIA7 -> "AXIA")
    ticker: str  # a ação usada para avaliar a empresa (a ON)
    company_cnpj: str  # CNPJ da COMPANHIA (a DFP é dela), não o do fundo
    sector: str
    industry: str


# Só entra a empresa cujo mapeamento foi conferido. Axia Energia: CNPJ 00.001.180/0001-26
# (o mesmo da Eletrobras, que só mudou de nome); setor como o das outras elétricas da
# carteira, o que faz o Bazin liderar se houver dividendos.
UNDERLYINGS: dict[str, Underlying] = {
    "AXIA": Underlying(
        issuer_code="AXIA",
        ticker="AXIA3",
        company_cnpj="00.001.180/0001-26",
        sector="Utilidade Pública",
        industry="Energia Elétrica",
    ),
}


def issuer_code(ticker: str) -> str:
    """As 4 letras iniciais de um ticker B3 (``"AXIA7"`` -> ``"AXIA"``); ``""`` se não
    começa com 4 letras."""
    match = re.match(r"[A-Z]{4}", ticker.strip().upper())
    return match.group(0) if match else ""


def equity_weights(portfolio: CdaPortfolio) -> tuple[dict[str, float], float]:
    """(peso por empresa mapeada, peso das ações sem empresa mapeada), como fração do
    patrimônio líquido. Posição de valor zero é ignorada."""
    mapped: dict[str, float] = {}
    unmapped = 0.0
    for equity in portfolio.equities:
        if equity.market_value <= 0:
            continue
        weight = equity.market_value / portfolio.net_assets
        code = issuer_code(equity.ticker)
        if code in UNDERLYINGS:
            mapped[code] = mapped.get(code, 0.0) + weight
        else:
            unmapped += weight
    return mapped, unmapped


def combine_margin(
    weights: dict[str, float], margins: dict[str, float | None]
) -> tuple[float | None, float]:
    """(margem ponderada, cobertura): a soma de peso x margem e a soma dos pesos das
    empresas cuja margem foi calculada. Uma empresa sem margem NÃO entra na cobertura,
    então baixa a confiança em vez de virar um zero. ``(None, 0.0)`` se nenhuma tem."""
    covered = 0.0
    weighted = 0.0
    for code, weight in weights.items():
        margin = margins.get(code)
        if margin is None:
            continue
        covered += weight
        weighted += weight * margin
    if covered <= 0:
        return None, 0.0
    return weighted, covered
