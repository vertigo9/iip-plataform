"""Núcleo compartilhado dos lotes da carteira (``iip.portfolio.batch_core``).

Os argumentos exatos com que cada lote chama cada buscador estão em
``test_portfolio_batch_dispatch.py``; aqui ficam as regras do próprio núcleo."""

from datetime import date

import pytest

import iip.cli.fetch_template as ft
from iip.portfolio.batch_core import (
    FetchPlan,
    fetch_template_for,
    resolve_fetchers,
)
from iip.portfolio.registry import PortfolioAsset

POSITION = PortfolioAsset("TICK11", "fund", cnpj="12")


def _fetchers(calls):
    def make(name):
        def fetch(*args, **kwargs):
            calls.append((name, args, kwargs))
            return {"price": 1.0}, object()

        return fetch

    return resolve_fetchers(
        fii=make("fii"),
        etf=make("etf"),
        fixed_income=make("fixed_income"),
        equity=make("equity"),
        fiagro=make("fiagro"),
    )


def _plan(**overrides):
    base = {
        "ano": 2026,
        "mes": 9,
        "ano_dfp": 2025,
        "bolsai_api_key": "BK",
        "brapi_token": "PK",
    }
    return FetchPlan(**{**base, **overrides})


def test_an_unknown_template_type_raises_instead_of_being_swallowed():
    with pytest.raises(ValueError, match="desconhecido"):
        fetch_template_for("crypto", POSITION, _fetchers([]), _plan())


@pytest.mark.parametrize(
    "template_type, expected",
    [
        ("fii", ("fii", ("TICK11", "12", 2026, "BK"), {})),
        ("etf", ("etf", ("TICK11", "12", 2026, 9, "PK"), {})),
        ("equity", ("equity", ("TICK11", "12", 2025, "BK", "PK"), {})),
        ("fiagro", ("fiagro", ("TICK11", "12", 2026, 9, "PK"), {})),
        ("fixed_income", ("fixed_income", ("TICK11", "12", 2026, 9), {})),
        (
            "fi_infra",
            ("fixed_income", ("TICK11", "12", 2026, 9), {"brapi_token": "PK"}),
        ),
    ],
)
def test_each_type_goes_to_its_own_fetcher_with_its_own_arguments(
    template_type, expected
):
    calls = []
    fetch_template_for(template_type, POSITION, _fetchers(calls), _plan())
    assert calls == [expected]


def test_fiagro_passes_the_bolsai_key_only_when_the_plan_asks_for_it():
    calls = []
    fetch_template_for("fiagro", POSITION, _fetchers(calls), _plan())
    fetch_template_for(
        "fiagro", POSITION, _fetchers(calls), _plan(fiagro_uses_bolsai=True)
    )
    assert calls[0][2] == {}
    assert calls[1][2] == {"bolsai_api_key": "BK"}


def test_the_fetcher_return_value_is_passed_through_untouched():
    marker = object()
    fetchers = resolve_fetchers(equity=lambda *a, **k: ({"price": 3.0}, marker))
    template, result = fetch_template_for("equity", POSITION, fetchers, _plan())
    assert template == {"price": 3.0}
    assert result is marker


def test_resolve_fetchers_uses_the_real_ones_when_nothing_is_injected():
    fetchers = resolve_fetchers()
    assert fetchers.fii is ft.fetch_fii_template_live
    assert fetchers.etf is ft.fetch_etf_template_live
    assert fetchers.equity is ft.fetch_equity_template_live
    assert fetchers.fiagro is ft.fetch_fiagro_template_live
    assert fetchers.fixed_income is ft.fetch_fixed_income_template_live


def test_resolve_fetchers_follows_a_replacement_of_the_live_function(monkeypatch):
    # a resolução é feita a cada chamada, então trocar o buscador no módulo vale
    sentinel = lambda *a, **k: ({}, None)  # noqa: E731
    monkeypatch.setattr(ft, "fetch_equity_template_live", sentinel)
    assert resolve_fetchers().equity is sentinel


def test_an_injected_fetcher_wins_over_the_real_one():
    injected = lambda *a, **k: ({}, None)  # noqa: E731
    assert resolve_fetchers(fii=injected).fii is injected


def test_fii_without_analysis_inputs_asks_for_the_lighter_template(monkeypatch):
    recorded = []

    def live(*args, **kwargs):
        recorded.append(kwargs)
        return {}, None

    monkeypatch.setattr(ft, "fetch_fii_template_live", live)
    resolve_fetchers(fii_analysis_inputs=False).fii("T", "1", 2026, "K")
    resolve_fetchers().fii("T", "1", 2026, "K")
    assert recorded == [{"analysis_inputs": False}, {}]


def test_an_injected_fii_fetcher_is_not_wrapped_even_without_analysis_inputs():
    injected = lambda *a, **k: ({}, None)  # noqa: E731
    assert resolve_fetchers(fii=injected, fii_analysis_inputs=False).fii is injected


def test_plan_defaults_to_the_current_year_and_month_and_the_previous_fiscal_year():
    plan = FetchPlan.for_run(
        ano=None,
        mes=None,
        bolsai_api_key="BK",
        brapi_token="PK",
        today=date(2026, 9, 19),
    )
    assert (plan.ano, plan.mes, plan.ano_dfp) == (2026, 9, 2025)
    assert (plan.bolsai_api_key, plan.brapi_token) == ("BK", "PK")
    assert plan.fiagro_uses_bolsai is False


def test_an_explicit_year_moves_the_fund_year_and_the_fiscal_year_together():
    plan = FetchPlan.for_run(
        ano=2020,
        mes=3,
        bolsai_api_key=None,
        brapi_token=None,
        today=date(2026, 9, 19),
    )
    assert (plan.ano, plan.mes, plan.ano_dfp) == (2020, 3, 2020)
