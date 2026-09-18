"""CVM DFP (Demonstrações Financeiras Padronizadas) — official open-data
channel for public companies' annual financial statements.

Built to close the gap documented in ``iip.cli.fetch_template``'s
``fetch_equity_template_live`` (confirmed live 18/09/2026): bolsai only
exposes pre-computed ratios (ROE, ROIC) for equities, never the raw
absolute figures (revenue, net income, equity) ``EquityAnalyzer`` needs
to compute those ratios itself. CVM publishes exactly those figures as
plain downloadable ZIP/CSV files, same open-data portal and layout
convention as ``cvm_fii.py`` (``dados.cvm.gov.br``, a CKAN instance, no
login/JS/Cloudflare) — confirmed live by downloading and inspecting a
real file (``dfp_cia_aberta_2025.zip``), not assumed from documentation.

Each year's ZIP contains, among others, six files this module reads:
``dfp_cia_aberta_{BPA,BPP,DRE}_{con,ind}_{ano}.csv`` — balance sheet
assets/liabilities and income statement, each in both consolidated
(``con``) and individual/holding-only (``ind``) variants. Rows are
keyed by ``CNPJ_CIA`` + ``CD_CONTA`` (a hierarchical account code,
e.g. ``"2.03"``) + ``ORDEM_EXERC`` (``"ÚLTIMO"``/``"PENÚLTIMO"`` —
each filing carries the current and prior fiscal year side by side).

CONFIRMED LIVE ACROSS ALL 14 PORTFOLIO EQUITIES (18/09/2026) — two real
findings that make ``CD_CONTA`` alone unreliable for cross-company
matching, so this module matches by ``DS_CONTA`` (account description)
text instead, wherever the code position isn't provably fixed:

  - Financial institutions (confirmed: ABCB4, a bank) file ONLY the
    ``_ind`` variant — the ``_con`` file has zero rows for their CNPJ.
    This module tries ``_con`` first and falls back to ``_ind`` per
    company, not globally, since most other companies DO file ``_con``.
  - ``CD_CONTA`` positions for "Patrimônio Líquido" and the final net
    income line move between taxonomies: a bank's equity line is
    ``"2.07"`` (``"Patrimônio Líquido"``), a normal company's is
    ``"2.03"`` (``"Patrimônio Líquido Consolidado"``) — same DS_CONTA
    substring, different code. ``"Ativo Total"`` (code ``"1"``) and the
    very first DRE line (code ``"3.01"``, always present since CVM's
    grouping numbering restarts at ``.01`` for every major section) ARE
    reliably positioned, confirmed across banks/insurers/industrials.
  - Insurance HOLDING companies (confirmed: BBSE3 — BB Seguridade,
    CXSE3 — Caixa Seguridade) report a genuine ``0`` at ``"3.01"`` and
    all its numbered children — their income is dominated by equity-
    method results from operating subsidiaries further down the
    statement, not top-line premium revenue. Treated as "not available"
    (``None``), not as a real zero, to avoid corrupting margin ratios
    downstream (dividing by a fabricated zero).
  - "EBIT" (``"Resultado Antes do Resultado Financeiro e dos Tributos"``,
    a real CVM standard line for non-financial companies) has no
    equivalent for banks — a bank's financial result IS its core
    business, not a separable financing cost. Left as ``None`` for
    financial institutions rather than approximated from an unrelated
    line — same "don't invent" call as the equity/holding case above.

Same request/response split as the other sources: this module builds
the request URL and parses the response; it performs no HTTP request
itself (see ``.cvm_dfp_harvester`` for the transport).
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass

BASE_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS"
_FIRST_AVAILABLE_YEAR = 2010

_ULTIMO = "ÚLTIMO"  # "ÚLTIMO"

_STATEMENT_GROUPS = ("BPA_con", "BPA_ind", "BPP_con", "BPP_ind", "DRE_con", "DRE_ind")


@dataclass(frozen=True)
class CvmDfpTarget:
    ano: int
    url: str
    provider: str = "cvm"
    role: str = "regulatory"
    year: int | None = None
    # Same "MULTI" convention as CvmFiiTarget -- one DFP ZIP covers
    # every open company's annual filing at once, not one ticker.
    ticker: str = "MULTI"
    cnpj: str | None = None


@dataclass(frozen=True)
class DfpRow:
    cnpj_cia: str
    ordem_exerc: str
    dt_fim_exerc: str
    cd_conta: str
    ds_conta: str
    vl_conta: float | None


@dataclass(frozen=True)
class CompanyFundamentals:
    cnpj_cia: str
    ano_referencia: int
    consolidado: bool
    ativo_total: float | None
    patrimonio_liquido: float | None
    receita: float | None
    lucro_liquido: float | None
    ebit: float | None
    passivo_nao_circulante: float | None


def build_target(ano: int) -> CvmDfpTarget:
    """Build the request URL for a given fiscal year's DFP ZIP.

    ``ano`` is the FISCAL year the statements cover (e.g. ``2025`` for
    the year ended 2025-12-31), not the filing/calendar year -- DFP for
    a given fiscal year is only filed, and only available here, a few
    months into the following calendar year.
    """

    if ano < _FIRST_AVAILABLE_YEAR:
        raise ValueError(
            f"CVM's structured DFP dataset starts in {_FIRST_AVAILABLE_YEAR}"
        )
    url = f"{BASE_URL}/dfp_cia_aberta_{ano}.zip"
    return CvmDfpTarget(ano=ano, url=url, year=ano)


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.lower().strip()


def _normalize_cnpj(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def _parse_number(raw: str) -> float | None:
    cleaned = raw.strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _read_csv_rows(archive: zipfile.ZipFile, filename_fragment: str) -> list[dict[str, str]]:
    matches = [name for name in archive.namelist() if filename_fragment in name]
    if not matches:
        return []
    with archive.open(matches[0]) as raw:
        text = io.TextIOWrapper(raw, encoding="latin-1", newline="")
        reader = csv.DictReader(text, delimiter=";")
        return list(reader)


def _parse_statement(body: bytes, filename_fragment: str) -> tuple[DfpRow, ...]:
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        rows = _read_csv_rows(archive, filename_fragment)
    return tuple(
        DfpRow(
            cnpj_cia=row.get("CNPJ_CIA", ""),
            ordem_exerc=row.get("ORDEM_EXERC", ""),
            dt_fim_exerc=row.get("DT_FIM_EXERC", ""),
            cd_conta=row.get("CD_CONTA", ""),
            ds_conta=row.get("DS_CONTA", ""),
            vl_conta=_parse_number(row.get("VL_CONTA", "")),
        )
        for row in rows
    )


def parse_bpa_con(body: bytes) -> tuple[DfpRow, ...]:
    return _parse_statement(body, "_BPA_con_")


def parse_bpa_ind(body: bytes) -> tuple[DfpRow, ...]:
    return _parse_statement(body, "_BPA_ind_")


def parse_bpp_con(body: bytes) -> tuple[DfpRow, ...]:
    return _parse_statement(body, "_BPP_con_")


def parse_bpp_ind(body: bytes) -> tuple[DfpRow, ...]:
    return _parse_statement(body, "_BPP_ind_")


def parse_dre_con(body: bytes) -> tuple[DfpRow, ...]:
    return _parse_statement(body, "_DRE_con_")


def parse_dre_ind(body: bytes) -> tuple[DfpRow, ...]:
    return _parse_statement(body, "_DRE_ind_")


def _find_ativo_total(rows: tuple[DfpRow, ...]) -> DfpRow | None:
    return next((r for r in rows if r.cd_conta == "1"), None)


def _find_receita(rows: tuple[DfpRow, ...]) -> DfpRow | None:
    row = next((r for r in rows if r.cd_conta == "3.01"), None)
    if row is not None and row.vl_conta not in (None, 0.0):
        return row
    return None


def _find_patrimonio_liquido(rows: tuple[DfpRow, ...]) -> DfpRow | None:
    candidates = [
        r
        for r in rows
        if r.cd_conta.count(".") == 1
        and "patrimonio liquido" in _normalize_text(r.ds_conta)
        and "atribuido" not in _normalize_text(r.ds_conta)
    ]
    return candidates[0] if candidates else None


_LUCRO_LIQUIDO_RE = re.compile(r"(lucro|prejuizo).*periodo$")


def _find_lucro_liquido(rows: tuple[DfpRow, ...]) -> DfpRow | None:
    candidates = [
        r
        for r in rows
        if r.cd_conta.count(".") <= 1 and _LUCRO_LIQUIDO_RE.search(_normalize_text(r.ds_conta))
    ]
    return candidates[0] if candidates else None


def _find_ebit(rows: tuple[DfpRow, ...]) -> DfpRow | None:
    candidates = [
        r
        for r in rows
        if "resultado antes do resultado financeiro e dos tributos" in _normalize_text(r.ds_conta)
    ]
    return candidates[0] if candidates else None


def _find_passivo_nao_circulante(rows: tuple[DfpRow, ...]) -> DfpRow | None:
    candidates = [
        r
        for r in rows
        if r.cd_conta.count(".") == 1 and _normalize_text(r.ds_conta) == "passivo nao circulante"
    ]
    return candidates[0] if candidates else None


def extract_fundamentals(
    ano: int,
    cnpj: str,
    *,
    bpa_con: tuple[DfpRow, ...],
    bpa_ind: tuple[DfpRow, ...],
    bpp_con: tuple[DfpRow, ...],
    bpp_ind: tuple[DfpRow, ...],
    dre_con: tuple[DfpRow, ...],
    dre_ind: tuple[DfpRow, ...],
) -> CompanyFundamentals | None:
    """Extract one company's real fundamentals from a year's already-
    parsed DFP statements. Returns ``None`` if the CNPJ has no rows in
    either the consolidated or individual balance sheet — a genuine
    "this company didn't file DFP for this year" case, not an error.

    Prefers consolidated (``_con``) figures, falling back to
    individual/holding-only (``_ind``) per company (confirmed live:
    banks like ABCB4 only file ``_ind``) -- never mixes the two within
    one company's snapshot.
    """

    normalized = _normalize_cnpj(cnpj)

    def _for_cnpj(rows: tuple[DfpRow, ...]) -> tuple[DfpRow, ...]:
        return tuple(r for r in rows if _normalize_cnpj(r.cnpj_cia) == normalized)

    consolidado = bool(_for_cnpj(bpa_con))
    bpa_rows = _for_cnpj(bpa_con) if consolidado else _for_cnpj(bpa_ind)
    if not bpa_rows:
        return None
    bpp_rows = _for_cnpj(bpp_con) if consolidado else _for_cnpj(bpp_ind)
    dre_rows = _for_cnpj(dre_con) if consolidado else _for_cnpj(dre_ind)

    bpa_ultimo = tuple(r for r in bpa_rows if r.ordem_exerc == _ULTIMO)
    bpp_ultimo = tuple(r for r in bpp_rows if r.ordem_exerc == _ULTIMO)
    dre_ultimo = tuple(r for r in dre_rows if r.ordem_exerc == _ULTIMO)

    ativo = _find_ativo_total(bpa_ultimo)
    pl = _find_patrimonio_liquido(bpp_ultimo)
    receita = _find_receita(dre_ultimo)
    lucro = _find_lucro_liquido(dre_ultimo)
    ebit = _find_ebit(dre_ultimo)
    passivo_nc = _find_passivo_nao_circulante(bpp_ultimo)

    return CompanyFundamentals(
        cnpj_cia=cnpj,
        ano_referencia=ano,
        consolidado=consolidado,
        ativo_total=ativo.vl_conta if ativo else None,
        patrimonio_liquido=pl.vl_conta if pl else None,
        receita=receita.vl_conta if receita else None,
        lucro_liquido=lucro.vl_conta if lucro else None,
        ebit=ebit.vl_conta if ebit else None,
        passivo_nao_circulante=passivo_nc.vl_conta if passivo_nc else None,
    )
