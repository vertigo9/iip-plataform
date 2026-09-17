from pathlib import Path

from iip.portfolio.historical_series import (
    HistoricalSeriesStore,
    collect_cvm_fii_history,
)
from iip.sources.cvm_fii_harvester import CvmFiiHTTPHarvester
from tests.test_cvm_fii import make_zip


class Response:
    status = 200
    headers = {"Content-Type": "application/zip"}

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
