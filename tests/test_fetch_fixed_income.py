from iip.cli.fetch_template import fetch_fixed_income_template_live
from iip.sources.cvm_renda_fixa import InformeDiario
from iip.sources.cvm_renda_fixa_harvester import (
    CvmRendaFixaHTTPHarvester,
    FetchedDiario,
)

CNPJ = "45.121.022/0001-48"


def fake_fetch_diario(self, target):
    informes = (
        InformeDiario(
            tipo_fundo_classe="CLASSE FIF/FAPI",
            cnpj_fundo_classe=CNPJ,
            id_subclasse=None,
            data_competencia="2026-08-05",
            valor_total=15_000_000.0,
            valor_cota=1.89,
            patrimonio_liquido=14_800_000.0,
            captacao_dia=0.0,
            resgate_dia=0.0,
            numero_cotistas=4970,
        ),
    )
    return FetchedDiario(target=target, status_code=200, informes=informes)


def test_fetch_fixed_income_never_fetches_price(monkeypatch):
    monkeypatch.setattr(CvmRendaFixaHTTPHarvester, "fetch_diario", fake_fetch_diario)

    template, resultado = fetch_fixed_income_template_live("AXIA3", CNPJ, 2026, 8)

    assert template["price"] is None
    assert "price" not in resultado.fetched_fields
    assert template["market_cap"] is None


def test_fetch_fixed_income_fills_aum_from_cvm(monkeypatch):
    monkeypatch.setattr(CvmRendaFixaHTTPHarvester, "fetch_diario", fake_fetch_diario)

    template, resultado = fetch_fixed_income_template_live("AXIA3", CNPJ, 2026, 8)

    assert template["financials"]["assets_under_management_millions"] == 14.8
    assert "assets_under_management_millions" in resultado.fetched_fields


def test_fetch_fixed_income_warns_about_no_price_lookup(monkeypatch):
    monkeypatch.setattr(CvmRendaFixaHTTPHarvester, "fetch_diario", fake_fetch_diario)

    _, resultado = fetch_fixed_income_template_live("AXIA3", CNPJ, 2026, 8)

    assert any(
        "Preço de mercado não buscado de propósito" in w for w in resultado.warnings
    )


def test_fetch_fixed_income_uses_fixed_income_analyzer_defaults_not_etf(monkeypatch):
    # Real bug found live (18/09/2026) while promoting real evidence for
    # CPTI11/AXIA3: this function used to default to _etf_defaults()
    # (ETFAnalyzer's field names, e.g. "aum_millions") instead of
    # FixedIncomeAnalyzer's own (e.g. "distribution_yield_pct",
    # "nav_volatility_pct") -- the real assets_under_management_millions
    # value it fetches IS a genuine FixedIncomeAnalyzer field, but every
    # OTHER default in the dict was silently the wrong analyzer's shape,
    # so `iip analyze --type fixed_income` would score against fields
    # FixedIncomeAnalyzer never populated with real data and never see
    # the ones it actually reads.
    from iip.analysis import ETFAnalyzer, FixedIncomeAnalyzer
    from iip.cli.main import _template_financials

    monkeypatch.setattr(CvmRendaFixaHTTPHarvester, "fetch_diario", fake_fetch_diario)

    template, _ = fetch_fixed_income_template_live("AXIA3", CNPJ, 2026, 8)

    fixed_income_fields = set(_template_financials(FixedIncomeAnalyzer))
    etf_only_fields = set(_template_financials(ETFAnalyzer)) - fixed_income_fields

    assert fixed_income_fields <= set(template["financials"])
    assert not (etf_only_fields & set(template["financials"]))


def test_fetch_fixed_income_does_not_call_any_price_provider(monkeypatch):
    # Sanity check: brapi is never instantiated for this asset class.
    # If this function ever started calling it, this guards against
    # someone accidentally wiring a price fetch back in for this asset
    # class without re-reading the AXIA3 warning above.
    from iip.sources.b3_brapi_harvester import BrapiHTTPHarvester

    monkeypatch.setattr(CvmRendaFixaHTTPHarvester, "fetch_diario", fake_fetch_diario)

    def exploding_init(self, *a, **kw):
        raise AssertionError("fetch_fixed_income_template_live must not use brapi")

    monkeypatch.setattr(BrapiHTTPHarvester, "__init__", exploding_init)

    # Should complete without touching BrapiHTTPHarvester at all.
    fetch_fixed_income_template_live("AXIA3", CNPJ, 2026, 8)
