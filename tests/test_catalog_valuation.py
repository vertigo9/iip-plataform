import json
from datetime import date

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.decision.catalog_valuation import catalog_valuation_for_decision
from iip.sources.tesouro_direto import NtnbRate

RATE = NtnbRate(
    reference_date=date(2026, 9, 17), maturity=date(2060, 8, 15), real_yield=0.073
)


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _value(**overrides):
    kwargs = {
        "ticker": "KLBN4",
        "asset_class": "equity",
        "sector": "Materiais Básicos",
        "industry": "Madeiras e Papel",
        "price": 2.0,
        "ntnb_real_yield": 0.073,
        "financials": {"lpa": 0.24, "vpa": 1.52},
    }
    kwargs.update(overrides)
    return catalog_valuation_for_decision(**kwargs)


# --- catalog_valuation_for_decision ------------------------------------------------


def test_score_is_five_plus_ten_per_hundred_percent_margin_of_safety():
    result = _value()  # Graham: sqrt(22.5 * 0.24 * 1.52) = 2.86 against price 2.00

    assert result.method == "Graham"
    assert result.fair_value == 2.86
    assert result.margin_of_safety == pytest.approx(2.86 / 2.0 - 1.0)
    assert result.score == pytest.approx(5.0 + (2.86 / 2.0 - 1.0) * 10, abs=0.01)
    assert "Graham" in result.explanation and "nota" in result.explanation


def test_score_is_clamped_to_the_zero_ten_scale():
    assert _value(price=0.5).score == 10.0  # enormous margin of safety
    assert _value(price=50.0).score == 0.0  # enormous overvaluation


def test_lead_method_follows_the_sector():
    financials = {
        "lpa": 4.97,
        "vpa": 19.72,
        "dividend_per_share": 3.05,
        "dividend_consistency_years": 5,
        "payout_ratio": 61.0,
    }
    utility = _value(
        sector="Utilidade Pública",
        industry="Energia Elétrica",
        price=45.0,
        financials=financials,
    )
    industrial = _value(price=45.0, financials=financials)

    assert utility.method == "Bazin"
    assert industrial.method == "Graham"


def test_no_method_producing_a_value_gives_no_score_and_says_why():
    result = _value(financials={"lpa": -0.4, "vpa": 1.5})

    assert result.score is None
    assert result.method is None
    assert "Graham" in result.explanation and "positivos" in result.explanation


def test_a_value_without_market_price_gives_no_score():
    result = _value(price=None)

    assert result.score is None
    assert result.method == "Graham" and result.fair_value == 2.86
    assert "sem preço" in result.explanation


def test_class_without_an_implemented_method_gives_no_score():
    result = _value(asset_class="fixed_income")

    assert result.score is None
    assert "fixed_income" in result.explanation


def test_missing_ntnb_rate_never_invents_a_bazin_ceiling():
    result = _value(
        sector="Utilidade Pública",
        industry="Gás",
        ntnb_real_yield=None,
        financials={"dividend_per_share": 1.0, "dividend_consistency_years": 5},
    )

    assert result.score is None  # Graham has no LPA/VPA either, Bazin has no rate
    assert "NTN-B" in result.explanation


# --- CLI: analyze --decide --auto-valuation -----------------------------------------


def _equity_file(
    tmp_path,
    *,
    sector="Materiais Básicos",
    industry="Madeiras e Papel",
    price=2.0,
    **financials,
):
    runner = CliRunner()
    path = tmp_path / "eq.json"
    runner.invoke(cli, ["analyze-template", "--type", "equity", "-o", str(path)])
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update({"sector": sector, "industry": industry, "price": price})
    data["financials"].update(financials)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _analyze(tmp_path, monkeypatch, *extra, rate=RATE, **file_kwargs):
    import iip.portfolio.batch_value as bv

    monkeypatch.setattr(bv, "_default_fetch_rate", lambda: rate)
    path = _equity_file(tmp_path, **file_kwargs)
    return CliRunner().invoke(
        cli,
        [
            "analyze",
            "KLBN4",
            "--type",
            "equity",
            "--data-file",
            str(path),
            "--decide",
            "--evidence-id",
            "ev-1",
            *extra,
        ],
    )


def test_auto_valuation_feeds_the_decision(tmp_path, monkeypatch):
    result = _analyze(tmp_path, monkeypatch, "--auto-valuation", lpa=0.24, vpa=1.52)

    assert result.exit_code == 0, result.output
    assert "Valuation automático: Graham" in result.output
    assert "valuation_score não fornecido" not in result.output  # not neutral any more


