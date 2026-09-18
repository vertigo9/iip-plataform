"""Pátria/CSHG "Planilha de Fundamentos" — a real, structured XLSX
distributed monthly through the same MZIQ document catalog as every
other Pátria document (see ``iip.sources.patria_mziq``), under a
per-fund category whose internal_name varies by fund (e.g.
``"lvbi11_planilha_de_fundamentos"``, ``"hgru - planilha de
fundamentos"``) but always contains the substring "planilha" +
"fundamentos" (case/accent-insensitive) -- see
``iip.sources.patria_mziq.PATRIA_MZIQ_FUNDS`` for exact category
lists.

Built to close the item-6 gap ("structured extraction of collected
documents") from ``IIP_reconciliacao_blueprint_vs_codigo.md`` -- the
FIRST concrete instance of extracting REAL structured data out of a
document this project already collects, beyond the NAV/DFP zip/CSV
channels. Unlike ``sparta_reports.py`` (PDF text-layout parsing, very
fragile), this reads real Excel cells via ``openpyxl`` -- far more
reliable, but with its own real gotcha (see unit handling below).

CONFIRMED LIVE (18/09/2026) against 5 real downloaded files: the
"Resumo" sheet's LAYOUT (row-by-row label/value pairs: label cells in
one row, the corresponding value one row directly below, same column)
is IDENTICAL across HGRU11, LVBI11 and PVBI11 -- all three are
"tijolo" (physical real-estate) FIIs with occupancy/lease-related
indicators (WALE, Vacância Física/Financeira, ABL, nº de locatários).
The exact COLUMN LETTERS shift between funds (LVBI11/PVBI11 start at
column C, HGRU11 starts at column B) -- this module locates cells by
scanning for the label TEXT, never by a fixed coordinate, same
discipline as every other "don't assume position" parser in this
project.

HGCR11 and PCIP11 (also Pátria, also named "Planilha de Fundamentos")
are CONFIRMED NOT to use this layout -- both are credit/recebíveis
funds (CRI), and their "Resumo" sheet is a completely different
template (yield curve sensitivity table, % PL by asset class -- no
WALE, no vacância, no locatários at all, since those concepts don't
apply to a credit fund). ``parse_resumo_tijolo`` returns ``None`` for
these rather than guessing at a wrong shape -- a genuinely different
extractor would be needed for the credit-fund template, not attempted
here.

REAL UNIT GOTCHA (confirmed live, would have been a silent 1000x
error): "Patrimônio líquido" and "Valor de Mercado" are unitless raw
numbers in the cell VALUE -- the actual unit ("R$ ... milhões" vs.
"R$ ... bilhões") is only encoded in the cell's Excel NUMBER FORMAT
string, and it genuinely differs between funds of similar real size
(LVBI11's PL cell is formatted in milhões, PVBI11's in bilhões, for
funds of a comparable real magnitude) -- reading the raw value alone
without checking ``number_format`` would have misrepresented one of
them by 1000x. This module always normalizes both to raw BRL.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date

_REQUIRED_LABELS = (
    "patrimonio liquido",
    "valor de mercado",
    "wale",
    "vacancia fisica",
    "vacancia financeira",
)

_N_ATIVOS_LABELS = ("no de ativos", "no de imoveis")


@dataclass(frozen=True)
class FundamentosPlanilha:
    ticker: str
    competencia: date | None
    patrimonio_liquido: float | None  # BRL, raw (never "milhões"/"bilhões")
    valor_mercado: float | None  # BRL, raw
    n_ativos: int | None
    n_locatarios: int | None
    abl_m2: float | None
    wale_anos: float | None
    vacancia_fisica: float | None  # fraction, e.g. 0.0043 = 0.43%
    vacancia_financeira: float | None  # fraction
    p_vp: float | None
    dy_mercado: float | None  # fraction
    dy_patrimonial: float | None  # fraction

    @property
    def occupancy_rate(self) -> float | None:
        """1 - vacância financeira -- the revenue-weighted occupancy
        rate, matching what FIIAnalyzer's ``occupancy_rate`` field
        means (see framework.py: ``occupancy * 100`` feeds the score
        directly, so this must be a fraction, not vacância itself)."""
        if self.vacancia_financeira is None:
            return None
        return round(1.0 - self.vacancia_financeira, 6)


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value))
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(stripped.lower().split())


def _find_value_below_label(ws, *label_variants: str) -> object | None:
    """Scan every cell for one whose normalized text exactly matches a
    label variant, then read the cell one row below in the SAME
    column -- confirmed live as the consistent value-placement rule
    across all three real "tijolo" Resumo sheets, even though the
    label's own column letter shifts between funds."""

    targets = {_normalize_text(v) for v in label_variants}
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is None:
                continue
            if _normalize_text(str(cell.value)) in targets:
                return ws.cell(row=cell.row + 1, column=cell.column)
    return None


