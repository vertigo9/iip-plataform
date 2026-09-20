from datetime import date

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.obsidian.series_report import render_series_report, write_series_report
from iip.portfolio import fii_history_refresh
from iip.portfolio.fii_history_refresh import HistoryRefreshOutcome
from iip.portfolio.historical_series import (
    HistoricalObservation,
    HistoricalSeries,
    HistoricalSeriesStore,
)
from iip.portfolio.series_state import (
    SeriesState,
    compute_state,
    load_state_file,
    save_state_file,
    series_alerts,
    write_alert_file,
)

TODAY = date(2026, 9, 20)


def _today():
    # a data que o comando usa (calendário local), não um timestamp
    return date.today()  # noqa: DTZ011


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


def _months(values, start=(2026, 3)):
    year, month = start
    out = []
    for value in values:
        out.append(_obs(f"{year:04d}-{month:02d}", value, nav=100.0 + len(out) * 0.01))
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return out


def _save(store, ticker, observations):
    store.save(
        HistoricalSeries(ticker, "0", "cvm", tuple(observations), source_documents=())
    )


def _state(ticker="HGRU11", code="regular", stale=False, last="2026-08"):
    return SeriesState(ticker, code, last, 12, "2026-09-20", stale)


# --- compute_state -------------------------------------------------------------


def test_a_regular_recent_series_is_healthy(tmp_path):
    store = HistoricalSeriesStore(tmp_path)
    _save(store, "HGRU11", _months([0.95] * 6))  # 2026-03 .. 2026-08

    state = compute_state("HGRU11", store, today=TODAY, refreshed_at="2026-09-20")

    assert (state.code, state.stale, state.last_period, state.months) == (
        "regular",
        False,
        "2026-08",
        6,
    )
    assert state.refreshed_at == "2026-09-20"


def test_a_missing_series_is_absent(tmp_path):
    state = compute_state(
        "HGRU11", HistoricalSeriesStore(tmp_path), today=TODAY, refreshed_at=None
    )

    assert state.code == "absent" and state.months == 0 and state.last_period is None


def test_zero_and_irregular_series_get_their_own_code(tmp_path):
    store = HistoricalSeriesStore(tmp_path)
    _save(store, "BTCI11", _months([0.0] * 6))
    _save(store, "XPML11", _months([0.3, 0.36, 0.86, 1.47, 0.2, 1.9]))

    assert compute_state("BTCI11", store, today=TODAY, refreshed_at=None).code == "zero"
    assert (
        compute_state("XPML11", store, today=TODAY, refreshed_at=None).code
        == "irregular"
    )


def test_a_series_that_stopped_three_months_ago_is_stale(tmp_path):
    store = HistoricalSeriesStore(tmp_path)
    _save(store, "OLD11", _months([0.5] * 6, start=(2026, 1)))  # ate 2026-06

    state = compute_state("OLD11", store, today=TODAY, refreshed_at=None)

    assert state.last_period == "2026-06" and state.stale


def test_the_month_before_last_is_not_yet_stale(tmp_path):
    store = HistoricalSeriesStore(tmp_path)
    _save(store, "OK11", _months([0.5] * 6, start=(2026, 2)))  # ate 2026-07

    assert not compute_state("OK11", store, today=TODAY, refreshed_at=None).stale


# --- alerts --------------------------------------------------------------------


def test_the_first_run_flags_every_current_problem_once():
    alerts = series_alerts(
        {}, (_state("A11"), _state("B11", "zero"), _state("C11", stale=True))
    )

    assert {(a.ticker, a.kind) for a in alerts} == {
        ("B11", "piorou"),
        ("C11", "defasada"),
    }


def test_a_series_that_was_already_bad_does_not_realert():
    previous = {"B11": {"code": "zero", "stale": False}}

    assert series_alerts(previous, (_state("B11", "zero"),)) == ()


