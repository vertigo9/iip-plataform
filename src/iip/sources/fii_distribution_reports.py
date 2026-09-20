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
    # a data do relatório e/ou da distribuição, como se consegue ler dele (frase ou nome do
    # arquivo); ``None`` quando não dá para saber
    reference: str | None = None


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
    # a frase inteira, com a data da divulgação e a do pagamento, vira a evidência
    match = _first(
        r"(?:No dia \d{2}/\d{2}/\d{4} )?o Fundo divulgou a distribuição de "
        r"R\$ ?([\d.,]+)\S? por cota(?:, com pagamento em \d{2}/\d{2}/\d{2,4})?",
        text,
    )
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


_MONTHS_EN = {
    "january": "01", "february": "02", "march": "03", "april": "04", "may": "05",
    "june": "06", "july": "07", "august": "08", "september": "09", "october": "10",
    "november": "11", "december": "12",
}  # fmt: skip


_MONTHS_PT = {
    "jan": "01", "fev": "02", "mar": "03", "abr": "04", "mai": "05", "jun": "06",
    "jul": "07", "ago": "08", "set": "09", "out": "10", "nov": "11", "dez": "12",
}  # fmt: skip


def reference_hint(evidence: str, source_url: str) -> str | None:
    """Data do relatório ou da distribuição, do que a fonte deixa ver: as datas escritas na
    própria frase (divulgação, pagamento) e o mês que o nome do arquivo indica."""
    parts: list[str] = []
    dates = re.findall(r"\b(\d{2}/\d{2}/\d{2,4})\b", evidence)
    if dates:
        parts.append("na frase: " + ", ".join(dates))
    name = source_url.rsplit("/", 1)[-1]
    period = None
    if match := re.search(r"REL(\d{2})(\d{2})(\d{4})", name):
        period = f"{match.group(3)}-{match.group(2)}"  # REL31082026 = 31/08/2026
    elif match := re.search(r"(\d{4})[-_](\d{2})", name):
        period = f"{match.group(1)}-{match.group(2)}"
    elif match := re.search(r"(\d{2})-(\d{4})", name):
        period = f"{match.group(2)}-{match.group(1)}"
    elif match := re.search(
        r"[._-](jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\.?(\d{2})(?!\d)",
        name,
        re.IGNORECASE,
    ):
        month = _MONTHS_PT[match.group(1).lower()]
        period = f"20{match.group(2)}-{month}"  # xp_malls_fii_ago.26 = agosto de 2026
    elif match := re.search(r"([A-Za-z]+)-(\d{4})", name):
        month = _MONTHS_EN.get(match.group(1).lower())
        period = f"{match.group(2)}-{month}" if month else None
    if period:
        parts.append(f"relatório de {period}")
    return "; ".join(parts) or None


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
    return DeclaredDistribution(
        ticker.strip().upper(),
        value,
        source_url,
        evidence,
        reference=reference_hint(evidence, source_url),
    )
