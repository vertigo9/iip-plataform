from urllib.error import HTTPError

from iip.cli.fetch_template import fetch_fiagro_template_live
from iip.sources.b3_brapi import BrapiQuote
from iip.sources.b3_brapi_harvester import BrapiHTTPHarvester, FetchedQuotes
from iip.sources.cvm_fiagro import FiagroInforme
from iip.sources.cvm_fiagro_harvester import CvmFiagroHTTPHarvester, FetchedFiagroReport

CNPJ = "48.903.610/0001-21"


def make_informe(data_referencia, dy_mes=None, cnpj=CNPJ):
    valores = {}
    if dy_mes is not None:
        valores["Dividend_Yield_Mes"] = dy_mes
    return FiagroInforme(
        cnpj_classe=cnpj,
        nome_classe="SPARTA FIAGRO",
        data_referencia=data_referencia,
        versao="1",
        nome_administrador="Sparta",
        cnpj_administrador=None,
        nome_gestor="Sparta",
        cnpj_gestor=None,
        mercado_negociacao=None,
        codigo_isin=None,
        valores=valores,
    )


def fake_fetch(self, target):
    informes = (
        make_informe("2025-06-01", dy_mes=1.2),
        make_informe("2025-07-01", dy_mes=0.9),
        make_informe("2025-08-01", dy_mes=1.59),
    )
    return FetchedFiagroReport(
        target=target, status_code=200, informes=informes, subclasses=()
    )


def test_fetch_fiagro_price_stays_none_without_brapi_token(monkeypatch):
    monkeypatch.setattr(CvmFiagroHTTPHarvester, "fetch", fake_fetch)

    template, resultado = fetch_fiagro_template_live("CRAA11", CNPJ, 2025, 8)

    assert template["price"] is None
    assert template["market_cap"] is None  # nunca preenchido, mesmo com token
    assert "price" not in resultado.fetched_fields


def test_fetch_fiagro_fills_price_via_brapi_when_token_present(monkeypatch):
    # Correcao real (12/09/2026): a suposicao original de que FIAGRO
    # como CRAA11 nao tem ticker de mercado estava errada -- o fundo
    # negocia na B3 de verdade (confirmado com cotacoes reais de
    # varias fontes publicas). So o patrimonio/AUM continua fora do
    # alcance (AgroAnalyzer nao tem esse campo).
    monkeypatch.setattr(CvmFiagroHTTPHarvester, "fetch", fake_fetch)

    def fake_brapi_fetch(self, target):
        return FetchedQuotes(
            target=target,
            status_code=200,
            quotes=(
                BrapiQuote(
                    symbol="CRAA11",
                    short_name="SPARTA FIAGRO",
                    currency="BRL",
                    regular_market_price=91.76,
                    regular_market_change_percent=1.73,
                ),
            ),
        )

    monkeypatch.setattr(BrapiHTTPHarvester, "fetch", fake_brapi_fetch)

    template, resultado = fetch_fiagro_template_live(
        "CRAA11", CNPJ, 2025, 8, "fake-token"
    )

    assert template["price"] == 91.76
    assert template["market_cap"] is None  # continua vazio, nunca estimado
    assert "price" in resultado.fetched_fields


def test_fetch_fiagro_warns_when_no_brapi_token(monkeypatch):
    monkeypatch.setattr(CvmFiagroHTTPHarvester, "fetch", fake_fetch)

    _, resultado = fetch_fiagro_template_live("CRAA11", CNPJ, 2025, 8)

    assert any("IIP_BRAPI_TOKEN não definida" in w for w in resultado.warnings)


def test_fetch_fiagro_continues_when_brapi_fetch_fails(monkeypatch):
    monkeypatch.setattr(CvmFiagroHTTPHarvester, "fetch", fake_fetch)

    def failing_fetch(self, target):
        raise RuntimeError("simulated brapi outage")

    monkeypatch.setattr(BrapiHTTPHarvester, "fetch", failing_fetch)

    template, resultado = fetch_fiagro_template_live(
        "CRAA11", CNPJ, 2025, 8, "fake-token"
    )

    assert template["price"] is None
    assert any("não consegui buscar preço via brapi" in w for w in resultado.warnings)


