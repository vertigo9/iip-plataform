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

Rentabilidade (``/api/produtos/rentabilidade/{ticker}``, também conferida ao vivo): uma
tabela oficial por período (``ultimoAno``, ``lancamento``... com ``etf``, ``indice``,
``benchmark`` = CDI e ``ibov``, em texto como ``"14,03%"``) e uma série diária
(``grafico``: ``etf``, ``indice``, ``benchmark``, ``ibov``, todos rebaseados a 100 em
31/10/2024). Dela saem dois números do ``ETFAnalyzer`` que ficavam no valor-padrão:

  - ``tracking_error_pct``: desvio-padrão da diferença de retorno ETF - índice,
    anualizado. Depende da frequência, e isto é uma propriedade do dado, não do método:
    o NAV é marcado de forma mais suave que o índice (há dias de +0,06% no NAV contra
    -0,29% no índice) e a diferença REVERTE, então o erro diário superestima o que quem
    segura o fundo enfrenta, e o mensal tem observações de menos numa janela de um ano.
    Nas últimas 52 semanas (set/2026): diário 0,91% (252 observações), semanal 0,51% (52
    janelas de 5 pregões) e mensal 0,44% (só 12 janelas). Usa-se o SEMANAL, o ponto
    intermediário com amostra suficiente, e a escolha é declarada no aviso. Foi
    verificado que não há defasagem de um dia entre as séries: com a história inteira a
    correlação é máxima e o erro mínimo com as datas alinhadas (0,81% diário).
  - ``tracking_difference_pct``: ETF - índice no último ano, da tabela oficial
    (+0,35 p.p.; desde o lançamento é -0,23 p.p.).

Também da ficha, ``expense_ratio_pct`` (``taxaAdm``: 0,19% a.a., de administração e
gestão; a taxa global do regulamento pode ser maior). E, do histórico, o fluxo líquido
do ano (``net_inflows_ytd_millions``): cotas em circulação = PL / cota patrimonial,
ambos oficiais, e o fluxo é a variação de cotas x a cota patrimonial. É uma estimativa
derivada, declarada como tal.

NÃO usado daqui: a composição com pesos ("Principais ativos") é HTML estático, cobre 12
dos 17 ativos e não tem data, então não se sabe a que dia se refere; e a cesta de
integralização (XLSX) traz quantidades por lote de criação, não pesos. A composição vem da
CDA da CVM, que é datada e completa: ver ``iip.sources.cvm_cda_etf``.

