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
    fills ``sector`` from CVM's ``Segmento_Atuacao``. This was ported
    from ``iip.integration.fii_template``, an earlier parallel
    implementation of the same idea (same CVM+price sourcing, same
    dividend_yield/AUM logic) that predated this module. That module
    and its ``fetch-fii-template`` CLI command were removed once this
    one (``fetch-template --type fii``) fully covered the same ground
    — this docstring keeps the note for anyone who finds a reference
    to the old name in history or documentation.
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


def _enrich_fii_with_patria_fundamentos(
    financials: dict[str, Any], symbol: str
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Best-effort enrichment from Pátria's real "Planilha de
    Fundamentos" spreadsheet (see
    ``iip.sources.patria_planilha_fundamentos``, added 18/09/2026) --
    fills real data for Pátria's two sheet layouts:

      - "tijolo" (physical real-estate) funds HGRU11/LVBI11/PVBI11:
        ``occupancy_rate`` (1 - vacância financeira) and
        ``avg_lease_term_years`` (WALE).
      - credit funds HGCR11/PCIP11: only ``reserves_to_npa`` (reserva
        acumulada por cota / VP por cota). Their sheet also carries
        prazo médio/spread of the CRI portfolio, but those are NOT
        mapped: a CRI portfolio's duration is not a lease term, so
        feeding it to ``avg_lease_term_years`` would be a
        semantically wrong number dressed up as a real one.

    No-ops entirely (returns ``financials`` unchanged, no warning) for
    any ticker without a Pátria MZIQ config at all -- this is called
    for EVERY FII, not just Pátria's, so staying silent for the other
    ~20 is deliberate (a warning here would be noise, not signal, for
    a fund this enrichment was never going to apply to).
    """
    from iip.sources.patria_mziq import fund_for_ticker as _patria_fund_for_ticker
    from iip.sources.patria_planilha_fundamentos_harvester import (
        PatriaPlanilhaFundamentosHTTPHarvester as _PatriaPlanilhaHarvester,
    )

    fetched: list[str] = []
    warnings: list[str] = []

    if _patria_fund_for_ticker(symbol) is None:
        return financials, fetched, warnings

    try:
        result = _PatriaPlanilhaHarvester().fetch(symbol)
    except Exception as exc:  # noqa: BLE001 — enriquecimento é best-effort, nunca deve derrubar o template CVM já montado
        warnings.append(
            f"não consegui buscar a Planilha de Fundamentos da Pátria: {exc}"
        )
        return financials, fetched, warnings

    if result.fundamentos is None and result.credito is None:
        warnings.append(
            "Planilha de Fundamentos da Pátria não tem o layout 'tijolo' nem "
            "o de crédito esperado (ou não há documento publicado ainda) — "
            "occupancy_rate/avg_lease_term_years/reserves_to_npa continuam "
            "no valor-padrão."
        )
        return financials, fetched, warnings

    financials = dict(financials)
    if result.fundamentos is not None:
        fund = result.fundamentos
        if fund.occupancy_rate is not None:
            financials["occupancy_rate"] = fund.occupancy_rate
            fetched.append("occupancy_rate")
        if fund.wale_anos is not None:
            financials["avg_lease_term_years"] = round(fund.wale_anos, 2)
            fetched.append("avg_lease_term_years")
    else:
        reserves = result.credito.reserves_to_npa
        if reserves is not None:
            financials["reserves_to_npa"] = reserves
            fetched.append("reserves_to_npa")

    return financials, fetched, warnings


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

    Also tries a Pátria-specific enrichment (real occupancy_rate/
    avg_lease_term_years for HGRU11/LVBI11/PVBI11, reserves_to_npa for
    HGCR11/PCIP11 — see
    ``_enrich_fii_with_patria_fundamentos``) — best-effort, same
    never-raises-on-failure treatment as the bolsai price lookup.
    """
    from iip.sources.b3_bolsai import build_fii_target as _build_bolsai_fii_target
    from iip.sources.b3_bolsai_harvester import (
        BolsaiHTTPHarvester as _BolsaiHTTPHarvester,
    )
    from iip.sources.cvm_fii import build_target as _build_cvm_fii_target
    from iip.sources.cvm_fii_harvester import (
        CvmFiiHTTPHarvester as _CvmFiiHTTPHarvester,
    )

    cvm_result = _CvmFiiHTTPHarvester().fetch(_build_cvm_fii_target(ano))

    price = None
    bolsai_warning = None
    if bolsai_api_key:
        try:
            bolsai_result = _BolsaiHTTPHarvester(api_key=bolsai_api_key).fetch_fii(
                _build_bolsai_fii_target(symbol)
            )
            price = bolsai_result.fii.close_price
        except Exception as exc:  # noqa: BLE001 — preço é opcional; qualquer falha aqui (rede, JSON, o que for) não deve derrubar os dados da CVM já obtidos
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
    enriched_financials, patria_fetched, patria_warnings = (
        _enrich_fii_with_patria_fundamentos(template["financials"], symbol)
    )
    template["financials"] = enriched_financials

    extra_warnings = (
        *([bolsai_warning] if bolsai_warning else []),
        *patria_warnings,
    )
    if patria_fetched or extra_warnings:
        resultado = FetchResult(
            fetched_fields=(*resultado.fetched_fields, *patria_fetched),
            dividend_yield_months_used=resultado.dividend_yield_months_used,
            warnings=(*resultado.warnings, *extra_warnings),
        )
    return template, resultado


