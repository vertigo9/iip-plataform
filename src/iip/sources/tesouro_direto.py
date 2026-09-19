"""Tesouro Direto bond rates -- the real yield of the long NTN-B.

Built to replace the fixed 6% required yield in Bazin's method with the
market's actual real opportunity cost (see
``iip.portfolio_data.valuation_methods``): a company that can pass
inflation through pays dividends that behave like a real yield, so the
coupon of the longest inflation-linked government bond is the risk-free
rate to beat.

Source: Tesouro Transparente's open dataset ``PrecoTaxaTesouroDireto.csv``
(``tesourotransparente.gov.br``, no login), semicolon-separated, decimal
comma, latin-1, one row per bond per business day. Confirmed live
(18/09/2026): the newest business day (17/09/2026) sits at the TOP of the
file, and the file is ~14.5 MB. The old ``tesourodireto.com.br`` JSON
endpoint now answers 410 Gone.

Which rate, and why:
  - Bond: ``Tesouro IPCA+ com Juros Semestrais`` (the NTN-B, which pays a
    coupon -- the closest analogue to a dividend stream), the LONGEST
    maturity available on the latest business day.
  - Column: ``Taxa Venda Manha`` -- the tesouro's *sale* rate, i.e. the
    yield an investor actually locks in by buying. ``Taxa Compra Manha``
    is the rate at which the Tesouro buys the bond back (lower), not an
    opportunity cost anyone can capture.
  - The rate is REAL (over IPCA), returned as a fraction (0.073 = IPCA +
    7.3%), directly comparable to a dividend yield.

A rate older than ``max_age_days`` is reported as unavailable rather than
used: an old rate would silently mis-price everything downstream.

Same split as the other sources: this module parses; the transport is in
``.tesouro_direto_harvester``.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime

URL = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
    "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/PrecoTaxaTesouroDireto.csv"
)

NTNB_TITLE = "Tesouro IPCA+ com Juros Semestrais"
DEFAULT_MAX_AGE_DAYS = 10

# A real yield outside this range is a parsing/data error, not a market
# rate -- refused instead of being fed into a valuation.
_PLAUSIBLE_REAL_YIELD = (0.0, 0.25)


@dataclass(frozen=True)
class TesouroRateRow:
    titulo: str
    vencimento: date
    data_base: date
    taxa_compra: float | None  # percent, as published
    taxa_venda: float | None  # percent, as published


@dataclass(frozen=True)
class NtnbRate:
    reference_date: date
    maturity: date
    real_yield: float  # fraction over IPCA, e.g. 0.073
    title: str = NTNB_TITLE


def _parse_date(raw: str) -> date | None:
    try:
        return datetime.strptime(raw.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def _parse_percent(raw: str) -> float | None:
    cleaned = raw.strip().replace(".", "").replace(",", ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_rates(
    text: str, *, drop_last_line: bool = False
) -> tuple[TesouroRateRow, ...]:
    """Parse the CSV body. ``drop_last_line`` discards a possibly truncated
    final line -- set it when the body came from a partial (ranged) read."""
    lines = text.splitlines()
    if drop_last_line and lines:
        lines = lines[:-1]
    reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=";")
    rows: list[TesouroRateRow] = []
    for raw in reader:
        vencimento = _parse_date(raw.get("Data Vencimento", ""))
        data_base = _parse_date(raw.get("Data Base", ""))
        if vencimento is None or data_base is None:
            continue
        rows.append(
            TesouroRateRow(
                titulo=(raw.get("Tipo Titulo") or "").strip(),
                vencimento=vencimento,
                data_base=data_base,
                taxa_compra=_parse_percent(raw.get("Taxa Compra Manha", "")),
                taxa_venda=_parse_percent(raw.get("Taxa Venda Manha", "")),
            )
        )
    return tuple(rows)


def long_ntnb_rate(
    rows: tuple[TesouroRateRow, ...],
    *,
    today: date,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> NtnbRate | None:
    """Real yield of the longest-maturity NTN-B on the most recent business
    day present in ``rows``. ``None`` when there is no usable, recent,
    plausible rate."""
    ntnb = [r for r in rows if r.titulo == NTNB_TITLE and r.taxa_venda is not None]
    if not ntnb:
        return None
    latest = max(r.data_base for r in ntnb)
    if (today - latest).days > max_age_days:
        return None
    on_latest = [r for r in ntnb if r.data_base == latest]
    longest = max(on_latest, key=lambda r: r.vencimento)
    real_yield = longest.taxa_venda / 100.0
    low, high = _PLAUSIBLE_REAL_YIELD
    if not low < real_yield < high:
        return None
    return NtnbRate(
        reference_date=latest,
        maturity=longest.vencimento,
        real_yield=round(real_yield, 6),
    )
