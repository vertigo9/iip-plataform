"""Dados do próprio Investo (gestora) para os ETFs dela: cota patrimonial diária,
patrimônio líquido e a ficha do produto.

Criado em 19/09/2026 para o LFTB11 (ETF Investo, MarketVector Brazil Treasury 760 Day),
que ficara sem valuation por falta de fonte de NAV: não está no Informe Diário da CVM
(consta no cadastro como FIIM) e o bolsai não serve ETF de renda fixa. A fonte é a página
oficial do fundo, https://www.investoetf.com/etf/lftb11/, cujo JavaScript
(``etfsv2.js``) preenche a tela lendo três endpoints públicos, sem login, que foram
conferidos ao vivo:

  - ``/api/produtos/historico/{ticker}``: lista de ``{"Data": "2026-09-17",
    "Cota Patrimonial (R$)": "R$ 126,66", "Patrimônio Líquido (R$)":
    "R$ 5.853.536.873,51", "Valor Índice (R$)": "R$ 2.768,63"}``, um por dia útil desde o
    início (31/10/2024, cota 100,00). Para o LFTB11: 467 pontos sem lacuna maior que
    5 dias e sem queda diária acima de 1%. A alta de 26,66% desde o lançamento e o PL de
    17/09 (R$ 5.853.536.873,51) batem com o que a página mostra.
  - ``/api/produtos/{ticker}``: a ficha (``cnpj``, ``codigoIsin``, ``taxaAdm``,
    ``dataInicio``, ``ativos``, ``aum``...). O CNPJ do LFTB11 (56.176.507/0001-55) é o do
    registro da carteira, e o harvester o confere: cota de outro fundo nunca entra.
  - ``/api/precos/{ticker}``: preços de compra/venda/"estimado" da cota. NÃO é usado: o
    preço de mercado continua vindo do brapi, como nos demais ETFs.

A cota patrimonial é D-1 (o último ponto é do pregão anterior), como o Informe Diário da
CVM que alimenta os outros fundos, e o preço de mercado é mais novo que ela; por isso o
prêmio/desconto sobre o NAV carrega essa defasagem, e o chamador o avisa. Um NAV com mais
de ``MAX_NAV_AGE_DAYS`` dias de idade é tratado como indisponível, nunca usado velho.

Só entra em ``VERIFIED_TICKERS`` o ETF cujos endpoints foram lidos ao vivo: a API aceita
qualquer código, mas só se confia no que foi visto.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

API_BASE = "https://api.investoetf.com.br/api"

# ETFs cujos endpoints foram lidos ao vivo (ver o docstring do módulo)
VERIFIED_TICKERS = frozenset({"LFTB11"})

# um NAV mais velho que isto (dias corridos) não é usado: cobre um fim de semana e um
# feriado prolongado, mas não uma fonte parada
MAX_NAV_AGE_DAYS = 7

_KEY_DATE = "Data"
_KEY_NAV = "Cota Patrimonial (R$)"
_KEY_NET_ASSETS = "Patrimônio Líquido (R$)"
_KEY_INDEX = "Valor Índice (R$)"


class InvestoEtfError(RuntimeError):
    """A fonte respondeu, mas não com o que se espera de um ETF verificado."""


@dataclass(frozen=True)
class InvestoNavPoint:
    date: date
    nav_per_share: float
    net_assets: float | None
    index_value: float | None


@dataclass(frozen=True)
class InvestoProduct:
    ticker: str
    cnpj: str
    isin: str | None
    administration_fee: str | None
    start_date: str | None


def supports(ticker: str) -> bool:
    return ticker.strip().upper() in VERIFIED_TICKERS


def history_url(ticker: str) -> str:
    return f"{API_BASE}/produtos/historico/{ticker.strip().upper()}"


def product_url(ticker: str) -> str:
    return f"{API_BASE}/produtos/{ticker.strip().upper()}"


def parse_brl(raw: object) -> float | None:
    """``"R$ 5.853.536.873,51"`` -> ``5853536873.51``; ``None`` se não for um valor."""
    if not isinstance(raw, str):
        return None
    cleaned = raw.replace("R$", "").replace("\xa0", " ").strip()
    if not re.fullmatch(r"-?\d{1,3}(?:\.\d{3})*(?:,\d+)?|-?\d+(?:,\d+)?", cleaned):
        return None
    return float(cleaned.replace(".", "").replace(",", "."))


def parse_history(payload: object) -> tuple[InvestoNavPoint, ...]:
    """Os pontos válidos, do mais antigo ao mais novo. Uma linha sem data ISO ou sem
    cota positiva é descartada (não vira zero); um payload que não é uma lista de
    objetos dá uma tupla vazia."""
    if not isinstance(payload, list):
        return ()
    points: dict[date, InvestoNavPoint] = {}
    for row in payload:
        if not isinstance(row, dict):
            continue
        try:
            day = date.fromisoformat(str(row.get(_KEY_DATE)))
        except ValueError:
            continue
        nav = parse_brl(row.get(_KEY_NAV))
        if nav is None or nav <= 0:
            continue
        points[day] = InvestoNavPoint(
            date=day,
            nav_per_share=nav,
            net_assets=parse_brl(row.get(_KEY_NET_ASSETS)),
            index_value=parse_brl(row.get(_KEY_INDEX)),
        )
    return tuple(points[d] for d in sorted(points))


def parse_product(payload: object) -> InvestoProduct | None:
    if not isinstance(payload, dict):
        return None
    ticker, cnpj = payload.get("nome"), payload.get("cnpj")
    if not isinstance(ticker, str) or not isinstance(cnpj, str) or not cnpj.strip():
        return None
    return InvestoProduct(
        ticker=ticker.strip().upper(),
        cnpj=cnpj.strip(),
        isin=payload.get("codigoIsin") or None,
        administration_fee=payload.get("taxaAdm") or None,
        start_date=payload.get("dataInicio") or None,
    )


def same_cnpj(a: str, b: str) -> bool:
    digits = lambda s: "".join(ch for ch in s if ch.isdigit())  # noqa: E731
    return bool(digits(a)) and digits(a) == digits(b)
