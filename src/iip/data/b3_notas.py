"""Parser real de Notas de Corretagem (B3/CBLC) e agregador de posições.

Substitui o antigo ``B3Gateway.fetch_user_positions(cpf)`` -- que era
mock fixo, ignorava o CPF recebido e nunca fazia chamada de rede
nenhuma (achado real, 14/09/2026).

Por que não é uma chamada de API: a B3 não oferece uma API pública
simples para um app pessoal buscar posição de custódia de um
investidor via CPF/client_id -- o acesso programático real hoje passa
por (a) exportação manual de extrato pela Área do Investidor/corretora,
(b) Open Finance Brasil (exige registro como TPP no Banco Central,
OAuth2, certificação -- infraestrutura institucional, não um script
pessoal), ou (c) API proprietária de uma corretora específica (exige
parceria comercial). Dado isso, o desenho honesto é: o usuário exporta
a nota de corretagem real (PDF), este módulo parseia.

Achado estrutural real (confirmado com notas reais da Nu Investimentos,
14/09/2026): uma nota de corretagem mostra as OPERAÇÕES de um pregão
(compra/venda), não a posição consolidada atual. Chegar em "quanto eu
tenho de cada ativo hoje" exige agregar TODAS as notas desde a abertura
da posição -- não dá pra derivar isso de uma nota só. Por isso este
módulo tem duas funções separadas: parsear uma nota (``parse_...``) e
agregar várias notas já parseadas (``aggregate_positions``).

Achado real sobre o mercado FRACIONARIO: o ticker vem com sufixo "F"
(``CSUD3F``, ``FESA4F``) que precisa ser removido para virar o ticker
real (``CSUD3``, ``FESA4``) -- confirmado com dado real, não suposição.
Essa remoção só acontece quando ``tipo_mercado == "FRACIONARIO"``, nunca
de forma cega (nenhum ticker real da B3 termina em "F" legitimamente).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

_TRADE_LINE_RE = re.compile(
    r"""
    ^(?P<mercado>BOVESPA)\s+
    (?P<buy_sell>[CV])\s+
    (?P<tipo_mercado>VISTA|FRACIONARIO)\s+
    (?P<especificacao>.+?)\s+
    (?P<observacao>@|\#|\d|[A-Z])?\s*
    (?P<quantidade>\d+)\s+
    R\$\s*(?P<preco>[\d.,]+)\s+
    R\$\s*(?P<valor>[\d.,]+)\s+
    (?P<debito_credito>[DC])\s*$
    """,
    re.VERBOSE,
)

_TICKER_TOKEN_RE = re.compile(r"^([A-Z]{4}\d{1,2}F?)")


def _parse_brl(text: str) -> float:
    """Converte '1.385,50' (formato brasileiro) em 1385.50."""
    return float(text.replace(".", "").replace(",", "."))


@dataclass(frozen=True)
class TradeRecord:
    """Uma operação real extraída de uma linha de nota de corretagem --
    nunca uma posição, só o evento de compra/venda daquele pregão."""

    ticker: str
    buy_sell: str  # "C" ou "V"
    market_type: str  # "VISTA" ou "FRACIONARIO"
    quantity: float
    price: float
    value: float
    trade_date: date
    note_number: str


def parse_nota_corretagem_text(
    text: str, *, trade_date: date, note_number: str
) -> list[TradeRecord]:
    """Extrai as linhas de negociação (tabela 'Mercado C/V Tipo de
    Mercado...') do texto já extraído de uma nota de corretagem.

    Espera receber o texto plano já extraído do PDF (ex: via
    ``pdfplumber``) -- este módulo não abre PDF sozinho, só parseia
    texto. Linhas que não batem com o formato esperado são ignoradas
    silenciosamente (cabeçalhos, rodapés, texto de contato) -- não é
    erro, é o esperado numa nota real cheia de texto ao redor da
    tabela.
    """
    trades: list[TradeRecord] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = _TRADE_LINE_RE.match(line)
        if not match:
            continue

        especificacao = match.group("especificacao")
        tipo_mercado = match.group("tipo_mercado")

        ticker_match = _TICKER_TOKEN_RE.match(especificacao)
        if not ticker_match:
            continue
        raw_ticker = ticker_match.group(1)

        ticker = raw_ticker
        if tipo_mercado == "FRACIONARIO" and raw_ticker.endswith("F"):
            ticker = raw_ticker[:-1]

        trades.append(
            TradeRecord(
                ticker=ticker,
                buy_sell=match.group("buy_sell"),
                market_type=tipo_mercado,
                quantity=float(match.group("quantidade")),
                price=_parse_brl(match.group("preco")),
                value=_parse_brl(match.group("valor")),
                trade_date=trade_date,
                note_number=note_number,
            )
        )

    return trades


@dataclass(frozen=True)
class AggregatedPosition:
    """Posição real, derivada só de ``TradeRecord`` -- nunca fabricada.
    ``asset_class`` não é preenchido aqui: quem chama deve cruzar
    ``ticker`` com o registro real (``PORTFOLIO_ASSETS``) para obter a
    classe -- este módulo não adivinha classe de ativo a partir do
    código do ticker."""

    ticker: str
    quantity: float
    average_price: float
    total_cost: float


@dataclass(frozen=True)
class AggregationResult:
    positions: tuple[AggregatedPosition, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)


def aggregate_positions(trades: list[TradeRecord]) -> AggregationResult:
    """Agrega uma lista de ``TradeRecord`` (de uma ou várias notas, já
    em ordem cronológica ou não -- esta função ordena por
    ``trade_date`` antes de processar) em posições consolidadas por
    ticker, usando a regra padrão de preço médio: compra recalcula a
    média ponderada; venda reduz a quantidade sem alterar o preço
    médio das cotas/ações restantes.

    Se o histórico de notas fornecido não cobrir a abertura real da
    posição (ex: uma venda aparece sem compra suficiente registrada
    antes), a quantidade líquida pode ficar negativa -- isso é um
    sinal real de histórico incompleto, não um bug de cálculo. A
    função NUNCA esconde isso: registra um aviso explícito em vez de
    silenciosamente "corrigir" ou descartar a posição.
    """
    ordered = sorted(trades, key=lambda t: (t.trade_date, t.note_number))

    running: dict[str, tuple[float, float]] = {}  # ticker -> (qty, avg_price)
    warnings: list[str] = []

    for trade in ordered:
        qty, avg = running.get(trade.ticker, (0.0, 0.0))

        if trade.buy_sell == "C":
            new_qty = qty + trade.quantity
            new_avg = (
                (qty * avg + trade.quantity * trade.price) / new_qty
                if new_qty
                else 0.0
            )
            running[trade.ticker] = (new_qty, new_avg)
        else:  # "V" -- venda
            new_qty = qty - trade.quantity
            if new_qty < 0:
                warnings.append(
                    f"{trade.ticker}: venda de {trade.quantity} em "
                    f"{trade.trade_date.isoformat()} (nota {trade.note_number}) "
                    f"excede a quantidade conhecida ({qty}) -- histórico de "
                    "notas provavelmente incompleto, quantidade líquida abaixo "
                    "não é confiável para este ticker."
                )
            # Venda nao muda o preco medio das cotas restantes.
            running[trade.ticker] = (new_qty, avg)

    positions = tuple(
        AggregatedPosition(
            ticker=ticker,
            quantity=qty,
            average_price=avg,
            total_cost=round(qty * avg, 2),
        )
        for ticker, (qty, avg) in sorted(running.items())
        if qty != 0
    )

    return AggregationResult(positions=positions, warnings=tuple(warnings))


# ---------------------------------------------------------------------------
# Formato legado "NOTA DE CORRETAGEM" (notas de 2024, layout diferente do
# formato "BOVESPA ... @ ..." de 2026 -- achado real, 14/09/2026, mesma
# sessão). Colunas: Q | Negociação (ex: "B3 RV LISTADO") | C/V | Tipo
# mercado | Prazo | Especificação do título | Obs.(*) | Quantidade |
# Preço/Ajuste | Valor Operação/Ajuste | D/C. Sem "R$" na frente dos
# valores, ao contrário do formato novo.
#
# Achado real: nesse formato o título vem como nome por extenso (ex:
# "FII BTLG CI ER", "FIC IE CAP CI"), NUNCA com o código de negociação
# direto -- diferente do formato novo, que já traz o ticker
# ("BTLG11 CI"). Não há como derivar o ticker automaticamente do nome;
# o mapeamento abaixo foi confirmado explicitamente pelo usuário
# (14/09/2026), não adivinhado.
# ---------------------------------------------------------------------------

LEGACY_TITLE_TO_TICKER: dict[str, str] = {
    "FII BTLG CI ER": "BTLG11",
    "FII BTLG CI": "BTLG11",
    "FII CSHGPRIM CI": "HGPO11",
    "FII HEDGEBS CI": "HGBS11",
    "FIC IE CAP CI": "CPTI11",
    "FIC FI BCNA CI": "BODB11",
}

_LEGACY_TRADE_LINE_RE = re.compile(
    r"""
    ^B3\s+R[VF]\s+LISTADO\s+
    (?P<buy_sell>[CV])\s+
    (?P<tipo_mercado>VISTA)\s+
    (?P<titulo>.+?)\s+
    (?:\#|@)?\s*
    (?P<quantidade>\d+)\s+
    (?P<preco>[\d.,]+)\s+
    (?P<valor>[\d.,]+)\s+
    (?P<debito_credito>[DC])\s*$
    """,
    re.VERBOSE,
)


def parse_legacy_nota_corretagem_text(
    text: str, *, trade_date: date, note_number: str
) -> tuple[list[TradeRecord], list[str]]:
    """Parseia o formato antigo de nota ("NOTA DE CORRETAGEM", notas de
    2024). Retorna ``(trades, avisos)`` -- ``avisos`` lista qualquer
    título encontrado que não está em ``LEGACY_TITLE_TO_TICKER``. Um
    título desconhecido NUNCA vira um ticker adivinhado nem é
    descartado silenciosamente: fica de fora de ``trades`` e aparece
    em ``avisos`` para revisão humana.
    """
    trades: list[TradeRecord] = []
    warnings: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = _LEGACY_TRADE_LINE_RE.match(line)
        if not match:
            continue

        titulo = match.group("titulo").strip()
        ticker = LEGACY_TITLE_TO_TICKER.get(titulo)

        if ticker is None:
            warnings.append(
                f"título '{titulo}' (nota {note_number}, {trade_date.isoformat()}) "
                "não está em LEGACY_TITLE_TO_TICKER -- ticker desconhecido, "
                "operação NÃO incluída na agregação. Confirme o ticker real "
                "e adicione ao mapeamento."
            )
            continue

        trades.append(
            TradeRecord(
                ticker=ticker,
                buy_sell=match.group("buy_sell"),
                market_type=match.group("tipo_mercado"),
                quantity=float(match.group("quantidade")),
                price=_parse_brl(match.group("preco")),
                value=_parse_brl(match.group("valor")),
                trade_date=trade_date,
                note_number=note_number,
            )
        )

    return trades, warnings