def test_regular_to_irregular_alerts_and_says_what_it_was():
    previous = {"X11": {"code": "regular", "stale": False}}

    (alert,) = series_alerts(previous, (_state("X11", "irregular"),))

    assert alert.kind == "piorou" and "irregular" in alert.detail
    assert "era regular" in alert.detail


def test_a_recovery_is_not_an_alert():
    previous = {"X11": {"code": "irregular", "stale": True}}

    assert series_alerts(previous, (_state("X11", "regular"),)) == ()


def test_going_stale_alerts_once():
    previous = {"X11": {"code": "regular", "stale": False}}

    first = series_alerts(previous, (_state("X11", stale=True, last="2026-06"),))
    again = series_alerts(
        {"X11": {"code": "regular", "stale": True}},
        (_state("X11", stale=True, last="2026-06"),),
    )

    assert [a.kind for a in first] == ["defasada"] and again == ()


def test_an_absent_series_alerts_once_and_not_as_a_worsening():
    absent = SeriesState("Z11", "absent", None, 0, None, False)

    (first,) = series_alerts({}, (absent,))
    again = series_alerts({"Z11": {"code": "absent"}}, (absent,))

    assert first.kind == "ausente" and again == ()


def test_the_alert_file_has_a_line_per_alert_and_is_removed_when_clean(tmp_path):
    path = tmp_path / "alertas_series.txt"
    alerts = series_alerts({}, (_state("B11", "zero"),))

    write_alert_file(path, alerts)
    assert path.read_text(encoding="utf-8").startswith("B11: série piorou")

    write_alert_file(path, ())
    assert not path.exists()


# --- state file ----------------------------------------------------------------


def test_the_state_file_round_trips(tmp_path):
    states = (_state("A11"), _state("B11", "zero", stale=True))

    save_state_file(tmp_path, states)
    loaded = load_state_file(tmp_path)

    assert loaded["B11"]["code"] == "zero" and loaded["B11"]["stale"] is True
    assert SeriesState.from_dict("B11", loaded["B11"]) == states[1]


def test_a_missing_or_corrupt_state_file_is_empty(tmp_path):
    assert load_state_file(tmp_path) == {}
    path = tmp_path / "02_Portfolio" / "Historical" / "_estado.json"
    path.parent.mkdir(parents=True)
    path.write_text("{nao e json", encoding="utf-8")
    assert load_state_file(tmp_path) == {}


# --- note ----------------------------------------------------------------------


def test_the_note_lists_problems_first_with_the_update_date(tmp_path):
    states = (_state("OK11"), _state("BAD11", "irregular"), _state("OLD11", stale=True))
    alerts = series_alerts({}, states)

    text = render_series_report(states, alerts, today_iso="2026-09-20")

    assert "3 séries; **2 com problema**" in text
    rows = [
        ln for ln in text.splitlines() if ln.startswith("| ") and "Ticker" not in ln
    ]
    assert [r.split(" | ")[0].removeprefix("| ") for r in rows][-1] == "OK11"
    assert "2026-09-20" in text and "Mudanças desta atualização" in text
    assert write_series_report(
        tmp_path, states, alerts, today_iso="2026-09-20"
    ).exists()


# --- CLI -----------------------------------------------------------------------


def _patch_refresh(monkeypatch, outcomes=(), captured=None):
    def fake(positions, **kwargs):
        if captured is not None:
            captured["tickers"] = [p.ticker for p in positions]
        return outcomes or tuple(
            HistoryRefreshOutcome(p.ticker, "ok", "série atualizada", 6, 0, "2026-08")
            for p in positions
        )

    monkeypatch.setattr(fii_history_refresh, "refresh_fii_histories", fake)


def _vault(tmp_path, tickers=("HGRU11",)):
    vault = tmp_path / "vault"
    store = HistoricalSeriesStore(vault)
    for ticker in tickers:
        _save(store, ticker, _months([0.95] * 6))
    return vault


