from pathlib import Path
from typing import ClassVar

from iip.portfolio.historical_series import (
    HistoricalObservation,
    HistoricalSeries,
    HistoricalSeriesStore,
    collect_cvm_fii_history,
    normalize_quota_splits,
)
from iip.sources.cvm_fii_harvester import CvmFiiHTTPHarvester
from tests.test_cvm_fii import make_zip


class Response:
    status = 200
    headers: ClassVar[dict[str, str]] = {"Content-Type": "application/zip"}

    def read(self):
        return make_zip()

    def geturl(self):
        return "https://dados.cvm.gov.br/final/fii.zip"


def test_collect_cvm_history_persists_observations_and_source_link(tmp_path: Path):
    store = HistoricalSeriesStore(tmp_path / "vault")
    series = collect_cvm_fii_history(
        "BTLG11",
        "11.839.593/0001-09",
        range(2026, 2027),
        store=store,
        harvester=CvmFiiHTTPHarvester(opener=lambda request, timeout: Response()),
    )

    assert len(series.observations) == 1
    observation = series.observations[0]
    assert observation.period == "2026-07-01"
    assert observation.valor_patrimonial_cotas == 15.16
    assert observation.document_hash
    assert observation.document_id.startswith("cvm:BTLG11:2026:")

    loaded = store.load("BTLG11")
    assert loaded == series
    assert store.path_for("BTLG11").exists()


class FakeBridge:
    def __init__(self):
        self.persisted = []

    def persist_evidence(self, evidence):
        self.persisted.append(evidence)
        return evidence


def test_collect_cvm_history_persists_atlas_evidence_when_bridge_given(tmp_path: Path):
    store = HistoricalSeriesStore(tmp_path / "vault")
    bridge = FakeBridge()

    collect_cvm_fii_history(
        "BTLG11",
        "11.839.593/0001-09",
        range(2026, 2027),
        store=store,
        harvester=CvmFiiHTTPHarvester(opener=lambda request, timeout: Response()),
        bridge=bridge,
    )

    assert len(bridge.persisted) == 1
    evidence = bridge.persisted[0]
    assert evidence.ticker == "BTLG11"
    assert evidence.source_type == "atlas"
    assert evidence.document_hash


def _observation(period: str, valor_patrimonial_cotas: float) -> HistoricalObservation:
    return HistoricalObservation(
        period=period,
        patrimonio_liquido=1_000_000_000.0,
        valor_patrimonial_cotas=valor_patrimonial_cotas,
        dividend_yield_mes=0.01,
        rentabilidade_patrimonial_mes=0.0,
        valor_ativo=1_005_000_000.0,
        total_numero_cotistas=30_000.0,
        document_id="doc",
        document_hash="hash",
        discovered_year=2023,
    )


def test_normalize_quota_splits_rescales_pre_break_nav_only():
    series = HistoricalSeries(
        ticker="BTCI11",
        cnpj="09552812000114",
        provider="cvm",
        observations=(
            _observation("2022-12-01", 90.56597),
            _observation("2023-01-01", 10.06605),
            _observation("2023-02-01", 10.103596),
        ),
        source_documents=(),
    )
    assert series.scale_breaks

    normalized = normalize_quota_splits(series)

    assert normalized.scale_breaks == ()
    assert normalized.observations[0].valor_patrimonial_cotas == (
        90.56597 / (90.56597 / 10.06605)
    )
    assert normalized.observations[0].patrimonio_liquido == 1_000_000_000.0
    assert normalized.observations[1].valor_patrimonial_cotas == 10.06605
    assert normalized.adjustments[0]["period"] == "2023-01-01"


def test_normalize_quota_splits_persists_and_reloads_adjustments(tmp_path: Path):
    store = HistoricalSeriesStore(tmp_path / "vault")
    series = HistoricalSeries(
        ticker="BTCI11",
        cnpj="09552812000114",
        provider="cvm",
        observations=(
            _observation("2022-12-01", 90.56597),
            _observation("2023-01-01", 10.06605),
        ),
        source_documents=(),
    )

    store.save(normalize_quota_splits(series))
    reloaded = store.load("BTCI11")

    assert reloaded.scale_breaks == ()
    assert reloaded.adjustments[0]["field"] == "valor_patrimonial_cotas"