Só entra em ``VERIFIED_TICKERS`` o ETF cujos endpoints foram lidos ao vivo: a API aceita
qualquer código, mas só se confia no que foi visto.
"""

from __future__ import annotations

import math
import re
import statistics
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


def returns_url(ticker: str) -> str:
    return f"{API_BASE}/produtos/rentabilidade/{ticker.strip().upper()}"


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


# ---------------------------------------------------------------- rentabilidade

TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class InvestoReturnPoint:
    date: date
    etf: float  # nível rebaseado (100 no início), cota patrimonial
    index: float  # nível rebaseado do índice de referência


@dataclass(frozen=True)
class InvestoReturns:
    ticker: str
    # período -> {"etf", "indice", "benchmark", "ibov"}, em % (ex.: 14.03)
    table: dict[str, dict[str, float]]
    series: tuple[InvestoReturnPoint, ...]
    benchmark_name: str | None


def parse_percent(raw: object) -> float | None:
    """``"14,03%"`` -> ``14.03``; ``"-0,23%"`` -> ``-0.23``; ``None`` se não for um valor."""
    if not isinstance(raw, str):
        return None
    match = re.fullmatch(r"\s*(-?\d+(?:,\d+)?)\s*%\s*", raw)
    return float(match.group(1).replace(",", ".")) if match else None


def parse_fee_pct(raw: object) -> float | None:
    """``"0,19% a.a."`` -> ``0.19``."""
    if not isinstance(raw, str):
        return None
    match = re.search(r"(\d+(?:,\d+)?)\s*%", raw)
    return float(match.group(1).replace(",", ".")) if match else None


def parse_returns(payload: object) -> InvestoReturns | None:
    """``None`` se a resposta não tem uma tabela e uma série utilizáveis. Uma linha da
    série sem data ISO ou com nível não positivo é descartada."""
    if not isinstance(payload, dict):
        return None
    raw_table, raw_series = payload.get("tabela"), payload.get("grafico")
    if not isinstance(raw_table, dict) or not isinstance(raw_series, list):
        return None
    table: dict[str, dict[str, float]] = {}
    for period, row in raw_table.items():
        if not isinstance(row, dict):
            continue  # ex.: "meses", que é uma tabela dentro da tabela
        values = {k: parse_percent(v) for k, v in row.items()}
        table[period] = {k: v for k, v in values.items() if v is not None}
    points: dict[date, InvestoReturnPoint] = {}
    for row in raw_series:
        if not isinstance(row, dict):
            continue
        try:
            day = date.fromisoformat(str(row.get("data")))
        except ValueError:
            continue
        etf, index = row.get("etf"), row.get("indice")
        if not all(isinstance(v, (int, float)) and v > 0 for v in (etf, index)):
            continue
        points[day] = InvestoReturnPoint(day, float(etf), float(index))
    if not table or len(points) < 2:
        return None
    ticker = payload.get("sigla")
    return InvestoReturns(
        ticker=ticker.strip().upper() if isinstance(ticker, str) else "",
        table=table,
        series=tuple(points[d] for d in sorted(points)),
        benchmark_name=payload.get("benchmark") or None,
    )


def tracking_error_pct(
    series: tuple[InvestoReturnPoint, ...],
    *,
    window: int = 5,
    windows: int = 52,
    min_windows: int = 26,
) -> float | None:
    """Tracking error anualizado (em %): desvio-padrão da diferença de retorno ETF -
    índice em janelas de ``window`` observações sem sobreposição, as ``windows`` mais
    recentes, x raiz de (252 / window). ``None`` com menos de ``min_windows`` janelas
    (um ETF novo demais): nunca se estima com pouca amostra."""
    diffs = []
    last = len(series) - 1
    for k in range(windows):
        end = last - k * window
        start = end - window
        if start < 0:
            break
        etf = series[end].etf / series[start].etf - 1.0
        index = series[end].index / series[start].index - 1.0
        diffs.append(etf - index)
    if len(diffs) < max(min_windows, 2):
        return None
    return round(
        statistics.stdev(diffs) * math.sqrt(TRADING_DAYS_PER_YEAR / window) * 100.0, 4
    )


def tracking_difference_pct(
    table: dict[str, dict[str, float]], period: str = "ultimoAno"
) -> float | None:
    """Retorno do ETF menos o do índice no período, em pontos percentuais, da tabela
    oficial (positivo: o ETF ficou à frente do índice)."""
    row = table.get(period, {})
    if "etf" not in row or "indice" not in row:
        return None
    return round(row["etf"] - row["indice"], 2)


def net_inflows_ytd_millions(
    points: tuple[InvestoNavPoint, ...], year: int
) -> float | None:
    """Fluxo líquido estimado do ano, em milhões de R$: cotas em circulação = PL / cota
    patrimonial, e o fluxo é a variação de cotas x a cota patrimonial do dia. ``None``
    se o ano não tem pelo menos dois dias com PL e cota."""
    flow = 0.0
    pairs = 0
    previous: float | None = None
    for point in points:
        if point.net_assets is None:
            previous = None
            continue
        shares = point.net_assets / point.nav_per_share
        if previous is not None and point.date.year == year:
            flow += (shares - previous) * point.nav_per_share
            pairs += 1
        previous = shares
    return round(flow / 1_000_000.0, 2) if pairs >= 1 else None
