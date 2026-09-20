"""Distribuição por cota declarada pela gestora no relatório mais recente do fundo.

Serve à validação cruzada da renda projetada (``iip.portfolio.income_cross_check``): a série
da CVM é a fonte do cálculo, e aqui está o número que a PRÓPRIA gestora escreve, lido do
mesmo PDF que ``iip.sources.fii_vacancia`` já baixa para a ocupação. Cada layout é diferente,
então há um leitor por fundo, conferido em 20/09/2026 contra o texto real do relatório mais
recente (as frases abaixo são as reais):

  - XPML11 (XP Asset): "No dia 18/08/2026 o Fundo divulgou a distribuição de R$ 0,92¹ por
    cota" (e "Nos últimos 28 meses, o XP Malls distribuiu consistentemente R$ 0,92");
  - TRXF11 (TRX, em inglês, ponto decimal): "TRXF11 announced a monthly distribution of BRL
    0.93 per share";
  - KNRI11 (Kinea, carta do gestor): "R$ 1,10/cota" seguido de "DISTRIBUIÇÃO MENSAL EM
    15/09/2026";
  - BTLG11 (BTG): "RENDIMENTO MENSAL" e, na linha seguinte, "R$ 0,81 por cota";
  - HGBS11 (Hedge): "anunciou a distribuição de R$ 0,170 / cota";
  - RBVA11 (Rio Bravo): "a distribuição, de R$0,09/cota";
  - ALZR11 (Alianza): "Resultado Distribuído de R$ 0,0840/cota";
  - HSML11 (HSI): a linha "Rendimento/Cota4 0,75 1,50 5,81", cuja primeira coluna é o mês.

O que NÃO está aqui: HGRU11, LVBI11 e PVBI11 (a planilha da Pátria de tijolo não traz o
rendimento; o relatório gerencial deles não tem leitor), MANA11, AFHI11, BTCI11 e VGIP11. Para
HGCR11 e PCIP11 o número vem da planilha da Pátria (``rendimento_cota``), lida em outro ponto.

Um leitor devolve ``None`` quando o texto não bate com o layout esperado; nunca um número
adivinhado.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class DeclaredDistribution:
    ticker: str
    per_quota: float
    source_url: str
    # a frase ou o rótulo de onde o número saiu, para conferência visual
    evidence: str
    # AAAA-MM a que o número se refere, quando a fonte diz (a planilha da Pátria diz; os
    # PDFs em geral não trazem o mês de forma legível): sem ele compara-se com o último mês
    competencia: str | None = None


def _number(raw: str, *, decimal_comma: bool = True) -> float | None:
    text = raw.strip()
    if decimal_comma:
        text = text.replace(".", "").replace(",", ".")
    try:
        value = float(text)
    except ValueError:
        return None
    return value if value > 0 else None


def _first(pattern: str, text: str, *, flags: int = re.IGNORECASE) -> re.Match | None:
    return re.search(pattern, text, flags)


def parse_xp(text: str) -> tuple[float, str] | None:
    match = _first(r"divulgou a distribuição de R\$ ?([\d.,]+)\S? por cota", text)
    value = _number(match.group(1)) if match else None
    return (value, match.group(0)) if match and value else None


def parse_trx(text: str) -> tuple[float, str] | None:
    match = _first(r"monthly distribution of BRL ([\d.]+) per share", text)
    value = _number(match.group(1), decimal_comma=False) if match else None
    return (value, match.group(0)) if match and value else None


def parse_knri(text: str) -> tuple[float, str] | None:
    match = _first(
        r"R\$ ?([\d.,]+)/cota\s*\n\s*DISTRIBUIÇÃO MENSAL EM (\d{2}/\d{2}/\d{4})", text
    )
    value = _number(match.group(1)) if match else None
    return (value, match.group(0).replace("\n", " ")) if match and value else None


def parse_btg(text: str) -> tuple[float, str] | None:
    match = _first(r"RENDIMENTO MENSAL\s*\n\s*R\$ ?([\d.,]+) por cota", text)
    value = _number(match.group(1)) if match else None
    return (value, match.group(0).replace("\n", " ")) if match and value else None


def parse_hedge(text: str) -> tuple[float, str] | None:
    match = _first(r"anunciou a distribuição de R\$ ?([\d.,]+) ?/ ?cota", text)
    value = _number(match.group(1)) if match else None
    return (value, match.group(0)) if match and value else None


def parse_rbva(text: str) -> tuple[float, str] | None:
    match = _first(r"distribuição, de R\$ ?([\d.,]+)/cota", text)
    value = _number(match.group(1)) if match else None
    return (value, match.group(0)) if match and value else None


def parse_alzr(text: str) -> tuple[float, str] | None:
    match = _first(r"Resultado Distribuído de R\$ ?([\d.,]+)/cota", text)
    value = _number(match.group(1)) if match else None
    return (value, match.group(0)) if match and value else None


def parse_hsi(text: str) -> tuple[float, str] | None:
    # "Rendimento/Cota4 0,75 1,50 5,81": a primeira coluna é o mês (a segunda dobra e a
    # terceira acumula o ano: 1,50 = 2 x 0,75; 5,81 / 8 meses = 0,73)
    match = _first(r"Rendimento/Cota\d? ([\d.,]+) [\d.,]+ [\d.,]+", text)
    value = _number(match.group(1)) if match else None
    return (value, match.group(0)) if match and value else None


PARSERS: dict[str, Callable[[str], tuple[float, str] | None]] = {
    "XPML11": parse_xp,
    "TRXF11": parse_trx,
    "KNRI11": parse_knri,
    "BTLG11": parse_btg,
    "HGBS11": parse_hedge,
    "RBVA11": parse_rbva,
    "ALZR11": parse_alzr,
    "HSML11": parse_hsi,
}


def supports(ticker: str) -> bool:
    return ticker.strip().upper() in PARSERS


def read_declared(
    ticker: str, text: str, source_url: str
) -> DeclaredDistribution | None:
    """A distribuição por cota que o texto do relatório declara, ou ``None`` se o layout
    não casa (ou o fundo não tem leitor)."""
    parser = PARSERS.get(ticker.strip().upper())
    if parser is None:
        return None
    found = parser(text)
    if found is None:
        return None
    value, evidence = found
    return DeclaredDistribution(ticker.strip().upper(), value, source_url, evidence)
