"""Auto-fill FII analysis templates from real fetched data.

Audit finding that motivated this module: `iip analyze` requires a
hand-authored JSON data-file — none of this session's providers
(CVM, bolsai, brapi, BACEN, IBGE, MZIQ) were wired to it. This module
is that wiring, for FII specifically (the asset class with the most
complete provider coverage this session).

Not full automation — `FIIAnalyzer` (see `iip.analysis.framework`)
expects 27 financial fields, most of which are qualitative/judgment
calls (occupancy rate, tenant concentration, board independence,
disclosure quality, manager track record, location quality...) that
no structured data source provides; they would need PDF report
reading or human judgment, out of scope here. Only three fields are
genuinely derivable from data this project already fetches:

  - ``dividend_yield`` — CVM FII's ``Percentual_Dividend_Yield_Mes``
    is a MONTHLY fraction (confirmed live: 0.009476 for BTLG11,
    July/2026). ``FIIAnalyzer`` expects an ANNUAL PERCENTAGE NUMBER
    (confirmed by reading the analyzer's own scoring code:
    ``score = min(dy * 12, 100)`` only makes sense if dy is a percent
    like 8, not a fraction like 0.08). Computed here as the sum of the
    trailing available months (up to 12) × 100 — a real TTM
    calculation, not a single month annualized by multiplication
    (which would overstate volatility).
  - ``assets_under_management_millions`` — CVM's ``Patrimonio_Liquido``
    (already in BRL) divided by 1,000,000.
  - ``reit_premium_discount`` — (market price − CVM's
    ``Valor_Patrimonial_Cotas``) / ``Valor_Patrimonial_Cotas``,
    confirmed to be a fraction (``abs(premium) * 200`` in the scoring
    code only makes sense for a fraction like 0.05, not a percent
    like 5).

``market_cap`` (price × ``Cotas_Emitidas``) and ``price`` itself are
also filled when available — these are ``AssetData`` fields, not
entries in the qualitative ``financials`` dict.

Every other field is left at the analyzer's own stated default
(reusing ``iip.cli.main._template_financials``, so this can never
drift from what the analyzer actually reads) — never silently
invented.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from iip.sources.cvm_fii import FiiComplemento


@dataclass(frozen=True)
class FetchResult:
    """What actually got fetched vs. left at analyzer defaults —
    surfaced explicitly so the person using this never mistakes a
    default for a real number."""

    fetched_fields: tuple[str, ...] = field(default_factory=tuple)
    dividend_yield_months_used: int = 0
    warnings: tuple[str, ...] = field(default_factory=tuple)


def compute_dividend_yield_ttm(
    complementos: list[FiiComplemento],
) -> tuple[float | None, int]:
    """Sum ``Percentual_Dividend_Yield_Mes`` over the most recent
    available months (up to 12), return (annualized_percent,
    months_used). Returns (None, 0) if no usable data at all."""

    ordenados = sorted(complementos, key=lambda c: c.data_referencia, reverse=True)
    ultimos = ordenados[:12]
    valores = [
        c.valores.get("Percentual_Dividend_Yield_Mes")
        for c in ultimos
        if c.valores.get("Percentual_Dividend_Yield_Mes") is not None
    ]
    if not valores:
        return None, 0
    return sum(valores) * 100, len(valores)


def latest_complemento_for_cnpj(
    complementos: list[FiiComplemento], cnpj: str
) -> FiiComplemento | None:
    normalized_cnpj = "".join(ch for ch in cnpj if ch.isdigit())
    matches = [
        c
        for c in complementos
        if "".join(ch for ch in c.cnpj_fundo_classe if ch.isdigit()) == normalized_cnpj
    ]
    if not matches:
        return None
    return max(matches, key=lambda c: c.data_referencia)


def build_fii_template(
    symbol: str,
    cnpj: str,
    complementos: list[FiiComplemento],
    default_financials: dict[str, Any],
    price: float | None = None,
) -> tuple[dict[str, Any], FetchResult]:
    """Assemble the same JSON shape ``iip analyze --data-file`` expects,
    with the fetchable fields filled from real data and everything
    else left at ``default_financials`` (from
    ``iip.cli.main._template_financials(FIIAnalyzer)``).
    """

    financials = dict(default_financials)
    fetched: list[str] = []
    warnings: list[str] = []

    cnpj_matches = [
        c
        for c in complementos
        if "".join(ch for ch in c.cnpj_fundo_classe if ch.isdigit())
        == "".join(ch for ch in cnpj if ch.isdigit())
    ]
    if not cnpj_matches:
        warnings.append(
            f"Nenhum registro CVM encontrado para o CNPJ {cnpj} — "
            "verifique se o CNPJ está certo e se o ano consultado tem dado."
        )

    dy_pct, months_used = compute_dividend_yield_ttm(cnpj_matches)
    if dy_pct is not None:
        financials["dividend_yield"] = round(dy_pct, 4)
        fetched.append("dividend_yield")
        if months_used < 12:
            warnings.append(
                f"dividend_yield calculado com apenas {months_used} mes(es) "
                "de dado disponivel, nao os 12 meses completos (TTM parcial)."
            )

    latest = latest_complemento_for_cnpj(cnpj_matches, cnpj)
    pl = latest.valores.get("Patrimonio_Liquido") if latest else None
    vp_cota = latest.valores.get("Valor_Patrimonial_Cotas") if latest else None
    cotas_emitidas = latest.valores.get("Cotas_Emitidas") if latest else None

    if pl is not None:
        financials["assets_under_management_millions"] = round(pl / 1_000_000, 2)
        fetched.append("assets_under_management_millions")

    market_cap = None
    if price is not None and cotas_emitidas is not None:
        market_cap = round(price * cotas_emitidas, 2)
        fetched.append("market_cap")

    if price is not None and vp_cota not in (None, 0):
        premium = (price - vp_cota) / vp_cota
        financials["reit_premium_discount"] = round(premium, 4)
        fetched.append("reit_premium_discount")

    if price is not None:
        fetched.append("price")
    else:
        warnings.append("Preço não informado/buscado — reit_premium_discount e market_cap ficam vazios.")

    template = {
        "symbol": symbol.upper(),
        "sector": "REPLACE_WITH_SECTOR",
        "industry": "REPLACE_WITH_INDUSTRY",
        "market_cap": market_cap,
        "price": price,
        "financials": financials,
    }

    return template, FetchResult(
        fetched_fields=tuple(fetched),
        dividend_yield_months_used=months_used,
        warnings=tuple(warnings),
    )