def test_fetch_fiagro_sums_dividend_yield_without_multiplying_by_100(monkeypatch):
    # Real finding: FIAGRO's Dividend_Yield_Mes is ALREADY a plain
    # percentage (confirmed live), unlike FII's fraction-based field --
    # summing must NOT multiply by 100 here.
    monkeypatch.setattr(CvmFiagroHTTPHarvester, "fetch", fake_fetch)

    template, resultado = fetch_fiagro_template_live("CRAA11", CNPJ, 2025, 8)

    esperado = round(1.2 + 0.9 + 1.59, 4)
    assert template["financials"]["dividend_yield_pct"] == esperado
    assert "dividend_yield_pct" in resultado.fetched_fields


def test_fetch_fiagro_warns_about_scope_limitation(monkeypatch):
    monkeypatch.setattr(CvmFiagroHTTPHarvester, "fetch", fake_fetch)

    _, resultado = fetch_fiagro_template_live("CRAA11", CNPJ, 2025, 8)

    assert any("não tem campo de patrimônio" in w for w in resultado.warnings)


def test_fetch_fiagro_warns_when_partial_ttm(monkeypatch):
    monkeypatch.setattr(CvmFiagroHTTPHarvester, "fetch", fake_fetch)

    _, resultado = fetch_fiagro_template_live("CRAA11", CNPJ, 2025, 8)

    assert resultado.dividend_yield_months_used == 3
    assert any("3 mes" in w for w in resultado.warnings)


def test_fetch_fiagro_warns_when_cnpj_not_found(monkeypatch):
    monkeypatch.setattr(CvmFiagroHTTPHarvester, "fetch", fake_fetch)

    template, resultado = fetch_fiagro_template_live(
        "XYZ11", "00.000.000/0001-00", 2025, 8
    )

    assert any("Nenhum registro CVM FIAGRO encontrado" in w for w in resultado.warnings)
    assert template["financials"]["dividend_yield_pct"] == 11.5  # default do AgroAnalyzer


def test_fetch_fiagro_does_not_call_brapi_without_a_token(monkeypatch):
    monkeypatch.setattr(CvmFiagroHTTPHarvester, "fetch", fake_fetch)

    def exploding_init(self, *a, **kw):
        raise AssertionError("must not instantiate brapi without a token")

    monkeypatch.setattr(BrapiHTTPHarvester, "__init__", exploding_init)

    fetch_fiagro_template_live("CRAA11", CNPJ, 2025, 8)


def _http_error(code):
    return HTTPError("https://dados.cvm.gov.br/x", code, "err", None, None)


def test_fetch_fiagro_falls_back_to_previous_month_on_404(monkeypatch):
    tentados = []

    def fetch(self, target):
        tentados.append((target.ano, target.mes))
        if (target.ano, target.mes) == (2026, 9):
            raise _http_error(404)
        return fake_fetch(self, target)

    monkeypatch.setattr(CvmFiagroHTTPHarvester, "fetch", fetch)

    _, resultado = fetch_fiagro_template_live("CRAA11", CNPJ, 2026, 9)

    assert tentados == [(2026, 9), (2026, 8)]
    assert "dividend_yield_pct" in resultado.fetched_fields
    assert any("2026-09" in w and "2026-08" in w for w in resultado.warnings)


def test_fetch_fiagro_fallback_crosses_year_boundary(monkeypatch):
    tentados = []

    def fetch(self, target):
        tentados.append((target.ano, target.mes))
        if len(tentados) < 3:
            raise _http_error(404)
        return fake_fetch(self, target)

    monkeypatch.setattr(CvmFiagroHTTPHarvester, "fetch", fetch)

    fetch_fiagro_template_live("CRAA11", CNPJ, 2026, 1)

    assert tentados == [(2026, 1), (2025, 12), (2025, 11)]


