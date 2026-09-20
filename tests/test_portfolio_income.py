from datetime import date

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.obsidian.income_report import render_income_report, write_income_report
from iip.portfolio.historical_series import (
    HistoricalObservation,
    HistoricalSeries,
    HistoricalSeriesStore,
)
from iip.portfolio.income import (
    NO_SERIES,
    build_income,
)
from iip.portfolio_data.income_forecast import (
    MonthlyDistribution,
    forecast_next_distribution,
)
from iip.universal.portfolio_state import PortfolioState, PositionState

TODAY = date(2026, 9, 20)


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _obs(period, per_unit, nav=100.0):
    return HistoricalObservation(
        period=f"{period}-01",
        patrimonio_liquido=1e9,
        valor_patrimonial_cotas=nav,
        dividend_yield_mes=per_unit / nav,
        rentabilidade_patrimonial_mes=None,
        valor_ativo=None,
        total_numero_cotistas=None,
        document_id="d",
        document_hash="h",
        discovered_year=2026,
    )


def _months(values, start=(2026, 1)):
    year, month = start
    out = []
    for value in values:
        out.append(_obs(f"{year:04d}-{month:02d}", value, nav=100.0 + len(out) * 0.01))
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return out


def _series(ticker, observations):
    return HistoricalSeries(
        ticker=ticker,
        cnpj="00000000000000",
        provider="cvm",
        observations=tuple(observations),
        source_documents=(),
    )


def _store(tmp_path, *series):
    store = HistoricalSeriesStore(tmp_path)
    for s in series:
        store.save(s)
    return store


def _state(*positions, as_of="2026-09-12"):
    return PortfolioState(
        as_of=as_of,
        positions=tuple(PositionState(t, q, v, 0.0, "fund") for t, q, v in positions),
        total_value=sum(v for _, _, v in positions),
    )


def _line(report, ticker):
    return next(ln for ln in report.lines if ln.ticker == ticker)


# --- the forecast statistic ----------------------------------------------------


def test_median_statistic_ignores_a_one_off_extra_month():
    history = tuple(
        MonthlyDistribution(f"2026-0{i}", v)
        for i, v in enumerate((1.0, 1.0, 1.0, 1.5, 1.0, 1.0), start=1)
    )

    mean = forecast_next_distribution("X11", history, window=6)
    median = forecast_next_distribution("X11", history, window=6, statistic="median")

    assert median.projected_amount_per_unit == 1.0
    assert mean.projected_amount_per_unit > 1.0
    assert median.method == "median_6m" and mean.method == "moving_average_6m"


def test_an_unknown_statistic_is_rejected():
    with pytest.raises(ValueError):
        forecast_next_distribution(
            "X11", (MonthlyDistribution("2026-01", 1.0),), statistic="mode"
        )


# --- build_income --------------------------------------------------------------


def test_a_regular_series_is_projected_as_the_median_times_the_quantity(tmp_path):
    store = _store(
        tmp_path, _series("HGRU11", _months([0.94, 0.95, 0.95, 0.95, 0.96, 0.95]))
    )

    report = build_income(_state(("HGRU11", 100.0, 10000.0)), store, today=TODAY)

    line = _line(report, "HGRU11")
    assert line.status == "projetada"
    assert line.per_unit == pytest.approx(0.95, abs=0.001)
    assert line.monthly_income == pytest.approx(95.0, abs=0.1)
    assert report.monthly_income == pytest.approx(95.0, abs=0.1)
    assert report.covered_share == pytest.approx(1.0)
    assert len(line.months) == 6 and line.last_period == "2026-06"


def test_a_one_off_extra_month_is_flagged_but_does_not_move_the_number(tmp_path):
    store = _store(
        tmp_path, _series("KNRI11", _months([1.10, 1.10, 1.38, 1.10, 1.10, 1.10]))
    )

    report = build_income(_state(("KNRI11", 10.0, 1000.0)), store, today=TODAY)

    line = _line(report, "KNRI11")
    assert line.status == "projetada"
    assert line.per_unit == pytest.approx(1.10, abs=0.001)
    assert line.unusual == ("2026-03",)


