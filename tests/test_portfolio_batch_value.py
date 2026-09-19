from datetime import date

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.portfolio.batch_value import value_portfolio
from iip.portfolio.registry import PortfolioAsset
from iip.portfolio_data.valuation import ValuationMethod
from iip.sources.tesouro_direto import NtnbRate

RATE = NtnbRate(reference_date=date(2026, 9, 17), maturity=date(2060, 8, 15), real_yield=0.073)


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _equity(ticker, **kw):
    return PortfolioAsset(
        ticker, "equity", cnpj="00.000.000/0000-00",
        sector=kw.pop("sector", "Materiais Básicos"),
        industry=kw.pop("industry", "Madeiras e Papel"), **kw,
    )


def _fake_fetch(templates):
    calls = []

    def fetch(symbol, cnpj, ano, bolsai_api_key, brapi_token):
        calls.append((symbol, ano))
        outcome = templates[symbol]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome, object()

    fetch.calls = calls
    return fetch


def _template(price=20.0, **financials):
    return {"price": price, "financials": financials}


def _run(positions, templates, *, rate=RATE, **kw):
    fetch = _fake_fetch(templates)
    result = value_portfolio(
        bolsai_api_key="k", brapi_token=None, positions=tuple(positions),
        fetch_equity=fetch, fetch_rate=lambda: rate, ano=2025, **kw,
    )
    return result, fetch


def test_each_position_gets_every_method_side_by_side():
    result, _ = _run(
        [_equity("CXSE3")],
        {"CXSE3": _template(lpa=1.51, vpa=4.60, dividend_per_share=1.26)},
    )

    outcome = result.outcomes[0]
    assert outcome.status == "ok"
    by_method = {a.method: a for a in outcome.attempts}
    assert by_method[ValuationMethod.GRAHAM].snapshot.fair_value == 12.50
    assert by_method[ValuationMethod.BAZIN].snapshot.fair_value == pytest.approx(17.26)
    assert "Graham=12.50" in outcome.detail and "Bazin=17.26" in outcome.detail
    assert outcome.price == 20.0


def test_the_ntnb_rate_is_fetched_once_for_the_whole_run():
    fetched = []

    def fetch_rate():
        fetched.append(1)
        return RATE

    fetch = _fake_fetch({t: _template(dividend_per_share=1.0) for t in ("A3", "B3", "C3")})
    value_portfolio(
        bolsai_api_key="k", brapi_token=None, ano=2025, fetch_equity=fetch, fetch_rate=fetch_rate,
        positions=tuple(_equity(t) for t in ("A3", "B3", "C3")),
    )

    assert len(fetched) == 1


def test_missing_rate_leaves_bazin_without_value_and_never_uses_six_percent():
    result, _ = _run(
        [_equity("KLBN4")],
        {"KLBN4": _template(lpa=0.24, vpa=1.52, dividend_per_share=0.15)},
        rate=None,
    )

    assert "indisponível" in result.ntnb_note
    outcome = result.outcomes[0]
    assert outcome.status == "ok"  # Graham still valued it
    bazin = next(a for a in outcome.attempts if a.method is ValuationMethod.BAZIN)
    assert bazin.status == "insufficient_data"
    assert bazin.snapshot is None


def test_rate_lookup_failure_is_a_note_not_a_crash():
    def boom():
        raise OSError("sem rede")

    fetch = _fake_fetch({"KLBN4": _template(lpa=0.24, vpa=1.52)})
    result = value_portfolio(
        bolsai_api_key="k", brapi_token=None, ano=2025, fetch_equity=fetch, fetch_rate=boom,
        positions=(_equity("KLBN4"),),
    )

    assert "sem rede" in result.ntnb_note
    assert result.outcomes[0].status == "ok"


def test_position_with_no_producible_method_is_skipped_with_reasons():
    result, _ = _run([_equity("SAUD3")], {"SAUD3": _template(lpa=-0.4, vpa=3.0, dividend_per_share=0.0)})

    outcome = result.outcomes[0]
    assert outcome.status == "pulado"
    assert "Graham" in outcome.detail and "Bazin" in outcome.detail
    assert "not_implemented" not in outcome.detail  # only real reasons are listed


