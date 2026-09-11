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

from iip.sources.cvm_fii import FiiComplemento, FiiGeral
from iip.sources.cvm_renda_fixa import InformeDiario


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
    geral: list[FiiGeral] | None = None,
) -> tuple[dict[str, Any], FetchResult]:
    """Assemble the same JSON shape ``iip analyze --data-file`` expects,
    with the fetchable fields filled from real data and everything
    else left at ``default_financials`` (from
    ``iip.cli.main._template_financials(FIIAnalyzer)``).

    ``geral`` is optional (defaults to none fetched) — when given, also
    fills ``sector`` from CVM's ``Segmento_Atuacao``, a feature ported
    from the parallel implementation in ``iip.integration.fii_template``
    (see that module's docstring for why the two exist side by side).
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

    sector = "REPLACE_WITH_SECTOR"
    if geral:
        cnpj_normalizado = "".join(ch for ch in cnpj if ch.isdigit())
        geral_matches = [
            g
            for g in geral
            if "".join(ch for ch in g.cnpj_fundo_classe if ch.isdigit()) == cnpj_normalizado
        ]
        if geral_matches:
            mais_recente = max(geral_matches, key=lambda g: g.data_referencia)
            if mais_recente.segmento_atuacao:
                sector = mais_recente.segmento_atuacao
                fetched.append("sector")

    template = {
        "symbol": symbol.upper(),
        "sector": sector,
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


def fetch_fii_template_live(
    symbol: str,
    cnpj: str,
    ano: int,
    bolsai_api_key: str | None,
) -> tuple[dict[str, Any], FetchResult]:
    """Do the real network fetch (CVM FII + optional bolsai price) and
    assemble the FII template. Raises whatever the CVM harvester raises
    on failure — that's a hard stop, there's no FII data to build a
    template from without it. A bolsai failure is NOT raised — it's
    folded into the returned FetchResult.warnings, since price is
    optional (the CVM-only fields still get filled).
    """
    from iip.sources.b3_bolsai import build_fii_target as _build_bolsai_fii_target
    from iip.sources.b3_bolsai_harvester import BolsaiHTTPHarvester as _BolsaiHTTPHarvester
    from iip.sources.cvm_fii import build_target as _build_cvm_fii_target
    from iip.sources.cvm_fii_harvester import CvmFiiHTTPHarvester as _CvmFiiHTTPHarvester

    cvm_result = _CvmFiiHTTPHarvester().fetch(_build_cvm_fii_target(ano))

    price = None
    bolsai_warning = None
    if bolsai_api_key:
        try:
            bolsai_result = _BolsaiHTTPHarvester(api_key=bolsai_api_key).fetch_fii(
                _build_bolsai_fii_target(symbol)
            )
            price = bolsai_result.fii.close_price
        except Exception as exc:
            bolsai_warning = f"não consegui buscar preço via bolsai: {exc}"

    default_financials = _fii_defaults()
    template, resultado = build_fii_template(
        symbol=symbol,
        cnpj=cnpj,
        complementos=list(cvm_result.complemento),
        default_financials=default_financials,
        price=price,
        geral=list(cvm_result.geral),
    )
    if bolsai_warning:
        resultado = FetchResult(
            fetched_fields=resultado.fetched_fields,
            dividend_yield_months_used=resultado.dividend_yield_months_used,
            warnings=(*resultado.warnings, bolsai_warning),
        )
    return template, resultado


def fetch_etf_template_live(
    symbol: str,
    cnpj: str,
    ano: int,
    mes: int,
    brapi_token: str | None,
) -> tuple[dict[str, Any], FetchResult]:
    """Same idea as ``fetch_fii_template_live`` but for ETFs (CVM
    Informe Diário + optional brapi.dev price)."""
    from iip.sources.b3_brapi import build_target as _build_brapi_target
    from iip.sources.b3_brapi_harvester import BrapiHTTPHarvester as _BrapiHTTPHarvester
    from iip.sources.cvm_renda_fixa import build_diario_target as _build_cvm_diario_target
    from iip.sources.cvm_renda_fixa_harvester import (
        CvmRendaFixaHTTPHarvester as _CvmRendaFixaHTTPHarvester,
    )

    diario_result = _CvmRendaFixaHTTPHarvester().fetch_diario(
        _build_cvm_diario_target(ano, mes)
    )

    price = None
    brapi_warning = None
    if brapi_token:
        try:
            brapi_result = _BrapiHTTPHarvester(token=brapi_token).fetch(
                _build_brapi_target((symbol,))
            )
            if brapi_result.quotes:
                price = brapi_result.quotes[0].regular_market_price
        except Exception as exc:
            brapi_warning = f"não consegui buscar preço via brapi.dev: {exc}"

    default_financials = _etf_defaults()
    template, resultado = build_etf_template(
        symbol=symbol,
        cnpj=cnpj,
        informes=list(diario_result.informes),
        default_financials=default_financials,
        price=price,
    )
    if brapi_warning:
        resultado = FetchResult(
            fetched_fields=resultado.fetched_fields,
            dividend_yield_months_used=resultado.dividend_yield_months_used,
            warnings=(*resultado.warnings, brapi_warning),
        )
    return template, resultado


def _fii_defaults() -> dict[str, Any]:
    from iip.analysis import FIIAnalyzer
    from iip.cli.main import _template_financials

    return _template_financials(FIIAnalyzer)


def _etf_defaults() -> dict[str, Any]:
    from iip.analysis import ETFAnalyzer
    from iip.cli.main import _template_financials

    return _template_financials(ETFAnalyzer)


def latest_informe_for_cnpj(
    informes: list[InformeDiario], cnpj: str
) -> InformeDiario | None:
    normalized_cnpj = "".join(ch for ch in cnpj if ch.isdigit())
    matches = [
        i
        for i in informes
        if "".join(ch for ch in i.cnpj_fundo_classe if ch.isdigit()) == normalized_cnpj
    ]
    if not matches:
        return None
    return max(matches, key=lambda i: i.data_competencia)


def build_etf_template(
    symbol: str,
    cnpj: str,
    informes: list[InformeDiario],
    default_financials: dict[str, Any],
    price: float | None = None,
) -> tuple[dict[str, Any], FetchResult]:
    """Assemble an ETF template from CVM's Informe Diário (ICVM 555 —
    covers ETFs too, not just bonds/fixed income despite the module's
    name) plus a market price.

    Deliberately more conservative than ``build_fii_template``: the
    Informe Diário fetch this reads from covers ONE competência month,
    so fields with an inherently period-based meaning (e.g. YTD net
    inflows) are NOT filled from a single month's flow — that would
    misrepresent a partial figure as a full-period one. Only genuinely
    point-in-time or directly-computable fields are filled:
    ``assets_under_management_millions`` (a snapshot, valid regardless
    of how much history was fetched), ``price``, and ``market_cap``
    (estimated as price × (VL_TOTAL / VL_QUOTA), since Informe Diário
    has no direct shares-outstanding field — VL_TOTAL/VL_QUOTA is the
    implied cota count).
    """

    financials = dict(default_financials)
    fetched: list[str] = []
    warnings: list[str] = []

    normalized_cnpj = "".join(ch for ch in cnpj if ch.isdigit())
    cnpj_matches = [
        i
        for i in informes
        if "".join(ch for ch in i.cnpj_fundo_classe if ch.isdigit()) == normalized_cnpj
    ]
    if not cnpj_matches:
        warnings.append(
            f"Nenhum registro CVM (Informe Diário) encontrado para o CNPJ {cnpj} — "
            "verifique o CNPJ e se o mês consultado tem dado. Nota: alguns ETFs "
            "podem não estar estruturados como fundo ICVM 555 e não aparecer aqui."
        )

    latest = latest_informe_for_cnpj(cnpj_matches, cnpj)

    if latest is not None and latest.patrimonio_liquido is not None:
        financials["assets_under_management_millions"] = round(
            latest.patrimonio_liquido / 1_000_000, 2
        )
        fetched.append("assets_under_management_millions")

    market_cap = None
    if (
        price is not None
        and latest is not None
        and latest.valor_total is not None
        and latest.valor_cota not in (None, 0)
    ):
        cotas_implicitas = latest.valor_total / latest.valor_cota
        market_cap = round(price * cotas_implicitas, 2)
        fetched.append("market_cap")

    if price is not None:
        fetched.append("price")
    else:
        warnings.append(
            "Preço não informado/buscado — market_cap fica vazio."
        )

    warnings.append(
        "assets_under_management_millions vem de um único mês de Informe "
        "Diário — não há aqui dado suficiente para aum_growth_3y_pct, "
        "net_inflows_ytd_millions, tracking_error_pct, expense_ratio_pct ou "
        "os indicadores de liquidez (volume, spread) — todos continuam com "
        "os valores-padrão do analisador."
    )

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
        dividend_yield_months_used=0,
        warnings=tuple(warnings),
    )