def test_zero_or_negative_yield_in_most_months_is_not_projected_as_zero(tmp_path):
    store = _store(tmp_path, _series("BTCI11", _months([0.0] * 11 + [0.9])))

    report = build_income(_state(("BTCI11", 100.0, 1000.0)), store, today=TODAY)

    line = _line(report, "BTCI11")
    assert line.status == "sem projeção"
    assert "zero ou negativo" in line.reason
    assert report.monthly_income == 0.0


def test_a_negative_month_is_dropped_from_the_window(tmp_path):
    store = _store(
        tmp_path,
        _series("LVBI11", _months([0.72, -0.24, 0.72, 0.75, 0.73, 0.74, 0.72])),
    )

    report = build_income(_state(("LVBI11", 100.0, 1000.0)), store, today=TODAY)

    line = _line(report, "LVBI11")
    assert line.status == "projetada"
    assert all(m.amount_per_unit > 0 for m in line.months)
    assert len(line.months) == 6


def test_a_month_identical_to_the_previous_one_counts_once(tmp_path):
    same = _obs("2026-05", 0.86, nav=110.0)
    copies = [
        same,
        _obs("2026-06", 0.86, nav=110.0),
        _obs("2026-07", 0.86, nav=110.0),
    ]
    good = _months([0.85, 0.87, 0.86], start=(2026, 2))
    store = _store(tmp_path, _series("XPML11", [*good, *copies]))

    report = build_income(_state(("XPML11", 50.0, 5000.0)), store, today=TODAY)

    line = _line(report, "XPML11")
    assert line.repeated == ("2026-06", "2026-07")
    assert [m.period for m in line.months].count("2026-06") == 0


def test_an_irregular_series_is_not_projected_and_shows_its_range(tmp_path):
    store = _store(
        tmp_path, _series("XPML11", _months([0.30, 0.36, 0.86, 1.47, 0.20, 1.9]))
    )

    report = build_income(_state(("XPML11", 50.0, 5000.0)), store, today=TODAY)

    line = _line(report, "XPML11")
    assert line.status == "sem projeção"
    assert "série irregular" in line.reason
    assert "0.2000" in line.reason and "1.9000" in line.reason


def test_a_quota_split_inside_the_window_is_not_projected(tmp_path):
    values = _months([0.9, 0.9, 0.9, 0.9, 0.9, 0.9])
    values[3] = _obs("2026-04", 0.9, nav=10.0)  # a cota patrimonial muda de escala
    store = _store(tmp_path, _series("SPLT11", values))

    report = build_income(_state(("SPLT11", 10.0, 100.0)), store, today=TODAY)

    assert _line(report, "SPLT11").status == "sem projeção"
    assert "desdobramento" in _line(report, "SPLT11").reason


def test_too_few_usable_months_is_not_projected(tmp_path):
    store = _store(tmp_path, _series("NEW11", _months([0.5, 0.5])))

    report = build_income(_state(("NEW11", 10.0, 100.0)), store, today=TODAY)

    assert _line(report, "NEW11").status == "sem projeção"
    assert "mínimo" in _line(report, "NEW11").reason


def test_a_position_without_a_series_says_so_and_counts_as_uncovered(tmp_path):
    store = _store(tmp_path, _series("HGRU11", _months([0.95] * 6)))

    report = build_income(
        _state(("HGRU11", 100.0, 5000.0), ("BBSE3", 50.0, 5000.0)), store, today=TODAY
    )

    line = _line(report, "BBSE3")
    assert line.status == "sem projeção" and line.reason == NO_SERIES
    assert report.covered_share == pytest.approx(0.5)


def test_a_stale_series_is_pointed_out(tmp_path):
    store = _store(tmp_path, _series("OLD11", _months([0.5] * 6, start=(2025, 1))))

    report = build_income(_state(("OLD11", 10.0, 100.0)), store, today=TODAY)

    assert [ln.ticker for ln in report.stale_series] == ["OLD11"]


