from pathlib import Path

from iip.portfolio.historical_series import HistoricalSeriesStore, collect_cotahist_history
from iip.sources.b3_cotahist import CotahistQuote


class _FetchedCotahist:
    def __init__(self, quotes, body=b"fake-cotahist-body"):
        self.quotes = quotes
        self.status_code = 200
        self.body = body
        self.final_url = ""
        self.content_hash = "unused-superseded-by-AtlasDocument.build"


class FakeCotahistHarvester:
    def __init__(self, quotes_by_year: dict[int, list[CotahistQuote]]):
        self._quotes_by_year = quotes_by_year
        self.calls: list[tuple[int, frozenset]] = []

    def fetch(self, target, *, tickers=None):
        self.calls.append((target.year, tickers))
        all_quotes = self._quotes_by_year.get(target.year, [])
        matched = tuple(q for q in all_quotes if tickers is None or q.ticker in tickers)
        return _FetchedCotahist(matched, body=f"fake-body-{target.year}".encode())


def _quote(ticker: str, date: str, close: float) -> CotahistQuote:
    return CotahistQuote(
        ticker=ticker, date=date, open=close, high=close, low=close, avg=close,
        close=close, trades=100, volume=close * 1000,
    )


def test_collect_cotahist_history_filters_by_ticker_and_persists(tmp_path: Path):
    harvester = FakeCotahistHarvester(
        {
            2025: [_quote("BBSE3", "2025-12-30", 38.0), _quote("PETR4", "2025-12-30", 30.0)],
            2026: [_quote("BBSE3", "2026-09-17", 40.41)],
        }
    )
    store = HistoricalSeriesStore(tmp_path)

    series = collect_cotahist_history(
        "bbse3", (2025, 2026), store=store, harvester=harvester
    )

    assert series.ticker == "BBSE3"
    assert series.cnpj == ""
    assert series.provider == "b3_cotahist"
    assert [o.period for o in series.observations] == ["2025-12-30", "2026-09-17"]
    assert series.observations[-1].valor_patrimonial_cotas == 40.41
    assert harvester.calls == [(2025, frozenset({"BBSE3"})), (2026, frozenset({"BBSE3"}))]

    reloaded = store.load("BBSE3")
    assert reloaded == series


def test_collect_cotahist_history_handles_ticker_with_no_coverage(tmp_path: Path):
    harvester = FakeCotahistHarvester({2026: []})
    store = HistoricalSeriesStore(tmp_path)

    series = collect_cotahist_history("LFTB11", (2026,), store=store, harvester=harvester)

    assert series.observations == ()
    assert series.source_documents[0]["matched"] is False


class FakeBridge:
    def __init__(self):
        self.persisted = []

    def persist_evidence(self, evidence):
        self.persisted.append(evidence)
        return evidence


def test_collect_cotahist_history_persists_atlas_evidence_when_bridge_given(tmp_path: Path):
    harvester = FakeCotahistHarvester({2026: [_quote("BBSE3", "2026-09-17", 40.41)]})
    store = HistoricalSeriesStore(tmp_path)
    bridge = FakeBridge()

    collect_cotahist_history("BBSE3", (2026,), store=store, harvester=harvester, bridge=bridge)

    assert len(bridge.persisted) == 1
    evidence = bridge.persisted[0]
    assert evidence.ticker == "BBSE3"
    assert evidence.source_type == "atlas"
    assert evidence.document_hash


def test_collect_cotahist_history_requires_ticker():
    store = HistoricalSeriesStore("unused")
    try:
        collect_cotahist_history("", (2026,), store=store, harvester=FakeCotahistHarvester({}))
        assert False, "expected ValueError"
    except ValueError:
        pass