def _normalized_brl(cell) -> float | None:
    if cell is None or cell.value is None:
        return None
    raw = float(cell.value)
    fmt = _normalize_text(str(cell.number_format or ""))
    if "bilh" in fmt:
        return raw * 1_000_000_000
    if "milh" in fmt:
        return raw * 1_000_000
    return raw


def _num(cell) -> float | None:
    if cell is None or cell.value is None:
        return None
    try:
        return float(cell.value)
    except (TypeError, ValueError):
        return None


def _int(cell) -> int | None:
    value = _num(cell)
    return int(value) if value is not None else None


def is_tijolo_layout(ws) -> bool:
    """True when this sheet has every label the "tijolo" Resumo
    template requires -- used to distinguish HGRU11/LVBI11/PVBI11's
    real-estate layout from HGCR11/PCIP11's credit-fund layout before
    trying to extract anything, rather than returning a half-filled,
    misleading result."""

    found = set()
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is None:
                continue
            found.add(_normalize_text(str(cell.value)))
    return all(any(label in text for text in found) for label in _REQUIRED_LABELS)


def parse_resumo_tijolo(workbook, ticker: str) -> FundamentosPlanilha | None:
    """Extract the "tijolo" Resumo sheet's indicators from an already-
    opened ``openpyxl`` workbook (``data_only=True``, so formulas read
    their last-calculated value, not the formula text). Returns
    ``None`` if there's no "Resumo" sheet or it doesn't match the
    tijolo layout (see ``is_tijolo_layout``) -- e.g. HGCR11/PCIP11's
    credit-fund template.
    """

    if "Resumo" not in workbook.sheetnames:
        return None
    ws = workbook["Resumo"]
    if not is_tijolo_layout(ws):
        return None

    competencia = None
    for row in ws.iter_rows(min_row=1, max_row=6):
        for cell in row:
            if hasattr(cell.value, "date"):
                competencia = cell.value.date()
                break
        if competencia:
            break

    return FundamentosPlanilha(
        ticker=ticker.strip().upper(),
        competencia=competencia,
        patrimonio_liquido=_normalized_brl(_find_value_below_label(ws, "patrimonio liquido")),
        valor_mercado=_normalized_brl(_find_value_below_label(ws, "valor de mercado")),
        n_ativos=_int(_find_value_below_label(ws, *_N_ATIVOS_LABELS)),
        n_locatarios=_int(_find_value_below_label(ws, "no de locatarios")),
        abl_m2=_num(_find_value_below_label(ws, "abl (m2)")),
        wale_anos=_num(_find_value_below_label(ws, "wale")),
        vacancia_fisica=_num(_find_value_below_label(ws, "vacancia fisica")),
        vacancia_financeira=_num(_find_value_below_label(ws, "vacancia financeira")),
        p_vp=_num(_find_value_below_label(ws, "p/vp")),
        dy_mercado=_num(_find_value_below_label(ws, "dy (mercado)")),
        dy_patrimonial=_num(_find_value_below_label(ws, "dy (patrimonial)")),
    )