def test_projected_lines_come_first_biggest_income_first(tmp_path):
    store = _store(
        tmp_path,
        _series("SMALL11", _months([0.1] * 6)),
        _series("BIG11", _months([1.0] * 6)),
    )

    report = build_income(
        _state(
            ("NOSER3", 1.0, 100.0), ("SMALL11", 10.0, 100.0), ("BIG11", 100.0, 100.0)
        ),
        store,
        today=TODAY,
    )

    assert [ln.ticker for ln in report.lines] == ["BIG11", "SMALL11", "NOSER3"]


def test_the_window_and_an_empty_snapshot_are_validated(tmp_path):
    store = _store(tmp_path)

    with pytest.raises(ValueError):
        build_income(_state(("A11", 1.0, 100.0)), store, today=TODAY, window=2)
    with pytest.raises(ValueError):
        build_income(_state(("A11", 1.0, 0.0)), store, today=TODAY)


# --- report --------------------------------------------------------------------


def _report(tmp_path):
    store = _store(
        tmp_path,
        _series("HGRU11", _months([0.95] * 6)),
        _series("BTCI11", _months([0.0] * 12)),
    )
    return build_income(
        _state(
            ("HGRU11", 100.0, 5000.0), ("BTCI11", 100.0, 3000.0), ("BBSE3", 1.0, 2000.0)
        ),
        store,
        today=TODAY,
    )


def test_the_note_states_the_number_its_coverage_and_the_exclusions(tmp_path):
    text = render_income_report(_report(tmp_path))

    assert "R$ 95,00 por mês (bruto)" in text
    assert "50.0%" in text  # 5000 de 10000
    assert "HGRU11" in text and "BTCI11: a CVM informa rendimento zero" in text
    assert "Sem série mensal de distribuição por cota" in text and "BBSE3" in text
    assert "collect-fii-history" in text
    assert "Não é promessa" in text or "não é promessa" in text.lower()


def test_the_note_is_written_to_the_portfolio_folder(tmp_path):
    path = write_income_report(tmp_path / "vault", _report(tmp_path))

    assert path == tmp_path / "vault" / "02_Portfolio" / "Renda.md"
    assert path.read_text(encoding="utf-8").startswith("---\ntype: portfolio_income")


# --- CLI -----------------------------------------------------------------------

_SNAPSHOT = """\
| ID | Ativo | Classe | Quantidade | PM | Preço atual | Valor | Peso | Peso alvo | Status |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| HGRU11 | HGRU11 | fii | 100,0000 | 100,00 | 100,00 | 10.000,00 | 100,00% | | active |
"""


def _vault(tmp_path):
    vault = tmp_path / "vault"
    (vault / "02_Portfolio").mkdir(parents=True)
    (vault / "02_Portfolio" / "Current.md").write_text(_SNAPSHOT, encoding="utf-8")
    HistoricalSeriesStore(vault).save(_series("HGRU11", _months([0.95] * 6)))
    return vault


def test_command_prints_the_projection_and_the_limits(tmp_path):
    vault = _vault(tmp_path)

    out = CliRunner().invoke(cli, ["portfolio-income", "--vault", str(vault)])

    assert out.exit_code == 0, out.output
    assert "Renda mensal projetada: R$ 95.00" in out.output
    assert "HGRU11" in out.output
    assert "não é promessa" in out.output
    assert not (vault / "02_Portfolio" / "Renda.md").exists()


def test_command_writes_the_note_with_report(tmp_path):
    vault = _vault(tmp_path)

    out = CliRunner().invoke(
        cli, ["portfolio-income", "--vault", str(vault), "--report"]
    )

    assert out.exit_code == 0, out.output
    assert (vault / "02_Portfolio" / "Renda.md").exists()


def test_command_rejects_a_window_below_the_minimum(tmp_path):
    out = CliRunner().invoke(
        cli, ["portfolio-income", "--vault", str(_vault(tmp_path)), "--janela", "2"]
    )

    assert out.exit_code != 0
    assert "Não consegui projetar" in out.output


def test_command_reports_a_missing_snapshot(tmp_path):
    out = CliRunner().invoke(cli, ["portfolio-income", "--vault", str(tmp_path)])

    assert out.exit_code != 0
    assert "não encontrado" in out.output
