from pathlib import Path

from iip.portfolio.historical_series import (
    HistoricalSeriesStore,
    collect_cvm_diario_history,
)
from iip.sources.cvm_renda_fixa import InformeDiario


class _FetchedDiario:
    def __init__(self, informes, body=b"fake-zip-body"):
        self.informes = informes
        self.status_code = 200
        self.body = body


class FakeDiarioHarvester:
    def __init__(self, informes_by_month: dict[tuple[int, int], list[InformeDiario]]):
        self._informes_by_month = informes_by_month
        self.calls: list[tuple[int, int]] = []

    def fetch_diario(self, target):
        self.calls.append((target.ano, target.mes))
        return _FetchedDiario(self._informes_by_month.get((target.ano, target.mes), []))


def _informe(
    cnpj: str, data: str, valor_cota: float, pl: float = 1_000_000.0
) -> InformeDiario:
    return InformeDiario(
        tipo_fundo_classe="CLASSES - FIF",
        cnpj_fundo_classe=cnpj,
        id_subclasse=None,
        data_competencia=data,
        valor_total=pl * 1.01,
        valor_cota=valor_cota,
        patrimonio_liquido=pl,
        captacao_dia=0.0,
        resgate_dia=0.0,
        numero_cotistas=100,
    )


def test_collect_cvm_diario_history_filters_by_cnpj_and_persists(tmp_path: Path):
    cnpj = "45.121.022/0001-48"
    harvester = FakeDiarioHarvester(
        {
            (2026, 8): [
                _informe("45121022000148", "2026-08-14", 1.85),
                _informe("99999999000199", "2026-08-14", 500.0),
            ],
            (2026, 9): [
                _informe("45121022000148", "2026-09-01", 1.86),
                _informe("45121022000148", "2026-09-15", 1.88),
            ],
        }
    )
    store = HistoricalSeriesStore(tmp_path)

    series = collect_cvm_diario_history(
        "AXIA3",
        cnpj,
        ((2026, 8), (2026, 9)),
        store=store,
        harvester=harvester,
    )

    assert [o.period for o in series.observations] == ["2026-08-14", "2026-09-15"]
    assert series.observations[-1].valor_patrimonial_cotas == 1.88
    assert series.provider == "cvm_renda_fixa"
    assert harvester.calls == [(2026, 8), (2026, 9)]

    reloaded = store.load("AXIA3")
    assert reloaded == series
    assert store.path_for("AXIA3").exists()


def test_collect_cvm_diario_history_skips_months_without_a_match(tmp_path: Path):
    cnpj = "45.121.022/0001-48"
    harvester = FakeDiarioHarvester(
        {(2026, 8): [_informe("00000000000000", "2026-08-14", 1.0)]}
    )
    store = HistoricalSeriesStore(tmp_path)

    series = collect_cvm_diario_history(
        "AXIA3", cnpj, ((2026, 8),), store=store, harvester=harvester
    )

    assert series.observations == ()
    assert series.source_documents[0]["matched"] is False


class FakeBridge:
    def __init__(self):
        self.persisted = []

    def persist_evidence(self, evidence):
        self.persisted.append(evidence)
        return evidence


def test_collect_cvm_diario_history_persists_atlas_evidence_when_bridge_given(
    tmp_path: Path,
):
    cnpj = "45.121.022/0001-48"
    harvester = FakeDiarioHarvester(
        {(2026, 8): [_informe("45121022000148", "2026-08-14", 1.85)]}
    )
    store = HistoricalSeriesStore(tmp_path)
    bridge = FakeBridge()

    collect_cvm_diario_history(
        "AXIA3", cnpj, ((2026, 8),), store=store, harvester=harvester, bridge=bridge
    )

    assert len(bridge.persisted) == 1
    evidence = bridge.persisted[0]
    assert evidence.ticker == "AXIA3"
    assert evidence.source_type == "atlas"
    assert evidence.document_hash  # real sha256 of the fake body, not empty/fabricated


def test_collect_cvm_diario_history_requires_cnpj_digits(tmp_path: Path):
    store = HistoricalSeriesStore(tmp_path)
    try:
        collect_cvm_diario_history(
            "AXIA3", "", ((2026, 8),), store=store, harvester=FakeDiarioHarvester({})
        )
        assert False, "expected ValueError"
    except ValueError:
        pass
