import json

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.sources.sparta_reports import SpartaReportTarget
from iip.sources.sparta_reports_harvester import (
    FetchedSpartaReport,
    SpartaReportsHTTPHarvester,
)


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings, get_settings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _fake_fetch(cota_by_month: dict[tuple[int, int], float]):
    def fetch(self, target: SpartaReportTarget) -> FetchedSpartaReport:
        cota = cota_by_month.get((target.ano, target.mes))
        if cota is None:
            from urllib.error import HTTPError

            raise HTTPError(target.url, 404, "Not Found", {}, None)
        return FetchedSpartaReport(
            target=target, status_code=200, body=b"fake-pdf", cota_patrimonial=cota
        )

    return fetch


def test_collect_sparta_history_persists_series_and_prints_table(monkeypatch, tmp_path):
    monkeypatch.setattr(
        SpartaReportsHTTPHarvester,
        "fetch",
        _fake_fetch({(2026, 2): 101.71, (2026, 3): 101.64}),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "collect-sparta-history",
            "--ticker",
            "CRAA11",
            "--desde",
            "2026-02",
            "--ate",
            "2026-03",
            "--vault",
            str(tmp_path),
            "--sem-evidencia",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "101.71" in result.output
    assert "101.64" in result.output

    series_path = tmp_path / "02_Portfolio" / "Historical" / "CRAA11.json"
    data = json.loads(series_path.read_text(encoding="utf-8"))
    assert data["provider"] == "sparta_reports"
    assert [o["period"] for o in data["observations"]] == ["2026-02-01", "2026-03-01"]


def test_collect_sparta_history_skips_unpublished_month_without_failing(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        SpartaReportsHTTPHarvester, "fetch", _fake_fetch({(2026, 3): 101.64})
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "collect-sparta-history",
            "--ticker",
            "CRAA11",
            "--desde",
            "2026-03",
            "--ate",
            "2026-04",
            "--vault",
            str(tmp_path),
            "--sem-evidencia",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "HTTP 404" in result.output

    series_path = tmp_path / "02_Portfolio" / "Historical" / "CRAA11.json"
    data = json.loads(series_path.read_text(encoding="utf-8"))
    assert len(data["observations"]) == 1
    assert data["observations"][0]["period"] == "2026-03-01"


def test_collect_sparta_history_rejects_invalid_month_format(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "collect-sparta-history",
            "--desde",
            "not-a-month",
            "--vault",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0


def test_collect_sparta_history_rejects_desde_after_ate(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "collect-sparta-history",
            "--desde",
            "2026-05",
            "--ate",
            "2026-01",
            "--vault",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0


def test_collect_sparta_history_persists_atlas_evidence_by_default(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        SpartaReportsHTTPHarvester, "fetch", _fake_fetch({(2026, 3): 101.64})
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "collect-sparta-history",
            "--ticker",
            "CRAA11",
            "--desde",
            "2026-03",
            "--ate",
            "2026-03",
            "--vault",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    evidence_dir = tmp_path / "04_Evidence"
    assert evidence_dir.exists()
    assert any(evidence_dir.iterdir())