def test_without_the_flag_valuation_stays_neutral(tmp_path, monkeypatch):
    result = _analyze(tmp_path, monkeypatch, lpa=0.24, vpa=1.52)

    assert result.exit_code == 0, result.output
    assert "valuation_score não fornecido" in result.output
    assert "Valuation automático" not in result.output


def test_explicit_valuation_score_takes_precedence(tmp_path, monkeypatch):
    result = _analyze(
        tmp_path,
        monkeypatch,
        "--auto-valuation",
        "--valuation-score",
        "7",
        lpa=0.24,
        vpa=1.52,
    )

    assert result.exit_code == 0, result.output
    assert "ignorado" in result.output
    assert "Valuation automático" not in result.output


def test_auto_valuation_without_a_producible_method_warns_and_stays_neutral(
    tmp_path, monkeypatch
):
    result = _analyze(tmp_path, monkeypatch, "--auto-valuation", lpa=-1.0, vpa=1.52)

    assert result.exit_code == 0, result.output
    assert "valuation automático sem valor" in result.output
    assert (
        "valuation_score não fornecido" in result.output
    )  # neutral fallback, with its own warning


def test_a_ntnb_failure_does_not_stop_the_decision(tmp_path, monkeypatch):
    import iip.portfolio.batch_value as bv

    def boom():
        raise OSError("sem rede")

    monkeypatch.setattr(bv, "_default_fetch_rate", boom)
    path = _equity_file(tmp_path, lpa=0.24, vpa=1.52)
    result = CliRunner().invoke(
        cli,
        [
            "analyze",
            "KLBN4",
            "--type",
            "equity",
            "--data-file",
            str(path),
            "--decide",
            "--evidence-id",
            "ev-1",
            "--auto-valuation",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "não consegui buscar a taxa da NTN-B" in result.output
    assert "Valuation automático: Graham" in result.output  # Graham needs no rate


# --- FIIs through the same flag ------------------------------------------------------


def _fii_file(
    tmp_path, *, structure="Tijolo", segment="Logístico", price=99.78, **financials
):
    runner = CliRunner()
    path = tmp_path / "fii.json"
    runner.invoke(cli, ["analyze-template", "--type", "fii", "-o", str(path)])
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update({"sector": structure, "industry": segment, "price": price})
    data["financials"].update(financials)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _analyze_fii(tmp_path, monkeypatch, *extra, **file_kwargs):
    import iip.portfolio.batch_value as bv

    monkeypatch.setattr(bv, "_default_fetch_rate", lambda: RATE)
    path = _fii_file(tmp_path, **file_kwargs)
    return CliRunner().invoke(
        cli,
        [
            "analyze",
            "BTLG11",
            "--type",
            "fii",
            "--data-file",
            str(path),
            "--decide",
            "--evidence-id",
            "ev-1",
            *extra,
        ],
    )


def test_auto_valuation_uses_the_nav_for_a_fii(tmp_path, monkeypatch):
    result = _analyze_fii(
        tmp_path, monkeypatch, "--auto-valuation", nav_per_share=106.86
    )

    assert result.exit_code == 0, result.output
    assert "Valuation automático: NAV" in result.output
    assert "valuation_score não fornecido" not in result.output


def test_a_paper_fund_is_still_valued_by_the_nav_only(tmp_path, monkeypatch):
    result = _analyze_fii(
        tmp_path,
        monkeypatch,
        "--auto-valuation",
        structure="Papel",
        segment="Crédito Imobiliário",
        nav_per_share=97.4,
        dividend_per_share=11.99,
        dividend_yield_ttm=12.31,
    )

    assert result.exit_code == 0, result.output
    assert "Valuation automático: NAV" in result.output


def test_a_fii_without_nav_keeps_the_neutral_value_and_says_why(tmp_path, monkeypatch):
    result = _analyze_fii(tmp_path, monkeypatch, "--auto-valuation")  # no nav_per_share

    assert result.exit_code == 0, result.output
    assert "valuation automático sem valor" in result.output
    assert "patrimônio por cota" in result.output
    assert "valuation_score não fornecido" in result.output


# --- FIAGRO (--type agro) and listed FI-Infra (--type fixed_income) -------------------


def _typed_file(tmp_path, asset_type, *, sector, industry, price, **financials):
    path = tmp_path / f"{asset_type}.json"
    CliRunner().invoke(cli, ["analyze-template", "--type", asset_type, "-o", str(path)])
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update({"sector": sector, "industry": industry, "price": price})
    data["financials"].update(financials)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _analyze_typed(tmp_path, monkeypatch, symbol, asset_type, **file_kwargs):
    import iip.portfolio.batch_value as bv

    monkeypatch.setattr(bv, "_default_fetch_rate", lambda: RATE)
    path = _typed_file(tmp_path, asset_type, **file_kwargs)
    return CliRunner().invoke(
        cli,
        [
            "analyze",
            symbol,
            "--type",
            asset_type,
            "--data-file",
            str(path),
            "--decide",
            "--evidence-id",
            "ev-1",
            "--auto-valuation",
        ],
    )


def test_auto_valuation_uses_the_nav_for_a_fiagro(tmp_path, monkeypatch):
    result = _analyze_typed(
        tmp_path,
        monkeypatch,
        "CRAA11",
        "agro",
        sector="Papel",
        industry="Crédito Agrícola",
        price=90.99,
        nav_per_share=100.96,
    )

    assert result.exit_code == 0, result.output
    assert "Valuation automático: NAV" in result.output
    assert "valuation_score não fornecido" not in result.output


def test_auto_valuation_uses_the_nav_for_a_listed_fi_infra(tmp_path, monkeypatch):
    result = _analyze_typed(
        tmp_path,
        monkeypatch,
        "CDII11",
        "fixed_income",
        sector="Papel",
        industry="Infraestrutura",
        price=95.2,
        nav_per_share=101.17,
    )

    assert result.exit_code == 0, result.output
    assert "Valuation automático: NAV" in result.output
    assert "valuation_score não fornecido" not in result.output


def test_auto_valuation_uses_the_nav_for_an_etf(tmp_path, monkeypatch):
    result = _analyze_typed(
        tmp_path,
        monkeypatch,
        "LFTB11",
        "etf",
        sector="Renda Fixa",
        industry="ETF de Renda Fixa",
        price=126.93,
        nav_per_share=126.66,
    )

    assert result.exit_code == 0, result.output
    assert "Valuation automático: NAV" in result.output
    assert "valuation_score não fornecido" not in result.output


def test_fixed_income_without_a_market_price_stays_neutral_and_says_why(
    tmp_path, monkeypatch
):
    # AXIA3 case: the data file has a cota but no price to compare it with.
    result = _analyze_typed(
        tmp_path,
        monkeypatch,
        "AXIA3",
        "fixed_income",
        sector="Utilities",
        industry="Electric Utilities",
        price=None,
        nav_per_share=1.89,
    )

    assert result.exit_code == 0, result.output
    output = " ".join(result.output.split())  # Rich wraps long warnings
    assert "valuation automático sem valor" in output
    assert "sem preço de mercado" in output
    assert "valuation_score não fornecido" in output


def _fetch_template_fixed_income(monkeypatch, tmp_path, *extra, token="tok"):
    import iip.cli.fetch_template as ft

    calls = []

    def fake(symbol, cnpj, ano, mes, brapi_token=None):
        calls.append(brapi_token)
        return {"symbol": symbol, "price": None, "financials": {}}, type(
            "R", (), {"fetched_fields": (), "warnings": ()}
        )()

    monkeypatch.setattr(ft, "fetch_fixed_income_template_live", fake)
    monkeypatch.setenv("IIP_BRAPI_TOKEN", token)
    from iip.config import get_settings

    get_settings.cache_clear()
    try:
        result = CliRunner().invoke(
            cli,
            [
                "fetch-template",
                "CDII11",
                "--type",
                "fixed_income",
                "--cnpj",
                "48.973.783/0001-16",
                "-o",
                str(tmp_path / "t.json"),
                *extra,
            ],
        )
    finally:
        get_settings.cache_clear()
    return result, calls


def test_fetch_template_fixed_income_never_prices_without_the_flag(
    monkeypatch, tmp_path
):
    result, calls = _fetch_template_fixed_income(monkeypatch, tmp_path)
    assert result.exit_code == 0, result.output
    assert calls == [None]


def test_fetch_template_fixed_income_prices_only_with_the_flag(monkeypatch, tmp_path):
    result, calls = _fetch_template_fixed_income(
        monkeypatch, tmp_path, "--preco-mercado"
    )
    assert result.exit_code == 0, result.output
    assert calls == ["tok"]