def test_fetch_fiagro_gives_up_after_three_404s(monkeypatch):
    def fetch(self, target):
        raise _http_error(404)

    monkeypatch.setattr(CvmFiagroHTTPHarvester, "fetch", fetch)

    try:
        fetch_fiagro_template_live("CRAA11", CNPJ, 2026, 9)
    except HTTPError as exc:
        assert exc.code == 404
    else:
        raise AssertionError("esperava HTTPError")


def test_fetch_fiagro_does_not_swallow_other_http_errors(monkeypatch):
    def fetch(self, target):
        raise _http_error(500)

    monkeypatch.setattr(CvmFiagroHTTPHarvester, "fetch", fetch)

    try:
        fetch_fiagro_template_live("CRAA11", CNPJ, 2026, 9)
    except HTTPError as exc:
        assert exc.code == 500
    else:
        raise AssertionError("esperava HTTPError")


def _bolsai_fii(**kw):
    from iip.sources.b3_bolsai import BolsaiFiiData

    base = {
        "ticker": "CRAA11", "name": "SPARTA", "reference_date": "2026-08-01", "close_price": 90.99,
        "book_value_per_share": 100.96, "pvp": 0.9, "dividend_yield_ttm": 15.66,
        "net_asset_value": 239_259_457.21, "shares_outstanding": 2_369_836.0,
        "total_shareholders": 10_889.0, "segment": None, "management_type": None,
    }
    base.update(kw)
    return BolsaiFiiData(**base)


def _patch_bolsai(monkeypatch, fii=None, error=None):
    from iip.sources.b3_bolsai_harvester import BolsaiHTTPHarvester

    calls = []

    def fetch_fii(self, target):
        calls.append(target.ticker)
        if error:
            raise error
        return type("R", (), {"fii": fii})()

    monkeypatch.setattr(BolsaiHTTPHarvester, "fetch_fii", fetch_fii)
    return calls


def test_fetch_fiagro_adds_valuation_inputs_from_bolsai_when_key_given(monkeypatch):
    monkeypatch.setattr(CvmFiagroHTTPHarvester, "fetch", fake_fetch)
    calls = _patch_bolsai(monkeypatch, fii=_bolsai_fii())

    template, resultado = fetch_fiagro_template_live(
        "CRAA11", CNPJ, 2025, 8, bolsai_api_key="k"
    )

    fin = template["financials"]
    assert calls == ["CRAA11"]
    assert fin["nav_per_share"] == 100.96
    assert fin["dividend_yield_ttm"] == 15.66
    assert fin["dividend_per_share"] == round(15.66 / 100 * 100.96, 4)
    assert "nav_per_share" in resultado.fetched_fields
    assert fin["dividend_yield_pct"] == round(1.2 + 0.9 + 1.59, 4)  # analyzer input untouched


def test_fetch_fiagro_does_not_call_bolsai_without_key(monkeypatch):
    monkeypatch.setattr(CvmFiagroHTTPHarvester, "fetch", fake_fetch)
    calls = _patch_bolsai(monkeypatch, fii=_bolsai_fii())

    template, _ = fetch_fiagro_template_live("CRAA11", CNPJ, 2025, 8)

    assert calls == []
    assert "nav_per_share" not in template["financials"]


def test_fetch_fiagro_bolsai_failure_is_a_warning_not_an_error(monkeypatch):
    monkeypatch.setattr(CvmFiagroHTTPHarvester, "fetch", fake_fetch)
    _patch_bolsai(monkeypatch, error=RuntimeError("cota esgotada"))

    template, resultado = fetch_fiagro_template_live(
        "CRAA11", CNPJ, 2025, 8, bolsai_api_key="k"
    )

    assert "nav_per_share" not in template["financials"]
    assert any("bolsai" in w and "cota esgotada" in w for w in resultado.warnings)