def test_technology_equity_is_valued_only_by_the_methods_that_fit():
    result, _ = _run(
        [_equity("CSUD3", sector="Utilidade Pública / Tecnologia", industry="Processamento de Dados")],
        {"CSUD3": _template(lpa=2.0, vpa=11.0, dividend_per_share=0.87)},
    )

    by_method = {a.method: a.status for a in result.outcomes[0].attempts}
    assert by_method[ValuationMethod.GRAHAM] == "not_applicable"
    assert by_method[ValuationMethod.BAZIN] == "ok"


def test_classes_without_an_implemented_method_and_missing_sector_are_skipped_without_fetching():
    etf = PortfolioAsset("LFTB11", "etf", cnpj="1")  # a class with no implemented method
    no_sector = PortfolioAsset("XXXX3", "equity", cnpj="1")  # no sector/industry in the registry

    result, fetch = _run([etf, no_sector], {})

    assert [o.status for o in result.outcomes] == ["pulado", "pulado"]
    assert "classe" in result.outcomes[0].detail
    assert "sector/industry" in result.outcomes[1].detail
    assert fetch.calls == []  # neither position triggered a network fetch


def test_one_failing_position_does_not_stop_the_others():
    result, _ = _run(
        [_equity("BAD3"), _equity("OK3")],
        {"BAD3": RuntimeError("bolsai fora do ar"), "OK3": _template(lpa=1.0, vpa=4.0)},
    )

    assert [o.status for o in result.outcomes] == ["erro", "ok"]
    assert "bolsai fora do ar" in result.outcomes[0].detail
    assert len(result.failed) == 1 and len(result.succeeded) == 1


def test_persist_writes_only_the_first_method_that_produced_a_value():
    written = []

    class FakeBridge:
        def __init__(self, vault):
            self.vault = vault

        def sync_valuation_projection(self, snapshot, ticker, asset_class):
            written.append((ticker, asset_class, snapshot.method))

    result, _ = _run(
        [_equity("CXSE3")],
        {"CXSE3": _template(lpa=1.51, vpa=4.60, dividend_per_share=1.26)},
        persist=True, vault_path="/vault", bridge_cls=FakeBridge,
    )

    assert written == [("CXSE3", "equity", ValuationMethod.GRAHAM)]
    assert "persistido: Graham" in result.outcomes[0].detail


def test_nothing_is_written_without_persist():
    class ExplodingBridge:
        def __init__(self, vault):
            raise AssertionError("must not touch the vault")

    result, _ = _run(
        [_equity("CXSE3")], {"CXSE3": _template(lpa=1.51, vpa=4.60)}, bridge_cls=ExplodingBridge
    )

    assert result.outcomes[0].status == "ok"


def test_persist_requires_a_vault_path():
    with pytest.raises(ValueError, match="vault_path"):
        value_portfolio(
            bolsai_api_key="k", brapi_token=None, positions=(), persist=True,
            fetch_equity=_fake_fetch({}), fetch_rate=lambda: RATE,
        )


# --- CLI ---------------------------------------------------------------------


def test_value_portfolio_command_prints_side_by_side_table(monkeypatch):
    import iip.cli.fetch_template as ft
    import iip.portfolio.batch_value as bv

    monkeypatch.setattr(
        bv, "assets_refreshable_now",
        lambda: (_equity("CXSE3", sector="Financeiro", industry="Seguros"), _equity("BTLG11x"),
                 PortfolioAsset("LFTB11", "etf", cnpj="1")),
    )
    monkeypatch.setattr(bv, "_default_fetch_rate", lambda: RATE)
    monkeypatch.setattr(
        ft, "fetch_equity_template_live",
        lambda symbol, cnpj, ano, b, r: (_template(price=20.54, lpa=1.43, vpa=4.6, dividend_per_share=1.26), object()),
    )

    result = CliRunner().invoke(cli, ["value-portfolio"])

    assert result.exit_code == 0, result.output
    assert "IPCA + 7.30%" in result.output
    assert "CXSE3" in result.output
    assert "12.17" in result.output  # Graham
    assert "17.26" in result.output  # Bazin at 7.30%
    # the fund is summarized per class in one line, not as a table row
    assert "pulado (1)" in result.output  # not wrapped-line sensitive
    assert "LFTB11" in result.output
    assert "principal" in result.output  # header may wrap in a narrow table
    assert "Bazin" in result.output  # lead for the insurer, with Graham among the others
    assert "não é recomendação" in result.output


