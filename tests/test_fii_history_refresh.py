from pathlib import Path
from typing import ClassVar

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.portfolio import fii_history_refresh
from iip.portfolio.fii_history_refresh import (
    HistoryRefreshOutcome,
    fii_positions,
    refresh_fii_histories,
)
from iip.portfolio.historical_series import (
    HistoricalObservation,
    HistoricalSeries,
    HistoricalSeriesStore,
)
from iip.portfolio.registry import PortfolioAsset
from iip.sources.cvm_fii_harvester import CvmFiiHTTPHarvester
from tests.test_cvm_fii import make_zip

CNPJ = "11.839.593/0001-09"  # o fundo que o zip de teste traz


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _Response:
    status = 200
    headers: ClassVar[dict[str, str]] = {"Content-Type": "application/zip"}

    def read(self):
        return make_zip()

    def geturl(self):
        return "https://dados.cvm.gov.br/final/fii.zip"


def _harvester():
    return CvmFiiHTTPHarvester(opener=lambda request, timeout: _Response())


def _position(ticker="BTLG11", cnpj=CNPJ, subtype="FII"):
    return PortfolioAsset(ticker, "fund", subtype=subtype, cnpj=cnpj)


def _observation(period, nav=100.0):
    return HistoricalObservation(
        period=period,
        patrimonio_liquido=1e9,
        valor_patrimonial_cotas=nav,
        dividend_yield_mes=0.008,
        rentabilidade_patrimonial_mes=None,
        valor_ativo=None,
        total_numero_cotistas=None,
        document_id="d",
        document_hash="h",
        discovered_year=2026,
    )


def _stored(ticker, periods, adjustments=()):
    return HistoricalSeries(
        ticker=ticker,
        cnpj="11839593000109",
        provider="cvm",
        observations=tuple(_observation(p) for p in periods),
        source_documents=(),
        adjustments=tuple(adjustments),
    )


def test_only_fiis_with_a_verified_cnpj_are_refreshed():
    positions = (
        _position("BTLG11"),
        _position("NOCNPJ11", cnpj=None),
        _position("CDII11", subtype="FI-Infra"),
        PortfolioAsset("ITUB4", "equity", cnpj="1"),
    )

    assert [p.ticker for p in fii_positions(positions)] == ["BTLG11"]


def test_a_refresh_saves_the_series_from_the_cvm_file(tmp_path: Path):
    store = HistoricalSeriesStore(tmp_path)

    outcomes = refresh_fii_histories(
        (_position(),), store=store, years=range(2026, 2027), harvester=_harvester()
    )

    assert outcomes == (
        HistoryRefreshOutcome(
            "BTLG11",
            "ok",
            "série atualizada",
            observations=1,
            added=1,
            last_period="2026-07",
        ),
    )
    assert store.load("BTLG11").observations[0].valor_patrimonial_cotas == 15.16


def test_a_collection_with_fewer_months_keeps_the_stored_series(tmp_path: Path):
    store = HistoricalSeriesStore(tmp_path)
    store.save(_stored("BTLG11", ["2026-05-01", "2026-06-01", "2026-07-01"]))

    outcomes = refresh_fii_histories(
        (_position(),), store=store, years=range(2026, 2027), harvester=_harvester()
    )

    assert outcomes[0].status == "erro"
    assert "série mantida" in outcomes[0].detail
    assert len(store.load("BTLG11").observations) == 3


def _spy_on_normalisation(monkeypatch):
    calls = []

    def spy(series):
        calls.append(series.ticker)
        return series

    monkeypatch.setattr(fii_history_refresh, "normalize_quota_splits", spy)
    return calls


def test_a_confirmed_split_adjustment_is_reapplied(tmp_path: Path, monkeypatch):
    calls = _spy_on_normalisation(monkeypatch)
    store = HistoricalSeriesStore(tmp_path)
    adjustment = {
        "period": "2026-07-01",
        "field": "valor_patrimonial_cotas",
        "factor": 2.0,
    }
    store.save(_stored("BTLG11", ["2026-07-01"], adjustments=[adjustment]))

    refresh_fii_histories(
        (_position(),), store=store, years=range(2026, 2027), harvester=_harvester()
    )

    # a coleta crua devolve a cota na escala antiga: sem reaplicar, o ajuste se perderia
    assert calls == ["BTLG11"]