def _cagr_pct(start: float | None, end: float | None, years: int) -> float | None:
    """CAGR as a plain percent number (e.g. 12.5, not 0.125) — matches
    how ``EquityAnalyzer`` reads growth fields (``rg * 2`` in its own
    scoring code only makes sense for a percent). Returns ``None`` for
    any input that can't produce a real, meaningful rate: a missing
    value, or a non-positive start/end (a loss year makes exponentiation
    undefined/nonsensical — better to leave the field at the analyzer's
    default than report a fabricated or complex-valued rate).
    """
    if start is None or end is None or start <= 0 or end <= 0:
        return None
    return round(((end / start) ** (1 / years) - 1) * 100, 4)


def fetch_equity_template_live(
    symbol: str,
    cnpj: str,
    ano: int,
    bolsai_api_key: str | None,
    brapi_token: str | None,
) -> tuple[dict[str, Any], FetchResult]:
    """Fill what's honestly fillable for an equity from real data.

    RESOLVED (18/09/2026) — this function used to fill only price/
    market_cap/dividend_yield via bolsai/brapi, since bolsai's stock
    fundamentals endpoint exposes PRE-COMPUTED RATIOS (ROE, ROIC,
    margins) rather than the raw absolute financial-statement figures
    (``revenue``, ``net_income``, ``ebit``, ``equity``,
    ``invested_capital``) ``EquityAnalyzer`` actually reads. Confirmed
    live: all 14 portfolio equities produced byte-for-byte identical
    ``Decision`` objects, since those 3 fields alone couldn't
    differentiate companies once ~26 other fields sat at identical
    defaults (see ``vault/07_Research/02_Limitacao_Decisoes_Equity.md``
    for the original finding).

    Now also pulls CVM's DFP (Demonstrações Financeiras Padronizadas —
    see ``iip.sources.cvm_dfp`` for the real, absolute figures CVM
    publishes per company (same open-data channel as ``cvm_fii``):
      - ``equity``, ``net_income``, ``revenue`` — straight from the
        most recent DFP filing (year ``ano``).
      - ``ebit`` — only for non-financial companies (CVM's standard
        "Resultado Antes do Resultado Financeiro e dos Tributos" line
        has no equivalent for banks, confirmed live with ABCB4 — left
        at the default rather than approximated).
      - ``invested_capital`` — equity + non-current liabilities, a
        common simplified "capital employed" proxy; only computable
        where the balance sheet splits circulante/não circulante
        (confirmed absent for banks, which classify differently).
      - ``revenue_growth_3y``/``earnings_growth_3y``/
        ``book_value_growth_3y`` — real CAGR between ``ano`` and
        ``ano - 3``'s DFP filings. May reflect M&A/corporate
        restructuring, not organic growth (confirmed live: ALOS3's
        CNPJ predates the 2023 Aliansce+BrMalls merger) — cross-check
        before treating as a clean organic growth signal.

      - ``current_ratio``, ``debt_to_equity``, ``interest_coverage`` —
        from CVM's standard-chart lines (circulante; "Empréstimos e
        Financiamentos" short + long term; "Despesas Financeiras").
        Revises this function's earlier call to leave ``debt_to_equity``
        out: checked live, that label IS stable across the 10
        non-financial portfolio companies. Banks/insurers don't carry
        those lines under those labels, so they stay at the default
        (their leverage is the business model, not a financing choice).
        A debt total of zero is treated as unavailable, not as "no
        debt" (ALOS3 files its debt outside those lines).

    Qualitative/judgment fields (moat, governance, management quality,
    pricing power, WACC, detailed cash flow...) remain at the
    analyzer's defaults — no structured data source provides these;
    they need real report reading or analyst judgment, out of scope
    here, same as every other asset class's fetch-template function.
    """
    from iip.sources.b3_bolsai import build_target as _build_bolsai_target
    from iip.sources.b3_bolsai_harvester import (
        BolsaiHTTPHarvester as _BolsaiHTTPHarvester,
    )
    from iip.sources.b3_brapi import build_target as _build_brapi_target
    from iip.sources.b3_brapi_harvester import BrapiHTTPHarvester as _BrapiHTTPHarvester
    from iip.sources.cvm_dfp import build_target as _build_cvm_dfp_target
    from iip.sources.cvm_dfp import extract_fundamentals as _extract_dfp_fundamentals
    from iip.sources.cvm_dfp_harvester import (
        CvmDfpHTTPHarvester as _CvmDfpHTTPHarvester,
    )

    default_financials = _equity_defaults()
    financials = dict(default_financials)
    fetched: list[str] = []
    warnings: list[str] = []
    price: float | None = None
    market_cap: float | None = None

    if bolsai_api_key:
        try:
            result = _BolsaiHTTPHarvester(api_key=bolsai_api_key).fetch(
                _build_bolsai_target(symbol)
            )
            fund = result.fundamentals
            if fund.close_price is not None:
                price = fund.close_price
                fetched.append("price")
            if fund.market_cap is not None:
                market_cap = fund.market_cap
                fetched.append("market_cap")
            if fund.dividend_yield is not None:
                financials["dividend_yield"] = fund.dividend_yield
                fetched.append("dividend_yield")
            # Per-share and multiple figures: not read by EquityAnalyzer, they
            # feed the valuation catalog (iip.portfolio_data.valuation_methods,
            # e.g. Graham needs lpa and vpa). Stored under names that can't be
            # confused with "patrimônio líquido" (bolsai calls P/L just "pl").
            bolsai_valuation_inputs = (
                ("lpa", fund.lpa),
                ("vpa", fund.vpa),
                ("price_to_earnings", fund.pl),
                ("price_to_book", fund.pvp),
            )
            for field_name, value in bolsai_valuation_inputs:
                if value is not None:
                    financials[field_name] = value
                    fetched.append(field_name)
            if any(value is not None for _, value in bolsai_valuation_inputs):
                warnings.append(
                    "lpa/vpa/price_to_earnings/price_to_book vêm do bolsai na base "
                    "dele (último balanço/janela móvel), que pode diferir do ano "
                    "fiscal da DFP usada nos demais campos."
                )
        except Exception as exc:  # noqa: BLE001 — bolsai é opcional; qualquer falha aqui não deve impedir o template de ser gerado
            warnings.append(f"não consegui buscar fundamentos via bolsai: {exc}")
    elif brapi_token:
        try:
            result = _BrapiHTTPHarvester(token=brapi_token).fetch(
                _build_brapi_target((symbol,))
            )
            if result.quotes:
                price = result.quotes[0].regular_market_price
                fetched.append("price")
        except Exception as exc:  # noqa: BLE001 — brapi é opcional; qualquer falha aqui não deve impedir o template de ser gerado
            warnings.append(f"não consegui buscar preço via brapi.dev: {exc}")
    else:
        warnings.append(
            "Nem IIP_BOLSAI_API_KEY nem IIP_BRAPI_TOKEN configurados — "
            "nenhum dado de preço buscado."
        )

    def _fetch_dfp(target_ano: int):
        result = _CvmDfpHTTPHarvester().fetch(_build_cvm_dfp_target(target_ano))
        return _extract_dfp_fundamentals(
            target_ano,
            cnpj,
            bpa_con=result.bpa_con,
            bpa_ind=result.bpa_ind,
            bpp_con=result.bpp_con,
            bpp_ind=result.bpp_ind,
            dre_con=result.dre_con,
            dre_ind=result.dre_ind,
        )

    current = None
    try:
        current = _fetch_dfp(ano)
    except Exception as exc:  # noqa: BLE001 — DFP é opcional; qualquer falha aqui não deve impedir o template de ser gerado
        warnings.append(f"não consegui buscar DFP da CVM para {ano}: {exc}")

    if current is None:
        warnings.append(
            f"Nenhum registro DFP encontrado na CVM para o CNPJ {cnpj} em {ano} — "
            "equity/net_income/revenue/ebit/invested_capital continuam nos "
            "valores-padrão."
        )
    else:
        if current.patrimonio_liquido is not None:
            financials["equity"] = current.patrimonio_liquido
            fetched.append("equity")
        if current.lucro_liquido is not None:
            financials["net_income"] = current.lucro_liquido
            fetched.append("net_income")
        if current.receita is not None:
            financials["revenue"] = current.receita
            fetched.append("revenue")
        else:
            warnings.append(
                "Receita (linha padrão CVM 3.01) veio zerada — provável holding "
                "cujo resultado vem de equivalência patrimonial, não de receita "
                "operacional direta (confirmado ao vivo: BBSE3, CXSE3); revenue "
                "e EBIT Margin continuam no valor-padrão."
            )
        if current.ebit is not None:
            financials["ebit"] = current.ebit
            fetched.append("ebit")
        else:
            warnings.append(
                "EBIT não encontrado — esperado para bancos/instituições "
                "financeiras (confirmado ao vivo: ABCB4), que não separam "
                "resultado financeiro do restante da operação; ebit e ROIC "
                "continuam no valor-padrão."
            )
        if current.patrimonio_liquido is not None and current.passivo_nao_circulante is not None:
            financials["invested_capital"] = round(
                current.patrimonio_liquido + current.passivo_nao_circulante, 2
            )
            fetched.append("invested_capital")

        resilience = (
            ("current_ratio", current.current_ratio),
            ("debt_to_equity", current.debt_to_equity),
            ("interest_coverage", current.interest_coverage),
        )
        for field_name, value in resilience:
            if value is not None:
                financials[field_name] = value
                fetched.append(field_name)
        missing = [name for name, value in resilience if value is None]
        if missing:
            warnings.append(
                f"{'/'.join(missing)} não derivável(is) do balanço padrão da "
                "CVM (esperado para bancos/seguradoras, ou quando a dívida "
                "financeira não aparece nas linhas padrão) — continuam no "
                "valor-padrão."
            )

    ano_base = ano - 3
    baseline = None
    try:
        baseline = _fetch_dfp(ano_base)
    except Exception as exc:  # noqa: BLE001 — crescimento 3y é opcional; qualquer falha aqui não deve impedir o restante do template
        warnings.append(
            f"não consegui buscar DFP da CVM de {ano_base} (para crescimento 3y): {exc}"
        )

    if current is not None and baseline is not None:
        rg = _cagr_pct(baseline.receita, current.receita, 3)
        if rg is not None:
            financials["revenue_growth_3y"] = rg
            fetched.append("revenue_growth_3y")
        eg = _cagr_pct(baseline.lucro_liquido, current.lucro_liquido, 3)
        if eg is not None:
            financials["earnings_growth_3y"] = eg
            fetched.append("earnings_growth_3y")
        bg = _cagr_pct(baseline.patrimonio_liquido, current.patrimonio_liquido, 3)
        if bg is not None:
            financials["book_value_growth_3y"] = bg
            fetched.append("book_value_growth_3y")
        if any(v is not None for v in (rg, eg, bg)):
            warnings.append(
                f"Crescimento 3y = CAGR real {ano_base}->{ano} via CVM — pode "
                "refletir fusão/aquisição/reestruturação societária, não só "
                "crescimento orgânico (ex.: ALOS3 nasceu de uma fusão em 2023); "
                "cheque a origem antes de usar para decisão de investimento."
            )
    elif current is not None:
        warnings.append(
            f"Sem dado DFP de {ano_base} para calcular crescimento 3y — "
            "revenue/earnings/book_value_growth_3y continuam no valor-padrão."
        )

    warnings.append(
        "Campos qualitativos/de julgamento (moat, governança, gestão, poder "
        "de precificação, WACC, fluxo de caixa detalhado etc.) continuam com os valores-padrão do analisador — não são "
        "derivados de demonstrações financeiras estruturadas."
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


def _equity_defaults() -> dict[str, Any]:
    from iip.analysis import EquityAnalyzer
    from iip.cli.main import _template_financials

    return _template_financials(EquityAnalyzer)


def fetch_fiagro_template_live(
    symbol: str,
    cnpj: str,
    ano: int,
    mes: int,
    brapi_token: str | None = None,
) -> tuple[dict[str, Any], FetchResult]:
    """Fill what's honestly fillable for a FIAGRO fund from CVM's own
    Informe Mensal FIAGRO, plus price via brapi.dev when configured.

    Correction from this module's earlier version (12/09/2026): the
    original docstring claimed FIAGRO funds like CRAA11 "aren't traded
    on B3 with a market ticker" — that was WRONG, found live when a
    real run against 2026 data hit a genuine gap: CRAA11's CNPJ
    (confirmed correct against six independent public sources —
    Kinvo, Investidor10, Rei dos Dividendos, Funds Explorer, Sparta's
    own site, iValor — and confirmed NOT a "too new to report" case,
    operating since 2023) does not appear in CVM's FIAGRO Informe
    Mensal for August/2026 either, even though the file itself
    downloads fine (not a publication-lag 404 like the current month
    gives). The reason for that specific gap is still unexplained —
    but those same public sources show CRAA11 trading actively on B3
    with a real price (~R$88-102 across recent months), so at minimum
    price IS fetchable here, unlike the true no-ticker case
    (fixed_income/AXIA3).

    ``AgroAnalyzer`` (confirmed by reading its own
    ``analyze-template`` output) has NO assets-under-management field
    at all, so patrimônio still can't be mapped even when the CVM
    lookup succeeds. ``dividend_yield_pct`` fetch logic (with FIAGRO's
    own ``Dividend_Yield_Mes`` scale — already a plain monthly percent,
    confirmed live, unlike CVM FII's fraction-based field) is
    unchanged from before; it simply won't fill for CNPJs the CVM
    dataset doesn't have, which is reported as a warning, not an
    error — the command still succeeds with whatever price data brapi
    provides.
    """
    from iip.sources.b3_brapi import build_target as _build_brapi_target
    from iip.sources.b3_brapi_harvester import BrapiHTTPHarvester as _BrapiHTTPHarvester
    from iip.sources.cvm_fiagro import build_target as _build_cvm_fiagro_target
    from iip.sources.cvm_fiagro_harvester import (
        CvmFiagroHTTPHarvester as _CvmFiagroHTTPHarvester,
    )

    result = _CvmFiagroHTTPHarvester().fetch(_build_cvm_fiagro_target(ano, mes))

    normalized_cnpj = "".join(ch for ch in cnpj if ch.isdigit())
    matches = [
        i
        for i in result.informes
        if "".join(ch for ch in i.cnpj_classe if ch.isdigit()) == normalized_cnpj
    ]

    default_financials = _agro_defaults()
    financials = dict(default_financials)
    fetched: list[str] = []
    warnings: list[str] = []

    if not matches:
        warnings.append(
            f"Nenhum registro CVM FIAGRO encontrado para o CNPJ {cnpj} no "
            f"mês {ano}-{mes:02d} — CNPJ pode estar certo mesmo assim (confirme "
            "em fontes públicas como Investidor10/Kinvo) e o fundo genuinamente "
            "não aparecer nesse dataset da CVM por um motivo ainda não identificado."
        )
    else:
        ordenados = sorted(matches, key=lambda i: i.data_referencia, reverse=True)
        ultimos = ordenados[:12]
        valores_dy = [
            i.valores.get("Dividend_Yield_Mes")
            for i in ultimos
            if i.valores.get("Dividend_Yield_Mes") is not None
        ]
        if valores_dy:
            financials["dividend_yield_pct"] = round(sum(valores_dy), 4)
            fetched.append("dividend_yield_pct")
            if len(valores_dy) < 12:
                warnings.append(
                    f"dividend_yield_pct calculado com apenas {len(valores_dy)} "
                    "mes(es) disponível(is), não os 12 meses completos (TTM parcial)."
                )

    price: float | None = None
    if brapi_token:
        try:
            brapi_result = _BrapiHTTPHarvester(token=brapi_token).fetch(
                _build_brapi_target((symbol,))
            )
            if brapi_result.quotes:
                price = brapi_result.quotes[0].regular_market_price
                fetched.append("price")
        except Exception as exc:  # noqa: BLE001 — preço é opcional, mesmo padrão do fetch-template atual
            warnings.append(f"não consegui buscar preço via brapi.dev: {exc}")
    else:
        warnings.append(
            "IIP_BRAPI_TOKEN não definida — pulando busca de preço."
        )

    warnings.append(
        "AgroAnalyzer não tem campo de patrimônio/AUM — só "
        "dividend_yield_pct (via CVM) e price (via brapi.dev) são "
        "buscáveis aqui."
    )

    template = {
        "symbol": symbol.upper(),
        "sector": "REPLACE_WITH_SECTOR",
        "industry": "REPLACE_WITH_INDUSTRY",
        "market_cap": None,
        "price": price,
        "financials": financials,
    }

    return template, FetchResult(
        fetched_fields=tuple(fetched),
        dividend_yield_months_used=len(valores_dy) if matches and valores_dy else 0,
        warnings=tuple(warnings),
    )


def _agro_defaults() -> dict[str, Any]:
    from iip.analysis import AgroAnalyzer
    from iip.cli.main import _template_financials

    return _template_financials(AgroAnalyzer)


def fetch_fixed_income_template_live(
    symbol: str,
    cnpj: str,
    ano: int,
    mes: int,
) -> tuple[dict[str, Any], FetchResult]:
    """CVM Informe Diário only (patrimônio/cota) — deliberately NEVER
    attempts a market price lookup, unlike the FII/ETF live-fetch
    functions.

    Reason: found live with AXIA3 (Daycoval FMP-FGTS Eletrobras) — the
    ``symbol`` a person's portfolio tool uses to label this kind of
    position is sometimes a proxy/reference ticker for a DIFFERENT,
    unrelated real asset (AXIA3 is Eletrobras' own common-share
    ticker), not the fund's own market ticker (FMP-FGTS funds have no
    B3 ticker at all — they're only accessible via FGTS, not a regular
    brokerage). Calling brapi/bolsai with that symbol would silently
    fetch and misattribute a different company's stock price to this
    position. Safer to fetch only what CVM's CNPJ-keyed data can
    honestly confirm, and leave price fields at their defaults with a
    clear warning, than to guess which symbol (if any) is safe to
    query for price.
    """
    from iip.sources.cvm_renda_fixa import (
        build_diario_target as _build_cvm_diario_target,
    )
    from iip.sources.cvm_renda_fixa_harvester import (
        CvmRendaFixaHTTPHarvester as _CvmRendaFixaHTTPHarvester,
    )

    diario_result = _CvmRendaFixaHTTPHarvester().fetch_diario(
        _build_cvm_diario_target(ano, mes)
    )

    default_financials = _fixed_income_defaults()
    template, resultado = build_etf_template(
        symbol=symbol,
        cnpj=cnpj,
        informes=list(diario_result.informes),
        default_financials=default_financials,
        price=None,
    )
    resultado = FetchResult(
        fetched_fields=resultado.fetched_fields,
        dividend_yield_months_used=resultado.dividend_yield_months_used,
        warnings=(
            *resultado.warnings,
            (
                "Preço de mercado não buscado de propósito para este ativo "
                "(fixed_income) — o ticker de referência pode não corresponder "
                "a um ticker de mercado real deste fundo. Preencha manualmente "
                "se souber o valor."
            ),
        ),
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
    from iip.sources.cvm_renda_fixa import (
        build_diario_target as _build_cvm_diario_target,
    )
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
        except Exception as exc:  # noqa: BLE001 — mesmo motivo do bolsai acima: preço é opcional
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


def _fixed_income_defaults() -> dict[str, Any]:
    from iip.analysis import FixedIncomeAnalyzer
    from iip.cli.main import _template_financials

    return _template_financials(FixedIncomeAnalyzer)


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
