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
        warnings.append(
            "Preço não informado/buscado — reit_premium_discount e market_cap ficam vazios."
        )

    sector = "REPLACE_WITH_SECTOR"
    if geral:
        cnpj_normalizado = "".join(ch for ch in cnpj if ch.isdigit())
        geral_matches = [
            g
            for g in geral
            if "".join(ch for ch in g.cnpj_fundo_classe if ch.isdigit())
            == cnpj_normalizado
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


def _enrich_fii_with_vacancia_report(
    financials: dict[str, Any], symbol: str
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Best-effort ``occupancy_rate`` and ``avg_lease_term_years`` from the manager's
    own latest report PDF (see ``iip.sources.fii_vacancia`` for the layouts and the
    criterion). Silent no-op for a ticker without a verified layout, like the Pátria
    enrichment -- this runs for every FII.

    Occupancy: the base is the financial vacancy when the report gives it (same as the
    Pátria path); when only the physical one exists it is used but flagged, and a
    number that was calculated instead of read says so. The lease term is filled only
    where the report declares a WALE/WAULT/remaining term (never a total contract
    duration), independent of whether the occupancy layout was recognised.
    """
    from iip.sources.fii_vacancia import profile_for_ticker
    from iip.sources.fii_vacancia_harvester import FiiVacanciaHTTPHarvester

    if profile_for_ticker(symbol) is None:
        return financials, [], []

    try:
        fetched_report = FiiVacanciaHTTPHarvester().fetch(symbol)
    # enriquecimento é best-effort, nunca deve derrubar o template CVM já montado
    except Exception as exc:  # noqa: BLE001
        return (
            financials,
            [],
            [f"não consegui ler o relatório gerencial de {symbol}: {exc}"],
        )

    if fetched_report is None:
        return (
            financials,
            [],
            [
                "relatório gerencial mais recente não encontrado — "
                "occupancy_rate continua no valor-padrão."
            ],
        )

    financials = dict(financials)
    fetched: list[str] = []
    warnings: list[str] = []

    reading = fetched_report.reading
    if reading is None or reading.occupancy_rate is None:
        warnings.append(
            f"o relatório gerencial ({fetched_report.source_url}) não tem o "
            "layout de vacância esperado — occupancy_rate continua no "
            "valor-padrão (layout mudou?)."
        )
    else:
        financials["occupancy_rate"] = reading.occupancy_rate
        fetched.append("occupancy_rate")
        if reading.basis != "financeira":
            warnings.append(
                f"occupancy_rate vem da vacância {reading.basis} do relatório gerencial "
                "(o relatório não informa a financeira, base usada nos fundos da Pátria)."
            )
        if reading.note:
            warnings.append(f"occupancy_rate: {reading.note}")

    lease = fetched_report.lease_term
    if lease is not None:
        financials["avg_lease_term_years"] = lease.years
        fetched.append("avg_lease_term_years")
        warnings.append(
            f'avg_lease_term_years = {lease.years:g} anos, o "{lease.label}" do '
            "relatório gerencial, tratado como WALE (prazo médio remanescente dos "
            "contratos); cada gestora pondera por receita ou por área e a Pátria usa o "
            "WALE dela."
        )
    return financials, fetched, warnings


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
    # enriquecimento é best-effort, nunca deve derrubar o template CVM já montado
    except Exception as exc:  # noqa: BLE001
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


def _fii_valuation_inputs(
    financials: dict[str, Any], fii: Any
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Inputs for the FII valuation catalog (``iip.portfolio_data.valuation_methods``)
    from bolsai's FII record: ``nav_per_share`` (patrimônio por cota),
    ``dividend_yield_ttm`` (12 months, percent) and ``dividend_per_share``.

    Why not the ``dividend_yield`` this template already carries: that one is
    summed from CVM's monthly field over the months of the current year only
    (7 in September, not 12) and the field itself is unreliable (checked live:
    0.0 for funds that distribute -- BTCI11, VGIP11, AFHI11 -- and negative for
    XPML11). bolsai's 12-month figure matches independent numbers (HGCR11:
    12.31% vs 12 x R$ 1.00 / R$ 97.40 from the manager's own sheet).

    Its BASIS is the fund's net asset value per share, not the market price,
    so the income per share is ``dividend_yield_ttm * nav_per_share``.
    ``dividend_yield`` (the analyzer input) is deliberately left untouched.
    """
    fetched: list[str] = []
    warnings: list[str] = []
    if fii is None:
        return financials, fetched, warnings

    financials = dict(financials)
    nav = fii.book_value_per_share
    dy_ttm = fii.dividend_yield_ttm
    if nav is not None and nav > 0:
        financials["nav_per_share"] = round(nav, 4)
        fetched.append("nav_per_share")
    if dy_ttm is not None:
        financials["dividend_yield_ttm"] = dy_ttm
        fetched.append("dividend_yield_ttm")
    if nav is not None and nav > 0 and dy_ttm is not None:
        financials["dividend_per_share"] = round(dy_ttm / 100 * nav, 4)
        fetched.append("dividend_per_share")
    if fetched:
        warnings.append(
            "nav_per_share/dividend_yield_ttm/dividend_per_share vêm do bolsai "
            f"(ref. {fii.reference_date}); o yield de 12 meses é sobre o patrimônio "
            "por cota, então dividend_per_share = yield × VP/cota. O "
            "`dividend_yield` do analisador (CVM, só meses do ano corrente) "
            "não é alterado."
        )
    return financials, fetched, warnings


def nav_preservation_score(change_pct: float) -> float:
    """0-100: a fund whose net asset value per share held or grew over 12 months
    scores 100; each -1% costs 20 points, so -5% or worse scores 0."""
    if change_pct >= 0:
        return 100.0
    return round(max(0.0, 100.0 + 20.0 * change_pct), 1)


def nav_change_12m_pct(
    complementos: list[Any], cnpj: str
) -> tuple[float | None, str | None]:
    """(net asset value per share change over 12 months in percent, reason it is
    unavailable). Needs the latest month and the month exactly 12 earlier, and
    refuses when any share amortization was recorded in the window (returned
    capital lowers the NAV per share without being erosion)."""
    digits = "".join(ch for ch in cnpj if ch.isdigit())
    by_month: dict[str, Any] = {}
    for c in sorted(complementos, key=lambda c: (c.data_referencia, c.versao)):
        if "".join(ch for ch in c.cnpj_fundo_classe if ch.isdigit()) == digits:
            by_month[c.data_referencia] = c  # latest version of each month
    if not by_month:
        return None, "sem registros do fundo na CVM"
    months = sorted(by_month)
    latest = months[-1]
    year, month = int(latest[:4]), int(latest[5:7])
    earlier = f"{year - 1:04d}-{month:02d}-01"
    if earlier not in by_month:
        return (
            None,
            f"sem o mês {earlier[:7]} para comparar (12 meses antes de {latest[:7]})",
        )
    window = [m for m in months if earlier < m <= latest]
    if any(
        (by_month[m].valores.get("Percentual_Amortizacao_Cotas_Mes") or 0) > 0
        for m in window
    ):
        return (
            None,
            "houve amortização de cotas na janela (capital devolvido, não erosão)",
        )
    now = by_month[latest].valores.get("Valor_Patrimonial_Cotas")
    ago = by_month[earlier].valores.get("Valor_Patrimonial_Cotas")
    if not now or not ago or ago <= 0:
        return None, "patrimônio por cota ausente em um dos extremos"
    return round((now / ago - 1) * 100, 2), None


def _fii_dividend_pillar_inputs(
    financials: dict[str, Any],
    cnpj: str,
    complementos: list[Any],
    load_previous_year: Any,
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Inputs the recalibrated FII dividends pillar needs:
    ``risk_free_real_yield`` (long NTN-B, percent) and a real
    ``payout_sustainability_score`` from the NAV-per-share trend (replacing the
    constant default 80)."""
    from iip.sources.tesouro_direto_harvester import long_ntnb_rate_cached

    financials = dict(financials)
    fetched: list[str] = []
    warnings: list[str] = []

    try:
        rate = long_ntnb_rate_cached()
    except Exception as exc:  # noqa: BLE001 — a taxa é consulta de mercado opcional
        rate = None
        warnings.append(f"não consegui buscar a taxa da NTN-B: {exc}")
    if rate is not None:
        financials["risk_free_real_yield"] = round(rate.real_yield * 100, 4)
        fetched.append("risk_free_real_yield")
        warnings.append(
            f"risk_free_real_yield = NTN-B longa (venc. {rate.maturity:%d/%m/%Y}, ref. "
            f"{rate.reference_date:%d/%m/%Y}): o pilar de dividendos pontua o yield "
            "relativo a ela (o dobro dela = nota máxima)."
        )
    else:
        warnings.append(
            "sem a taxa da NTN-B: o pilar de dividendos usa a calibração antiga "
            "(yield fixo, satura em 8,3%)."
        )

    all_complementos = list(complementos)
    try:
        all_complementos += list(load_previous_year())
    # o ano anterior é opcional; sem ele a tendência do VP pode ficar indisponível
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"não consegui buscar o informe CVM do ano anterior: {exc}")
    change, reason = nav_change_12m_pct(all_complementos, cnpj)
    if change is not None:
        financials["nav_change_12m_pct"] = change
        financials["payout_sustainability_score"] = nav_preservation_score(change)
        fetched += ["nav_change_12m_pct", "payout_sustainability_score"]
        warnings.append(
            f"payout_sustainability_score = preservação do patrimônio por cota em 12 "
            f"meses ({change:+.1f}%): proxy, não medida direta — inclui reavaliação de "
            "imóveis; 100 se o VP não caiu, 0 se caiu 5% ou mais."
        )
    else:
        warnings.append(
            f"payout_sustainability_score continua no valor-padrão (80): {reason}."
        )
    return financials, fetched, warnings


def _use_ttm_dividend_yield(
    financials: dict[str, Any], fii: Any
) -> tuple[dict[str, Any], bool, str | None]:
    """Set the analyzer's ``dividend_yield`` to bolsai's 12-month figure.

    The value this template used to carry is summed from CVM's monthly
    ``Percentual_Dividend_Yield_Mes`` over the months of the CURRENT year only
    (7 in September, so it read as a partial year) and that CVM field is itself
    unreliable (checked live: 0.0 for funds that distribute -- BTCI11, VGIP11,
    AFHI11 -- and negative for XPML11). bolsai's 12-month yield matches
    independent data (HGCR11: 12.31% vs 12 x R$ 1.00 / R$ 97.40 from the
    manager's sheet) and uses the same basis (net asset value per share) and unit
    (annual percent) the analyzer expects. Without it the CVM value stays, as
    before.
    """
    if fii is None or fii.dividend_yield_ttm is None:
        return financials, False, None
    financials = dict(financials)
    financials["dividend_yield"] = fii.dividend_yield_ttm
    return (
        financials,
        True,
        "dividend_yield = TTM de 12 meses do bolsai (sobre o patrimônio por cota, "
        f"ref. {fii.reference_date}); substitui o valor somado da CVM, que cobria só "
        "os meses do ano corrente e é pouco confiável (0 em fundos que distribuem).",
    )


def fetch_fii_template_live(
    symbol: str,
    cnpj: str,
    ano: int,
    bolsai_api_key: str | None,
    *,
    analysis_inputs: bool = True,
) -> tuple[dict[str, Any], FetchResult]:
    """Do the real network fetch (CVM FII + optional bolsai price) and
    assemble the FII template. Raises whatever the CVM harvester raises
    on failure — that's a hard stop, there's no FII data to build a
    template from without it. A bolsai failure is NOT raised — it's
    folded into the returned FetchResult.warnings, since price is
    optional (the CVM-only fields still get filled).

    ``analysis_inputs=False`` skips what only ``FIIAnalyzer`` reads -- the Pátria
    spreadsheet enrichment (5 file downloads for their funds), the previous-year
    CVM file and the NAV trend -- for callers that only value the fund
    (``value-portfolio``); the price/NAV/yield inputs valuation needs stay.

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
    from iip.sources.cvm_fii_harvester import active_fii_cache as _active_fii_cache

    fii_harvester = _active_fii_cache() or _CvmFiiHTTPHarvester()
    cvm_result = fii_harvester.fetch(_build_cvm_fii_target(ano))

    price = None
    bolsai_fii = None
    bolsai_warning = None
    if bolsai_api_key:
        try:
            bolsai_result = _BolsaiHTTPHarvester(api_key=bolsai_api_key).fetch_fii(
                _build_bolsai_fii_target(symbol)
            )
            price = bolsai_result.fii.close_price
            bolsai_fii = bolsai_result.fii
        # preço é opcional; qualquer falha aqui (rede, JSON, o que for) não deve derrubar os dados da CVM já obtidos
        except Exception as exc:  # noqa: BLE001
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
    if analysis_inputs:
        enriched_financials, patria_fetched, patria_warnings = (
            _enrich_fii_with_patria_fundamentos(template["financials"], symbol)
        )
        template["financials"] = enriched_financials
        if "occupancy_rate" not in patria_fetched:
            vacancia_financials, vacancia_fetched, vacancia_warnings = (
                _enrich_fii_with_vacancia_report(template["financials"], symbol)
            )
            template["financials"] = vacancia_financials
            patria_fetched = [*patria_fetched, *vacancia_fetched]
            patria_warnings = [*patria_warnings, *vacancia_warnings]
    else:
        patria_fetched, patria_warnings = [], []

    valuation_financials, valuation_fetched, valuation_warnings = _fii_valuation_inputs(
        template["financials"], bolsai_fii
    )
    template["financials"] = valuation_financials

    # The analyzer's dividend_yield: prefer bolsai's 12-month figure over the
    # one summed from CVM's current-year months (see _use_ttm_dividend_yield).
    ttm_financials, ttm_used, ttm_warning = _use_ttm_dividend_yield(
        template["financials"], bolsai_fii
    )
    template["financials"] = ttm_financials
    base_warnings = resultado.warnings
    base_fetched = resultado.fetched_fields
    months_used = resultado.dividend_yield_months_used
    if ttm_used:
        base_warnings = tuple(
            w
            for w in base_warnings
            if not w.startswith("dividend_yield calculado com apenas")
        )
        if "dividend_yield" not in base_fetched:
            base_fetched = (*base_fetched, "dividend_yield")
        months_used = 12

    # Market rate and NAV preservation for the dividends pillar (see
    # FIIAnalyzer._analyze_fii_dividends). Both best-effort: failures degrade
    # the pillar to its previous calibration and say so.
    if analysis_inputs:
        pillar_financials, pillar_fetched, pillar_warnings = (
            _fii_dividend_pillar_inputs(
                template["financials"],
                cnpj,
                list(cvm_result.complemento),
                lambda: fii_harvester.fetch(_build_cvm_fii_target(ano - 1)).complemento,
            )
        )
        template["financials"] = pillar_financials
    else:
        pillar_fetched, pillar_warnings = [], []

    extra_warnings = (
        *([bolsai_warning] if bolsai_warning else []),
        *patria_warnings,
        *valuation_warnings,
        *([ttm_warning] if ttm_warning else []),
        *pillar_warnings,
    )
    valuation_fetched = [*valuation_fetched, *pillar_fetched]
    patria_fetched = [*patria_fetched, *valuation_fetched]
    if patria_fetched or extra_warnings or ttm_used:
        resultado = FetchResult(
            fetched_fields=(*base_fetched, *patria_fetched),
            dividend_yield_months_used=months_used,
            warnings=(*base_warnings, *extra_warnings),
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
    dfp_harvester: Any = None,
) -> tuple[dict[str, Any], FetchResult]:
    """Fill what's honestly fillable for an equity from real data.

    ``dfp_harvester`` (anything with ``.fetch(target)``) lets a batch share one
    ``CachedCvmDfpHarvester`` so each fiscal year's ~13 MB DFP ZIP is downloaded
    once per run instead of once per equity.

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
    from iip.sources.cvm_dfp import (
        consecutive_dividend_years as _consecutive_dividend_years,
    )
    from iip.sources.cvm_dfp import dividend_history as _dividend_history
    from iip.sources.cvm_dfp import extract_fundamentals as _extract_dfp_fundamentals
    from iip.sources.cvm_dfp_harvester import (
        CvmDfpHTTPHarvester as _CvmDfpHTTPHarvester,
    )
    from iip.sources.cvm_dfp_harvester import active_dfp_cache as _active_dfp_cache

    default_financials = _equity_defaults()
    financials = dict(default_financials)
    fetched: list[str] = []
    warnings: list[str] = []
    price: float | None = None
    market_cap: float | None = None
    shares_outstanding: float | None = None

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
            shares_outstanding = fund.shares_outstanding
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
        # bolsai é opcional; qualquer falha aqui não deve impedir o template de ser gerado
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"não consegui buscar fundamentos via bolsai: {exc}")
    elif brapi_token:
        try:
            result = _BrapiHTTPHarvester(token=brapi_token).fetch(
                _build_brapi_target((symbol,))
            )
            if result.quotes:
                price = result.quotes[0].regular_market_price
                fetched.append("price")
        # brapi é opcional; qualquer falha aqui não deve impedir o template de ser gerado
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"não consegui buscar preço via brapi.dev: {exc}")
    else:
        warnings.append(
            "Nem IIP_BOLSAI_API_KEY nem IIP_BRAPI_TOKEN configurados — "
            "nenhum dado de preço buscado."
        )

    harvester = dfp_harvester or _active_dfp_cache() or _CvmDfpHTTPHarvester()
    dfp_by_year: dict[int, Any] = {}

    def _load_dfp(target_ano: int):
        # one download per fiscal year within this call (the current-year and
        # dividend-history passes both need some of the same years)
        if target_ano not in dfp_by_year:
            dfp_by_year[target_ano] = harvester.fetch(_build_cvm_dfp_target(target_ano))
        return dfp_by_year[target_ano]

    def _fetch_dfp(target_ano: int):
        result = _load_dfp(target_ano)
        return _extract_dfp_fundamentals(
            target_ano,
            cnpj,
            bpa_con=result.bpa_con,
            bpa_ind=result.bpa_ind,
            bpp_con=result.bpp_con,
            bpp_ind=result.bpp_ind,
            dre_con=result.dre_con,
            dre_ind=result.dre_ind,
            dfc_con=result.dfc_con,
            dfc_ind=result.dfc_ind,
        )

    current = None
    try:
        current = _fetch_dfp(ano)
    # DFP é opcional; qualquer falha aqui não deve impedir o template de ser gerado
    except Exception as exc:  # noqa: BLE001
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
        if (
            current.patrimonio_liquido is not None
            and current.passivo_nao_circulante is not None
        ):
            financials["invested_capital"] = round(
                current.patrimonio_liquido + current.passivo_nao_circulante, 2
            )
            fetched.append("invested_capital")

        if current.dividendos_pagos is not None:
            if shares_outstanding:
                financials["dividend_per_share"] = round(
                    current.dividendos_pagos / shares_outstanding, 4
                )
                fetched.append("dividend_per_share")
                # bolsai's stock endpoint carries no dividend_yield (always
                # None, confirmed live), so the analyzer's dividends pillar had
                # only its default. Derive it here -- as a PERCENT number, the
                # unit EquityAnalyzer scores (dy * 15) -- unless bolsai did
                # provide one.
                if "dividend_yield" not in fetched and price:
                    financials["dividend_yield"] = round(
                        financials["dividend_per_share"] / price * 100, 4
                    )
                    fetched.append("dividend_yield")
                warnings.append(
                    "dividend_per_share = dividendos e JCP PAGOS no ano fiscal "
                    f"{ano} (DFC da CVM) ÷ total de ações de todas as classes "
                    "(bolsai): média entre classes e caixa pago no ano, não o "
                    "declarado — proventos extraordinários entram no valor."
                )
            else:
                warnings.append(
                    "Dividendos pagos encontrados na DFC, mas o número de ações "
                    "(bolsai) não está disponível — dividend_per_share não calculado."
                )
        else:
            warnings.append(
                "Dividendos pagos não encontrados na DFC (esperado para alguns "
                "bancos) — dividend_per_share não calculado."
            )

        payout = current.payout_ratio_pct
        if payout is not None:
            financials["payout_ratio"] = payout
            fetched.append("payout_ratio")
            warnings.append(
                "payout_ratio = dividendos e JCP PAGOS no ano fiscal ÷ lucro "
                "líquido do mesmo ano (em %): pode passar de 100% quando a "
                "empresa distribui lucros de anos anteriores."
            )
        elif current.dividendos_pagos is not None:
            warnings.append(
                "payout_ratio não calculado: lucro líquido do ano ausente ou "
                "não positivo (payout sobre prejuízo não tem sentido)."
            )

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
    # crescimento 3y é opcional; qualquer falha aqui não deve impedir o restante do template
    except Exception as exc:  # noqa: BLE001
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

    if current is not None:
        # Years of dividend history: each year is read from ITS OWN DFP file
        # (see cvm_dfp.dividend_history for why the prior-year comparative
        # column is not used). A 5-year window is 5 files (ano and ano-3 are
        # already loaded above); in a batch they come from the shared cache.
        history: dict[int, float] = {}
        for history_ano in range(ano, ano - 5, -1):
            try:
                loaded = _load_dfp(history_ano)
            # histórico é opcional; falha aqui não derruba o restante do template
            except Exception as exc:  # noqa: BLE001
                warnings.append(
                    f"não consegui buscar DFP da CVM de {history_ano} (para histórico de dividendos): {exc}"
                )
                continue
            for year, value in _dividend_history(
                cnpj, dfc_con=loaded.dfc_con, dfc_ind=loaded.dfc_ind
            ).items():
                history[year] = value

        streak = _consecutive_dividend_years(history, ano, window=5)
        if streak is not None:
            financials["dividend_consistency_years"] = streak
            fetched.append("dividend_consistency_years")
            warnings.append(
                f"dividend_consistency_years = anos consecutivos (até {ano}) com "
                "dividendos/JCP pagos > 0, numa janela de no máximo 5 anos"
                + (" — 5 significa 'pelo menos 5'." if streak >= 5 else ".")
            )
            broken_year = ano - streak
            if (
                streak < 5
                and history.get(broken_year) == 0.0
                and any(
                    history.get(y, 0.0) > 0 for y in range(broken_year - 1, ano - 5, -1)
                )
            ):
                warnings.append(
                    f"dividend_consistency_years parou em {broken_year}, ano com "
                    "dividendos = 0 na DFC, mas há anos anteriores pagantes na "
                    "janela — confira: pode ser suspensão real ou só classificação "
                    "diferente do fluxo de caixa (ex.: bancos lançam JCP/dividendos "
                    "fora do financiamento; confirmado ao vivo no ABCB4)."
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


def _fetch_month_with_fallback(
    fetch: Any,
    build_target: Any,
    ano: int,
    mes: int,
    label: str,
    *,
    max_months_back: int = 2,
) -> tuple[Any, str | None]:
    """Fetch a CVM dataset published monthly, stepping back up to
    ``max_months_back`` months while the requested one is not published yet
    (HTTP 404 -- CVM lags at the start of every month). Any other HTTP error, or a
    404 on the last attempt, propagates. Returns the result and a warning naming the
    month actually used (``None`` when the requested month was available)."""
    from urllib.error import HTTPError

    ano_try, mes_try = ano, mes
    for attempt in range(max_months_back + 1):
        try:
            result = fetch(build_target(ano_try, mes_try))
        except HTTPError as exc:
            if exc.code != 404 or attempt == max_months_back:
                raise
            ano_try, mes_try = (
                (ano_try - 1, 12) if mes_try == 1 else (ano_try, mes_try - 1)
            )
            continue
        break
    warning = (
        f"{label} de {ano}-{mes:02d} ainda não publicado pela CVM; "
        f"usando {ano_try}-{mes_try:02d}."
        if (ano_try, mes_try) != (ano, mes)
        else None
    )
    return result, warning


def fetch_fiagro_template_live(
    symbol: str,
    cnpj: str,
    ano: int,
    mes: int,
    brapi_token: str | None = None,
    bolsai_api_key: str | None = None,
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

    result, fallback_warning = _fetch_month_with_fallback(
        _CvmFiagroHTTPHarvester().fetch,
        _build_cvm_fiagro_target,
        ano,
        mes,
        "Informe FIAGRO",
    )

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
    if fallback_warning:
        warnings.append(fallback_warning)

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
        # preço é opcional, mesmo padrão do fetch-template atual
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"não consegui buscar preço via brapi.dev: {exc}")
    else:
        warnings.append("IIP_BRAPI_TOKEN não definida — pulando busca de preço.")

    # Valuation inputs (NAV per share, 12-month yield) -- bolsai serves FIAGROs from
    # its FII endpoint, so this is the same lookup the FII valuation uses (CRAA11 is
    # absent from CVM's FIAGRO dataset, so CVM cannot provide the NAV). Opt-in: only
    # when a key is passed, so refresh-portfolio's quota use is unchanged.
    if bolsai_api_key:
        from iip.sources.b3_bolsai import build_fii_target as _build_bolsai_fii_target
        from iip.sources.b3_bolsai_harvester import (
            BolsaiHTTPHarvester as _BolsaiHTTPHarvester,
        )

        try:
            bolsai_result = _BolsaiHTTPHarvester(api_key=bolsai_api_key).fetch_fii(
                _build_bolsai_fii_target(symbol)
            )
            financials, val_fetched, val_warnings = _fii_valuation_inputs(
                financials, bolsai_result.fii
            )
            fetched.extend(val_fetched)
            warnings.extend(val_warnings)
        # opcional, mesmo padrão do preço via brapi
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"não consegui buscar NAV/yield via bolsai: {exc}")

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
    brapi_token: str | None = None,
) -> tuple[dict[str, Any], FetchResult]:
    """CVM Informe Diário (patrimônio/cota) — a market price lookup is
    opt-in: it only happens when the caller passes ``brapi_token``, and the
    caller must only do so for a fund whose ``symbol`` is really its own B3
    ticker (listed FI-Infra: CDII11, JURO11, CPTI11). ``refresh-portfolio``
    never passes it. Without the token this NEVER attempts a price lookup,
    unlike the FII/ETF live-fetch functions.

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

    diario_result, diario_warning = _fetch_month_with_fallback(
        _CvmRendaFixaHTTPHarvester().fetch_diario,
        _build_cvm_diario_target,
        ano,
        mes,
        "Informe Diário",
    )

    price = None
    price_warning = None
    if brapi_token:
        from iip.sources.b3_brapi import build_target as _build_brapi_target
        from iip.sources.b3_brapi_harvester import (
            BrapiHTTPHarvester as _BrapiHTTPHarvester,
        )

        try:
            brapi_result = _BrapiHTTPHarvester(token=brapi_token).fetch(
                _build_brapi_target((symbol,))
            )
            if brapi_result.quotes:
                price = brapi_result.quotes[0].regular_market_price
        except Exception as exc:  # noqa: BLE001 — preço é opcional, mesmo padrão do ETF
            price_warning = f"não consegui buscar preço via brapi.dev: {exc}"

    default_financials = _fixed_income_defaults()
    template, resultado = build_etf_template(
        symbol=symbol,
        cnpj=cnpj,
        informes=list(diario_result.informes),
        default_financials=default_financials,
        price=price,
    )

    fetched = list(resultado.fetched_fields)
    extra: list[str] = []
    # Input of the NAV valuation method (not a FixedIncomeAnalyzer field): the fund's
    # last published cota, which lags the market price by the CVM publication delay.
    latest = latest_informe_for_cnpj(list(diario_result.informes), cnpj)
    if latest is not None and latest.valor_cota is not None and latest.valor_cota > 0:
        template["financials"]["nav_per_share"] = round(latest.valor_cota, 4)
        fetched.append("nav_per_share")
        extra.append(
            f"nav_per_share = cota de {latest.data_competencia} (Informe Diário da CVM), "
            "defasada em relação ao preço de mercado."
        )
    if diario_warning:
        extra.append(diario_warning)
    if price_warning:
        extra.append(price_warning)
    if not brapi_token:
        extra.append(
            "Preço de mercado não buscado de propósito para este ativo "
            "(fixed_income) — o ticker de referência pode não corresponder "
            "a um ticker de mercado real deste fundo. Preencha manualmente "
            "se souber o valor."
        )
    resultado = FetchResult(
        fetched_fields=tuple(fetched),
        dividend_yield_months_used=resultado.dividend_yield_months_used,
        warnings=(*resultado.warnings, *extra),
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

    diario_result, diario_warning = _fetch_month_with_fallback(
        _CvmRendaFixaHTTPHarvester().fetch_diario,
        _build_cvm_diario_target,
        ano,
        mes,
        "Informe Diário",
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
        # mesmo motivo do bolsai acima: preço é opcional
        except Exception as exc:  # noqa: BLE001
            brapi_warning = f"não consegui buscar preço via brapi.dev: {exc}"

    default_financials = _etf_defaults()
    template, resultado = build_etf_template(
        symbol=symbol,
        cnpj=cnpj,
        informes=list(diario_result.informes),
        default_financials=default_financials,
        price=price,
    )
    template, investo_fetched, investo_warnings = _enrich_etf_with_investo(
        template, symbol, cnpj, price, resultado.fetched_fields
    )
    extra_warnings = tuple(
        w for w in (diario_warning, brapi_warning, *investo_warnings) if w
    )
    base_warnings = resultado.warnings
    if "assets_under_management_millions" in investo_fetched:
        # o aviso genérico diz que o PL vem de um mês de Informe Diário; aqui vem do Investo
        base_warnings = tuple(
            w
            for w in base_warnings
            if not w.startswith("assets_under_management_millions vem de um único mês")
        )
    if extra_warnings or investo_fetched:
        resultado = FetchResult(
            fetched_fields=(*resultado.fetched_fields, *investo_fetched),
            dividend_yield_months_used=resultado.dividend_yield_months_used,
            warnings=(*base_warnings, *extra_warnings),
        )
    return template, resultado


def _enrich_etf_with_investo(
    template: dict[str, Any],
    symbol: str,
    cnpj: str,
    price: float | None,
    already_fetched: tuple[str, ...] = (),
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Best-effort NAV per share (and net assets) from the ETF manager's own page, for
    the ETFs verified in ``iip.sources.investo_etf`` (LFTB11): the CVM Informe Diário does
    not carry them, and without ``nav_per_share`` there is nothing to value them by.

    Silent no-op for any other ticker. Never raises: a failure becomes a warning and the
    template stays as the CVM/brapi path built it. A NAV older than the source's limit is
    not used (and says so). The NAV is D-1 and the brapi price is newer, so the premium
    over NAV carries that lag -- the warning states it.
    """
    from datetime import date

    from iip.sources import investo_etf
    from iip.sources.investo_etf_harvester import InvestoEtfHTTPHarvester

    if not investo_etf.supports(symbol):
        return template, [], []
    harvester = InvestoEtfHTTPHarvester()
    try:
        fetched = harvester.fetch(symbol, expected_cnpj=cnpj)
    # enriquecimento é best-effort, nunca deve derrubar o template já montado
    except Exception as exc:  # noqa: BLE001
        return (
            template,
            [],
            [f"não consegui ler a cota patrimonial de {symbol} no Investo: {exc}"],
        )

    latest = fetched.latest
    # data de calendário (idade do dado), não timestamp
    age_days = (date.today() - latest.date).days  # noqa: DTZ011
    if age_days > investo_etf.MAX_NAV_AGE_DAYS:
        return (
            template,
            [],
            [
                f"a cota patrimonial mais recente do Investo é de {latest.date:%d/%m/%Y} "
                f"({age_days} dias, acima do limite de {investo_etf.MAX_NAV_AGE_DAYS}): "
                "não usada, nav_per_share fica vazio"
            ],
        )

    template = dict(template)
    financials = dict(template.get("financials", {}))
    financials["nav_per_share"] = latest.nav_per_share
    fetched_fields = ["nav_per_share"]
    # o Informe Diário da CVM não traz estes ETFs; só o que ele NÃO preencheu vem do
    # Investo (o PL é o do mesmo dia da cota)
    if "assets_under_management_millions" not in already_fetched and latest.net_assets:
        financials["assets_under_management_millions"] = round(
            latest.net_assets / 1_000_000, 2
        )
        fetched_fields.append("assets_under_management_millions")
    if price is not None and "market_cap" not in already_fetched and latest.net_assets:
        # cotas = PL / NAV; valor de mercado = preço x cotas
        template["market_cap"] = round(
            price * latest.net_assets / latest.nav_per_share, 2
        )
        fetched_fields.append("market_cap")
    financials, analysis_fields, analysis_warnings = _investo_analysis_inputs(
        financials, fetched, harvester, symbol
    )
    fetched_fields.extend(analysis_fields)
    template["financials"] = financials
    warnings = [
        f"nav_per_share = R$ {latest.nav_per_share:.2f}, a cota patrimonial de "
        f"{latest.date:%d/%m/%Y} (D-1) do site oficial da Investo; o preço de mercado "
        "vem do brapi e é mais novo, então o prêmio sobre o NAV carrega essa defasagem."
    ]
    warnings.extend(analysis_warnings)
    return template, fetched_fields, warnings


def _investo_analysis_inputs(
    financials: dict[str, Any], fetched, harvester, symbol: str
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Inputs of ``ETFAnalyzer`` that were sitting at their defaults, from the same
    Investo source (see ``iip.sources.investo_etf``): the expense ratio (read from the
    product sheet), the year's net inflows (ESTIMATED from net assets and NAV per share)
    and the tracking error/difference (CALCULATED from the official ETF x index series,
    the difference from the official table). Each one says in a warning whether it was
    read or derived. The performance table is a separate request: if it fails, the NAV
    the valuation needs is untouched and only the two tracking fields stay at default.
    """
    from iip.sources import investo_etf

    financials = dict(financials)
    fields: list[str] = []
    warnings: list[str] = []

    fee = investo_etf.parse_fee_pct(fetched.product.administration_fee)
    if fee is not None:
        financials["expense_ratio_pct"] = fee
        fields.append("expense_ratio_pct")
        warnings.append(
            f"expense_ratio_pct = {fee:g}%: a taxa de administração e gestão da ficha "
            "do Investo (a taxa global do regulamento pode ser maior)."
        )

    year = fetched.latest.date.year
    inflows = investo_etf.net_inflows_ytd_millions(fetched.points, year)
    if inflows is not None:
        financials["net_inflows_ytd_millions"] = inflows
        fields.append("net_inflows_ytd_millions")
        warnings.append(
            f"net_inflows_ytd_millions = R$ {inflows:,.0f} mi ({year}): ESTIMATIVA "
            "derivada (cotas = PL / cota patrimonial; fluxo = variação de cotas x a cota "
            "do dia), não um número informado pelo fundo."
        )

    try:
        returns = harvester.fetch_returns(symbol)
    # a rentabilidade é um complemento: sem ela o NAV do valuation segue intacto
    except Exception as exc:  # noqa: BLE001
        warnings.append(
            f"não consegui ler a rentabilidade de {symbol} no Investo: {exc}; "
            "tracking_error_pct e tracking_difference_pct ficam no valor-padrão."
        )
        return financials, fields, warnings

    weekly = investo_etf.tracking_error_pct(returns.series)
    if weekly is None:
        warnings.append(
            "a série ETF x índice é curta demais para um tracking error confiável: "
            "tracking_error_pct fica no valor-padrão."
        )
    else:
        financials["tracking_error_pct"] = weekly
        fields.append("tracking_error_pct")
        daily = investo_etf.tracking_error_pct(
            returns.series, window=1, windows=252, min_windows=126
        )
        monthly = investo_etf.tracking_error_pct(
            returns.series, window=21, windows=12, min_windows=6
        )
        others = ", ".join(
            f"{label} {value:g}%"
            for label, value in (("diário", daily), ("mensal", monthly))
            if value is not None
        )
        warnings.append(
            f"tracking_error_pct = {weekly:g}%: CALCULADO, desvio-padrão semanal (janelas "
            "de 5 pregões, últimas 52) da diferença de retorno ETF - índice, anualizado"
            + (
                f" (outras frequências: {others}; a diferença diária reverte, então o "
                "diário exagera)."
                if others
                else "."
            )
        )

    difference = investo_etf.tracking_difference_pct(returns.table)
    if difference is not None:
        financials["tracking_difference_pct"] = difference
        fields.append("tracking_difference_pct")
        since = investo_etf.tracking_difference_pct(returns.table, "lancamento")
        warnings.append(
            f"tracking_difference_pct = {difference:+g} p.p.: ETF - índice no último ano "
            "(tabela oficial)"
            + (f"; desde o lançamento, {since:+g} p.p." if since is not None else ".")
        )
    return financials, fields, warnings


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
        warnings.append("Preço não informado/buscado — market_cap fica vazio.")

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