def test_command_records_the_state_and_writes_the_note_and_alert_file(
    monkeypatch, tmp_path
):
    _patch_refresh(monkeypatch)
    vault = _vault(tmp_path)
    alert = tmp_path / "alertas.txt"

    out = CliRunner().invoke(
        cli,
        [
            "collect-fii-history",
            "--vault",
            str(vault),
            "--sem-evidencia",
            "--ticker",
            "HGRU11",
            "--report",
            "--alert-file",
            str(alert),
        ],
    )

    assert out.exit_code == 0, out.output
    state = load_state_file(vault)
    assert state["HGRU11"]["code"] == "regular"
    assert state["HGRU11"]["refreshed_at"] is not None
    assert (vault / "02_Portfolio" / "Series.md").exists()
    assert not alert.exists()  # HGRU11 está sã: nada a avisar


def test_command_alerts_a_series_that_is_missing(monkeypatch, tmp_path):
    _patch_refresh(monkeypatch)
    vault = tmp_path / "vault"
    alert = tmp_path / "alertas.txt"

    CliRunner().invoke(
        cli,
        [
            "collect-fii-history",
            "--vault",
            str(vault),
            "--sem-evidencia",
            "--ticker",
            "HGRU11",
            "--alert-file",
            str(alert),
        ],
    )

    assert "HGRU11: série ausente" in alert.read_text(encoding="utf-8")


def test_min_age_days_skips_when_every_series_is_recent(monkeypatch, tmp_path):
    captured = {"tickers": None}
    _patch_refresh(monkeypatch, captured=captured)
    vault = _vault(tmp_path)
    save_state_file(
        vault,
        (SeriesState("HGRU11", "regular", "2026-08", 6, _today().isoformat(), False),),
    )

    out = CliRunner().invoke(
        cli,
        [
            "collect-fii-history",
            "--vault",
            str(vault),
            "--sem-evidencia",
            "--ticker",
            "HGRU11",
            "--min-age-days",
            "6",
        ],
    )

    assert out.exit_code == 0, out.output
    assert "Séries em dia" in out.output
    assert captured["tickers"] is None  # não baixou nada


def test_min_age_days_refreshes_only_the_old_or_never_refreshed(monkeypatch, tmp_path):
    captured = {}
    _patch_refresh(monkeypatch, captured=captured)
    vault = _vault(tmp_path, tickers=("HGRU11", "KNRI11"))
    save_state_file(
        vault,
        (
            SeriesState("HGRU11", "regular", "2026-08", 6, "2020-01-01", False),
            SeriesState("KNRI11", "regular", "2026-08", 6, _today().isoformat(), False),
        ),
    )

    CliRunner().invoke(
        cli,
        [
            "collect-fii-history",
            "--vault",
            str(vault),
            "--sem-evidencia",
            "--ticker",
            "HGRU11",
            "--ticker",
            "KNRI11",
            "--min-age-days",
            "6",
        ],
    )

    assert captured["tickers"] == ["HGRU11"]
    state = load_state_file(vault)
    assert state["HGRU11"]["refreshed_at"] == _today().isoformat()


def test_a_failed_refresh_keeps_the_old_update_date_and_exits_with_error(
    monkeypatch, tmp_path
):
    _patch_refresh(monkeypatch, (HistoryRefreshOutcome("HGRU11", "erro", "sem rede"),))
    vault = _vault(tmp_path)
    save_state_file(
        vault, (SeriesState("HGRU11", "regular", "2026-08", 6, "2026-09-01", False),)
    )

    out = CliRunner().invoke(
        cli,
        [
            "collect-fii-history",
            "--vault",
            str(vault),
            "--sem-evidencia",
            "--ticker",
            "HGRU11",
        ],
    )

    assert out.exit_code == 1
    assert load_state_file(vault)["HGRU11"]["refreshed_at"] == "2026-09-01"