def test_a_series_without_a_confirmed_adjustment_is_not_rescaled(
    tmp_path: Path, monkeypatch
):
    calls = _spy_on_normalisation(monkeypatch)
    store = HistoricalSeriesStore(tmp_path)

    refresh_fii_histories(
        (_position(),), store=store, years=range(2026, 2027), harvester=_harvester()
    )

    assert calls == []


def test_a_fund_the_file_does_not_have_is_an_isolated_error(tmp_path: Path):
    store = HistoricalSeriesStore(tmp_path)

    outcomes = refresh_fii_histories(
        (_position("OTHER11", cnpj="99.999.999/0001-99"), _position()),
        store=store,
        years=range(2026, 2027),
        harvester=_harvester(),
    )

    assert [o.status for o in outcomes] == ["erro", "ok"]
    assert "nenhum mês" in outcomes[0].detail
    assert not store.path_for("OTHER11").exists()


def test_a_network_failure_is_isolated_and_keeps_the_stored_series(tmp_path: Path):
    store = HistoricalSeriesStore(tmp_path)
    store.save(_stored("BTLG11", ["2026-06-01", "2026-07-01"]))

    def broken(request, timeout):
        raise OSError("sem rede")

    outcomes = refresh_fii_histories(
        (_position(),),
        store=store,
        years=range(2026, 2027),
        harvester=CvmFiiHTTPHarvester(opener=broken),
    )

    assert outcomes[0].status == "erro" and "sem rede" in outcomes[0].detail
    assert len(store.load("BTLG11").observations) == 2


# --- CLI -----------------------------------------------------------------------


def _patch(monkeypatch, outcomes, captured=None):
    def fake(positions, **kwargs):
        if captured is not None:
            captured["positions"] = positions
            captured["years"] = kwargs["years"]
        return outcomes

    monkeypatch.setattr(fii_history_refresh, "refresh_fii_histories", fake)


def test_command_lists_each_fund_and_summarises(monkeypatch, tmp_path):
    _patch(
        monkeypatch,
        (
            HistoryRefreshOutcome("BTLG11", "ok", "série atualizada", 68, 1, "2026-08"),
            HistoryRefreshOutcome("XPML11", "ok", "série atualizada", 68, 0, "2026-08"),
        ),
    )

    out = CliRunner().invoke(
        cli, ["collect-fii-history", "--vault", str(tmp_path), "--sem-evidencia"]
    )

    assert out.exit_code == 0, out.output
    assert "BTLG11" in out.output and "2026-08" in out.output
    assert "2 ok, 0 erro, 0 pulado" in out.output


def test_command_exits_with_an_error_when_a_fund_fails(monkeypatch, tmp_path):
    _patch(monkeypatch, (HistoryRefreshOutcome("BTLG11", "erro", "sem rede"),))

    out = CliRunner().invoke(
        cli, ["collect-fii-history", "--vault", str(tmp_path), "--sem-evidencia"]
    )

    assert out.exit_code == 1
    assert "sem rede" in out.output


def test_command_filters_by_ticker_and_year(monkeypatch, tmp_path):
    captured = {}
    _patch(monkeypatch, (), captured)

    CliRunner().invoke(
        cli,
        [
            "collect-fii-history",
            "--vault",
            str(tmp_path),
            "--sem-evidencia",
            "--ticker",
            "hgru11",
            "--desde-ano",
            "2024",
        ],
    )

    assert [p.ticker for p in captured["positions"]] == ["HGRU11"]
    assert captured["years"].start == 2024


def test_command_rejects_a_ticker_that_is_not_a_portfolio_fii(tmp_path):
    out = CliRunner().invoke(
        cli,
        ["collect-fii-history", "--vault", str(tmp_path), "--ticker", "ITUB4"],
    )

    assert out.exit_code != 0
    assert "ITUB4" in out.output