def test_value_portfolio_command_exits_nonzero_when_a_position_errors(monkeypatch):
    import iip.cli.fetch_template as ft
    import iip.portfolio.batch_value as bv

    monkeypatch.setattr(bv, "assets_refreshable_now", lambda: (_equity("BAD3"),))
    monkeypatch.setattr(bv, "_default_fetch_rate", lambda: RATE)

    def boom(*args):
        raise RuntimeError("falhou")

    monkeypatch.setattr(ft, "fetch_equity_template_live", boom)

    result = CliRunner().invoke(cli, ["value-portfolio"])

    assert result.exit_code == 1


def test_fiagro_paper_fund_is_valued_by_nav_only_through_the_fiagro_fetch():
    craa = PortfolioAsset(
        "CRAA11", "fund", subtype="FI-Agro", structure="Papel",
        segment="Crédito Agrícola", cnpj="48.903.610/0001-21",
    )
    calls = []

    def fetch_fiagro(symbol, cnpj, ano, mes, brapi_token, bolsai_api_key=None):
        calls.append((symbol, brapi_token, bolsai_api_key))
        return _template(
            price=90.99, nav_per_share=100.96, dividend_yield_ttm=15.66,
            dividend_per_share=15.81,
        ), object()

    result = value_portfolio(
        bolsai_api_key="k", brapi_token="b", positions=(craa,),
        fetch_fiagro=fetch_fiagro, fetch_rate=lambda: RATE,
    )

    outcome = result.outcomes[0]
    assert outcome.status == "ok" and outcome.asset_class == "fiagro"
    by_method = {a.method: a for a in outcome.attempts}
    assert by_method[ValuationMethod.NAV].snapshot.fair_value == 100.96
    assert by_method[ValuationMethod.YIELD].status == "not_applicable"  # papel: CDI, not real
    assert calls == [("CRAA11", "b", "k")]


def _fi_infra(ticker="CDII11"):
    return PortfolioAsset(
        ticker, "fund", subtype="FI-Infra", structure="Papel",
        segment="Infraestrutura", cnpj="48.973.783/0001-16",
    )


def test_listed_fi_infra_is_valued_by_nav_with_brapi_price():
    calls = []

    def fetch_fixed_income(symbol, cnpj, ano, mes, brapi_token=None):
        calls.append((symbol, brapi_token))
        return _template(price=95.2, nav_per_share=101.17), object()

    result = value_portfolio(
        bolsai_api_key="k", brapi_token="b", positions=(_fi_infra(),),
        fetch_fixed_income=fetch_fixed_income, fetch_rate=lambda: RATE,
    )

    outcome = result.outcomes[0]
    assert outcome.status == "ok" and outcome.asset_class == "fi_infra"
    assert outcome.attempts[0].snapshot.fair_value == 101.17
    assert outcome.attempts[0].snapshot.margin_of_safety == pytest.approx(101.17 / 95.2 - 1)
    assert calls == [("CDII11", "b")]


def test_fi_infra_with_failed_price_fetch_is_an_error():
    result = value_portfolio(
        bolsai_api_key="k", brapi_token="b", positions=(_fi_infra(),),
        fetch_fixed_income=lambda *a, **kw: (_template(price=None, nav_per_share=101.17), object()),
        fetch_rate=lambda: RATE,
    )
    assert result.outcomes[0].status == "erro"


def test_unlisted_fixed_income_like_axia3_is_still_skipped_without_fetching():
    axia = PortfolioAsset("AXIA3", "fixed_income", subtype="Daycoval FMP FGTS", cnpj="1")

    def fetch_fixed_income(*a, **kw):
        raise AssertionError("must not fetch: no market ticker to price against")

    result = value_portfolio(
        bolsai_api_key="k", brapi_token="b", positions=(axia,),
        fetch_fixed_income=fetch_fixed_income, fetch_rate=lambda: RATE,
    )
    assert result.outcomes[0].status == "pulado"
    assert "fixed_income" in result.outcomes[0].detail
