from pathlib import Path
from urllib.error import HTTPError

from iip.portfolio.historical_series import (
    HistoricalSeriesStore,
    collect_sparta_report_history,
)


class _FetchedSpartaReport:
    def __init__(self, cota_patrimonial, body=b"fake-pdf-body"):
        self.status_code = 200
        self.body = body
        self.cota_patrimonial = cota_patrimonial
        self.final_url = ""


class FakeSpartaHarvester:
    def __init__(self, cota_by_month: dict[tuple[int, int], float | None]):
        self._cota_by_month = cota_by_month
        self.calls: list[tuple[int, int]] = []

    def fetch(self, target):
        self.calls.append((target.ano, target.mes))
        key = (target.ano, target.mes)
        if key not in self._cota_by_month:
            raise HTTPError(target.url, 404, "Not Found", {}, None)
        return _FetchedSpartaReport(self._cota_by_month[key])


def test_collect_sparta_report_history_builds_observations_and_persists(tmp_path: Path):
    harvester = FakeSpartaHarvester({(2026, 2): 101.71, (2026, 3): 101.64})
    store = HistoricalSeriesStore(tmp_path)

    series = collect_sparta_report_history(
        "CRAA11", ((2026, 2), (2026, 3)), store=store, harvester=harvester
    )

    assert series.provider == "sparta_reports"
    assert series.cnpj == ""
    assert [o.period for o in series.observations] == ["2026-02-01", "2026-03-01"]
    assert series.observations[0].valor_patrimonial_cotas == 101.71
    assert series.observations[1].valor_patrimonial_cotas == 101.64
    assert harvester.calls == [(2026, 2), (2026, 3)]

    reloaded = store.load("CRAA11")
    assert reloaded == series


def test_collect_sparta_report_history_skips_404_months_without_raising(tmp_path: Path):
    harvester = FakeSpartaHarvester({(2026, 3): 101.64})
    store = HistoricalSeriesStore(tmp_path)

    series = collect_sparta_report_history(
        "CRAA11", ((2026, 4), (2026, 3)), store=store, harvester=harvester
    )

    assert len(series.observations) == 1
    assert series.observations[0].period == "2026-03-01"
    not_found = next(d for d in series.source_documents if d["ano"] == 2026 and d["mes"] == 4)
    assert not_found["matched"] is False
    assert not_found["error"] == "HTTP 404"


def test_collect_sparta_report_history_skips_when_layout_extraction_returns_none(tmp_path: Path):
    harvester = FakeSpartaHarvester({(2026, 3): None})
    store = HistoricalSeriesStore(tmp_path)

    series = collect_sparta_report_history(
        "CRAA11", ((2026, 3),), store=store, harvester=harvester
    )

    assert series.observations == ()
    assert series.source_documents[0]["matched"] is False


class FakeBridge:
    def __init__(self):
        self.persisted = []

    def persist_evidence(self, evidence):
        self.persisted.append(evidence)
        return evidence


def test_collect_sparta_report_history_persists_atlas_evidence_when_bridge_given(tmp_path: Path):
    harvester = FakeSpartaHarvester({(2026, 3): 101.64})
    store = HistoricalSeriesStore(tmp_path)
    bridge = FakeBridge()

    collect_sparta_report_history(
        "CRAA11", ((2026, 3),), store=store, harvester=harvester, bridge=bridge
    )

    assert len(bridge.persisted) == 1
    evidence = bridge.persisted[0]
    assert evidence.ticker == "CRAA11"
    assert evidence.source_type == "atlas"
    assert evidence.document_hash


def test_collect_sparta_report_history_requires_ticker():
    store = HistoricalSeriesStore("unused")
    try:
        collect_sparta_report_history(
            "", ((2026, 3),), store=store, harvester=FakeSpartaHarvester({})
        )
        assert False, "expected ValueError"
    except ValueError:
        pass
