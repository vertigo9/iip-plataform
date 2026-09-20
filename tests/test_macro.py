import gzip
import json
from dataclasses import dataclass
from datetime import date

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.macro.collector import (
    _sidra_reference,
    collect_indicator,
    collect_macro,
)
from iip.macro.context import build_context, period_end, read_indicator
from iip.macro.contract import (
    BACEN_SGS,
    CATEGORY_LABELS,
    DAILY,
    IBGE_SIDRA,
    INDICATORS,
    MONTHLY,
    QUARTERLY,
    indicator,
)
from iip.macro.store import MacroStore
from iip.obsidian import dashboard as dash
from iip.obsidian.macro_report import render_macro_report, write_macro_report
from iip.sources.bacen import BacenSeriesPoint
from iip.sources.ibge import IbgeDataPoint
from iip.sources.ibge_harvester import IbgeHTTPHarvester

TODAY = date(2026, 9, 20)


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --- the contract --------------------------------------------------------------


def test_the_catalog_is_internally_consistent():
    for ind in INDICATORS.values():
        assert ind.source in (BACEN_SGS, IBGE_SIDRA)
        assert ind.frequency in (DAILY, MONTHLY, QUARTERLY)
        assert ind.category in CATEGORY_LABELS
        assert ind.change_kind in ("pp", "pct", "none")
        assert ind.verified_by and ind.unit and ind.description
        assert ind.stale_after_days > 0
        if ind.source == BACEN_SGS:
            assert ind.source_ref.isdigit()
        else:
            agregado, variavel = ind.source_ref.split("/")
            assert agregado.isdigit() and variavel.isdigit()


def test_cross_checks_point_at_existing_indicators_and_are_reciprocal():
    for ind in INDICATORS.values():
        if ind.cross_check_with:
            other = INDICATORS[ind.cross_check_with]
            assert other.cross_check_with == ind.id
            assert {ind.source, other.source} == {BACEN_SGS, IBGE_SIDRA}


def test_the_current_month_of_an_accumulating_indicator_is_flagged_in_the_catalog():
    assert INDICATORS["selic_mes"].accumulates_in_month
    assert not INDICATORS["ipca_mensal"].accumulates_in_month


def test_an_unknown_indicator_says_what_the_catalog_has():
    with pytest.raises(KeyError) as excinfo:
        indicator("pib_do_futuro")

    assert "selic_meta" in str(excinfo.value)


# --- the store -----------------------------------------------------------------


def _pts(*items):
    return tuple((ref, value, False) for ref, value in items)


def test_a_first_collection_stores_every_point_with_its_collection_date(tmp_path):
    store = MacroStore(tmp_path)

    result = store.ingest(
        "ipca_mensal",
        _pts(("2026-07", 0.07), ("2026-08", -0.32)),
        collected_at="2026-09-20",
    )

    assert (result.new, result.revised, result.unchanged) == (2, 0, 0)
    obs = store.latest("ipca_mensal")
    assert [(o.reference, o.value, o.collected_at) for o in obs] == [
        ("2026-07", 0.07, "2026-09-20"),
        ("2026-08", -0.32, "2026-09-20"),
    ]


def test_collecting_the_same_values_again_adds_nothing(tmp_path):
    store = MacroStore(tmp_path)
    store.ingest("ipca_mensal", _pts(("2026-08", -0.32)), collected_at="2026-09-20")

    again = store.ingest(
        "ipca_mensal", _pts(("2026-08", -0.32)), collected_at="2026-09-21"
    )

    assert (again.new, again.revised, again.unchanged) == (0, 0, 1)
    assert len(store.observations("ipca_mensal")) == 1


def test_a_revised_value_is_kept_beside_the_old_one_never_replacing_it(tmp_path):
    store = MacroStore(tmp_path)
    store.ingest("ipca_mensal", _pts(("2026-08", -0.32)), collected_at="2026-09-20")

    revised = store.ingest(
        "ipca_mensal", _pts(("2026-08", -0.30)), collected_at="2026-10-10"
    )

    assert (revised.new, revised.revised) == (0, 1)
    assert [o.value for o in store.observations("ipca_mensal")] == [-0.32, -0.30]
    assert store.latest("ipca_mensal")[0].value == -0.30
    (history,) = store.revisions("ipca_mensal")
    assert [o.collected_at for o in history] == ["2026-09-20", "2026-10-10"]


def test_as_known_on_uses_only_what_had_been_collected_by_that_date(tmp_path):
    store = MacroStore(tmp_path)
    store.ingest("ipca_mensal", _pts(("2026-08", -0.32)), collected_at="2026-09-20")
    store.ingest(
        "ipca_mensal",
        _pts(("2026-08", -0.30), ("2026-09", 0.4)),
        collected_at="2026-10-10",
    )

    assert (
        store.as_known_on("ipca_mensal", "2026-09-19") == ()
    )  # antes da primeira coleta
    on_sept = store.as_known_on("ipca_mensal", "2026-09-30")
    assert [(o.reference, o.value) for o in on_sept] == [("2026-08", -0.32)]
    on_oct = store.as_known_on("ipca_mensal", "2026-10-10")
    assert [(o.reference, o.value) for o in on_oct] == [
        ("2026-08", -0.30),
        ("2026-09", 0.4),
    ]


def test_first_and_last_collection_dates(tmp_path):
    store = MacroStore(tmp_path)
    assert store.first_collected_at("selic_meta") is None
    store.ingest("selic_meta", _pts(("2026-09-19", 13.75)), collected_at="2026-09-20")
    store.ingest("selic_meta", _pts(("2026-09-20", 13.75)), collected_at="2026-09-21")

    assert store.first_collected_at("selic_meta") == "2026-09-20"
    assert store.last_collected_at("selic_meta") == "2026-09-21"


def test_a_provisional_value_that_closes_is_recorded_as_a_new_version(tmp_path):
    store = MacroStore(tmp_path)
    store.ingest("selic_mes", (("2026-09", 0.67, True),), collected_at="2026-09-20")

    result = store.ingest(
        "selic_mes", (("2026-09", 1.05, False),), collected_at="2026-10-02"
    )

    assert result.revised == 1
    first, last = store.observations("selic_mes")
    assert first.provisional and not last.provisional


def test_a_missing_or_corrupt_series_file_reads_as_empty(tmp_path):
    store = MacroStore(tmp_path)
    assert store.observations("selic_meta") == ()
    store.path_for("selic_meta").parent.mkdir(parents=True)
    store.path_for("selic_meta").write_text("{nao e json", encoding="utf-8")
    assert store.observations("selic_meta") == ()


def test_the_run_log_keeps_the_last_success_apart_from_the_last_attempt(tmp_path):
    store = MacroStore(tmp_path)
    store.record_run("ipca_mensal", collected_at="2026-09-20", status="ok")
    store.record_run(
        "ipca_mensal", collected_at="2026-09-21", status="erro", detail="sem rede"
    )

    run = store.runs()["ipca_mensal"]
    assert run["last_ok"] == "2026-09-20" and run["last_attempt"] == "2026-09-21"
    assert run["status"] == "erro" and run["detail"] == "sem rede"


# --- the collector -------------------------------------------------------------


@dataclass
class _Fetched:
    points: tuple


class _FakeBacen:
    def __init__(self, points=None, error=None):
        self.points, self.error, self.targets = points or {}, error, []

    def fetch(self, target):
        self.targets.append(target)
        if self.error:
            raise self.error
        return _Fetched(self.points.get(target.code, ()))


class _FakeIbge:
    def __init__(self, points=None):
        self.points, self.targets = points or {}, []

    def fetch(self, target):
        self.targets.append(target)
        return _Fetched(self.points.get((target.agregado, target.variavel), ()))


def _sgs(*items):
    return tuple(BacenSeriesPoint(date.fromisoformat(d), v) for d, v in items)


def _sidra(*items):
    return tuple(IbgeDataPoint("v", "nome", "%", "1", "Brasil", p, v) for p, v in items)


def test_daily_and_monthly_bacen_points_get_the_contract_competencia(tmp_path):
    bacen = _FakeBacen(
        {432: _sgs(("2026-09-19", 13.75)), 433: _sgs(("2026-08-01", -0.32))}
    )
    store = MacroStore(tmp_path)

    collect_indicator(
        indicator("selic_meta"), store, today=TODAY, bacen=bacen, ibge=None
    )
    collect_indicator(
        indicator("ipca_mensal"), store, today=TODAY, bacen=bacen, ibge=None
    )

    assert store.latest("selic_meta")[0].reference == "2026-09-19"
    assert store.latest("ipca_mensal")[0].reference == "2026-08"


def test_only_the_current_month_of_an_accumulating_series_is_provisional(tmp_path):
    bacen = _FakeBacen({4390: _sgs(("2026-08-01", 1.09), ("2026-09-01", 0.67))})
    store = MacroStore(tmp_path)

    collect_indicator(
        indicator("selic_mes"), store, today=TODAY, bacen=bacen, ibge=None
    )

    august, september = store.latest("selic_mes")
    assert not august.provisional and september.provisional


def test_ibge_periods_become_months_and_quarters_and_missing_values_are_skipped(
    tmp_path,
):
    ibge = _FakeIbge(
        {
            (1737, 63): _sidra(("202607", 0.07), ("202608", -0.32)),
            (4099, 4099): _sidra(("202601", 6.1), ("202602", 5.4), ("202603", None)),
        }
    )
    store = MacroStore(tmp_path)

    collect_indicator(
        indicator("ipca_mensal_ibge"), store, today=TODAY, bacen=None, ibge=ibge
    )
    collect_indicator(
        indicator("desocupacao_ibge"), store, today=TODAY, bacen=None, ibge=ibge
    )

    assert [o.reference for o in store.latest("ipca_mensal_ibge")] == [
        "2026-07",
        "2026-08",
    ]
    assert [o.reference for o in store.latest("desocupacao_ibge")] == [
        "2026-T1",
        "2026-T2",
    ]


def test_a_sidra_period_that_is_not_a_period_is_ignored():
    assert _sidra_reference("2026", MONTHLY) is None
    assert _sidra_reference("202613", MONTHLY) is None
    assert _sidra_reference("202605", QUARTERLY) is None
    assert _sidra_reference("202602", QUARTERLY) == "2026-T2"


def test_one_failing_source_is_isolated_and_recorded(tmp_path):
    store = MacroStore(tmp_path)
    bacen = _FakeBacen(error=OSError("sem rede"))

    outcomes = collect_macro(
        ("selic_meta", "ipca_mensal"), store, today=TODAY, bacen=bacen, ibge=_FakeIbge()
    )

    assert [o.status for o in outcomes] == ["erro", "erro"]
    assert "sem rede" in outcomes[0].detail
    run = store.runs()["selic_meta"]
    assert run["status"] == "erro" and "last_ok" not in run


def test_an_empty_answer_is_an_error_not_an_empty_series(tmp_path):
    outcome = collect_indicator(
        indicator("selic_meta"),
        MacroStore(tmp_path),
        today=TODAY,
        bacen=_FakeBacen({}),
        ibge=None,
    )

    assert outcome.status == "erro" and "nenhum ponto" in outcome.detail


def test_collecting_twice_reports_no_new_points_the_second_time(tmp_path):
    store = MacroStore(tmp_path)
    bacen = _FakeBacen({433: _sgs(("2026-08-01", -0.32))})

    first = collect_indicator(
        indicator("ipca_mensal"), store, today=TODAY, bacen=bacen, ibge=None
    )
    second = collect_indicator(
        indicator("ipca_mensal"), store, today=date(2026, 9, 21), bacen=bacen, ibge=None
    )

    assert (
        first.result.new == 1
        and second.result.new == 0
        and second.result.unchanged == 1
    )
    assert (
        second.status == "ok" and store.runs()["ipca_mensal"]["last_ok"] == "2026-09-21"
    )


def test_an_unknown_id_fails_before_collecting_anything(tmp_path):
    bacen = _FakeBacen({})

    with pytest.raises(KeyError):
        collect_macro(
            ("selic_meta", "xyz"),
            MacroStore(tmp_path),
            today=TODAY,
            bacen=bacen,
            ibge=_FakeIbge(),
        )

    assert bacen.targets == []


def test_the_bacen_window_respects_the_ten_year_limit(tmp_path):
    bacen = _FakeBacen({432: _sgs(("2026-09-19", 13.75))})

    collect_indicator(
        indicator("selic_meta"),
        MacroStore(tmp_path),
        today=TODAY,
        bacen=bacen,
        ibge=None,
    )

    target = bacen.targets[0]
    assert (target.end_date - target.start_date).days <= 3653


def test_the_ibge_harvester_reads_a_gzip_response():
    payload = json.dumps(
        [
            {
                "id": "63",
                "variavel": "IPCA",
                "unidade": "%",
                "resultados": [
                    {
                        "classificacoes": [],
                        "series": [
                            {
                                "localidade": {"id": "1", "nome": "Brasil"},
                                "serie": {"202608": "-0.32"},
                            }
                        ],
                    }
                ],
            }
        ]
    ).encode()

    class Response:
        status = 200

        def read(self):
            return gzip.compress(payload)

    harvester = IbgeHTTPHarvester(opener=lambda request, timeout: Response())
    from iip.sources.ibge import build_target

    fetched = harvester.fetch(build_target(1737, 63))

    assert [(p.periodo, p.value) for p in fetched.points] == [("202608", -0.32)]


# --- the context ---------------------------------------------------------------


def _seed(store, indicator_id, items, collected="2026-09-20"):
    store.ingest(
        indicator_id, tuple((r, v, False) for r, v in items), collected_at=collected
    )
    store.record_run(indicator_id, collected_at=collected, status="ok")


def test_period_end_by_frequency():
    assert period_end("2026-09-19", DAILY) == date(2026, 9, 19)
    assert period_end("2026-08", MONTHLY) == date(2026, 8, 31)
    assert period_end("2026-T2", QUARTERLY) == date(2026, 6, 30)


def test_a_rate_is_compared_with_twelve_months_earlier_in_percentage_points(tmp_path):
    store = MacroStore(tmp_path)
    _seed(store, "ipca_12m", [("2025-08", 5.13), ("2026-08", 4.22)])

    reading = read_indicator(indicator("ipca_12m"), store, TODAY)

    assert reading.latest.value == 4.22 and reading.year_ago.value == 5.13
    assert reading.change == pytest.approx(-0.91)


def test_a_level_is_compared_as_a_percentage_change(tmp_path):
    store = MacroStore(tmp_path)
    _seed(store, "ibc_br", [("2025-07", 100.0), ("2026-07", 104.0)])

    assert read_indicator(indicator("ibc_br"), store, TODAY).change == pytest.approx(
        4.0
    )


def test_a_monthly_flow_has_no_twelve_month_change(tmp_path):
    store = MacroStore(tmp_path)
    _seed(store, "ipca_mensal", [("2025-08", 0.2), ("2026-08", -0.32)])

    assert read_indicator(indicator("ipca_mensal"), store, TODAY).change is None


def test_a_daily_series_uses_the_last_value_up_to_the_same_day_a_year_earlier(tmp_path):
    store = MacroStore(tmp_path)
    _seed(
        store,
        "selic_meta",
        [("2025-09-19", 15.0), ("2025-09-22", 14.9), ("2026-09-20", 13.75)],
    )

    reading = read_indicator(indicator("selic_meta"), store, TODAY)

    assert (
        reading.year_ago.reference == "2025-09-19"
        and reading.change == pytest.approx(-1.25)
    )


def test_a_series_is_stale_only_after_its_window(tmp_path):
    store = MacroStore(tmp_path)
    _seed(store, "ipca_mensal", [("2026-06", 0.1)])  # fim de junho: 82 dias antes
    _seed(store, "selic_meta", [("2026-09-15", 13.75)])

    assert read_indicator(indicator("ipca_mensal"), store, TODAY).stale
    assert not read_indicator(indicator("selic_meta"), store, TODAY).stale


def test_an_indicator_never_collected_is_missing_not_zero(tmp_path):
    reading = read_indicator(indicator("selic_meta"), MacroStore(tmp_path), TODAY)

    assert reading.missing and reading.latest is None and not reading.stale


def test_two_sources_that_agree_and_two_that_do_not(tmp_path):
    store = MacroStore(tmp_path)
    _seed(store, "ipca_mensal", [("2026-07", 0.07), ("2026-08", -0.32)])
    _seed(store, "ipca_mensal_ibge", [("2026-07", 0.07), ("2026-08", -0.32)])
    context = build_context(store, TODAY)
    ipca = next(
        c
        for c in context.source_checks
        if {c.a, c.b} == {"ipca_mensal", "ipca_mensal_ibge"}
    )
    assert ipca.agrees and ipca.compared == 2

    _seed(store, "ipca_mensal_ibge", [("2026-08", -0.10)], collected="2026-09-21")
    bad = next(
        c
        for c in build_context(store, TODAY).source_checks
        if {c.a, c.b} == {"ipca_mensal", "ipca_mensal_ibge"}
    )
    assert not bad.agrees and bad.max_difference == pytest.approx(0.22)


def test_the_monthly_bacen_series_is_checked_against_the_quarter_it_closes(tmp_path):
    store = MacroStore(tmp_path)
    _seed(store, "desocupacao_mensal", [("2026-06", 5.4), ("2026-07", 5.3)])
    _seed(store, "desocupacao_ibge", [("2026-T2", 5.4)])

    check = next(
        c
        for c in build_context(store, TODAY).source_checks
        if {c.a, c.b} == {"desocupacao_mensal", "desocupacao_ibge"}
    )

    assert check.compared == 1 and check.agrees


# --- the note ------------------------------------------------------------------


def _frontmatter(text):
    out = {}
    for line in text.split("---")[1].strip().splitlines():
        key, _, value = line.partition(": ")
        try:
            out[key] = json.loads(value)
        except json.JSONDecodeError:
            out[key] = value
    return out


def _context(tmp_path):
    store = MacroStore(tmp_path)
    _seed(store, "selic_meta", [("2025-09-19", 15.0), ("2026-09-20", 13.75)])
    store.ingest("selic_mes", (("2026-09", 0.67, True),), collected_at="2026-09-20")
    _seed(store, "ipca_mensal", [("2026-06", 0.1)])
    return build_context(store, TODAY)


def test_the_note_states_its_limits_and_that_it_is_not_a_recommendation(tmp_path):
    text = render_macro_report(_context(tmp_path))

    assert "É CONTEXTO" in text and "Não decide aporte nem peso-alvo" in text
    assert "a partir da primeira coleta (2026-09-20)" in text
    assert "NÃO serve para reconstruir" in text
    assert "Mapa de LEITURA, não causal" in text


def test_the_note_marks_partial_stale_and_missing_indicators(tmp_path):
    text = render_macro_report(_context(tmp_path))

    assert "parcial (mês em curso)" in text
    assert "**defasado**" in text and "**sem dados**" in text
    assert "-1,25 p.p." in text


def test_the_note_frontmatter_feeds_the_dashboard(tmp_path):
    fm = _frontmatter(render_macro_report(_context(tmp_path)))

    assert dash.MACRO_INDICATORS_KEY in fm and dash.MACRO_PROBLEMS_KEY in fm
    assert fm[dash.MACRO_COLLECTED_KEY] == "2026-09-20"
    by_id = {i["id"]: i for i in fm[dash.MACRO_INDICATORS_KEY]}
    assert by_id["selic_meta"]["variacao_12m"] == -1.25
    assert (
        by_id["selic_mes"]["provisorio"] is True
        and by_id["ipca_mensal"]["defasado"] is True
    )
    assert {p["id"] for p in fm[dash.MACRO_PROBLEMS_KEY]} >= {
        "ipca_mensal",
        "cdi_diario",
    }


def test_the_note_is_written_to_the_research_folder(tmp_path):
    path = write_macro_report(tmp_path / "vault", _context(tmp_path))

    assert path == tmp_path / "vault" / "07_Research" / "Macro" / "Contexto_Macro.md"


# --- CLI -----------------------------------------------------------------------


def _patch_harvesters(monkeypatch, bacen, ibge):
    monkeypatch.setattr("iip.sources.bacen_harvester.BacenHTTPHarvester", lambda: bacen)
    monkeypatch.setattr("iip.sources.ibge_harvester.IbgeHTTPHarvester", lambda: ibge)


def test_collect_macro_command_collects_and_summarises(monkeypatch, tmp_path):
    bacen = _FakeBacen(
        {432: _sgs(("2026-09-19", 13.75)), 433: _sgs(("2026-08-01", -0.32))}
    )
    _patch_harvesters(monkeypatch, bacen, _FakeIbge())

    out = CliRunner().invoke(
        cli,
        [
            "collect-macro",
            "--vault",
            str(tmp_path),
            "--indicator",
            "selic_meta",
            "--indicator",
            "ipca_mensal",
        ],
    )

    assert out.exit_code == 0, out.output
    assert "2 ok, 0 erro" in out.output
    assert MacroStore(tmp_path).latest("selic_meta")[0].value == 13.75


def test_collect_macro_command_exits_with_an_error_when_a_source_fails(
    monkeypatch, tmp_path
):
    _patch_harvesters(monkeypatch, _FakeBacen(error=OSError("sem rede")), _FakeIbge())

    out = CliRunner().invoke(
        cli, ["collect-macro", "--vault", str(tmp_path), "--indicator", "selic_meta"]
    )

    assert out.exit_code == 1 and "sem rede" in out.output


def test_collect_macro_command_rejects_an_id_outside_the_catalog(tmp_path):
    out = CliRunner().invoke(
        cli, ["collect-macro", "--vault", str(tmp_path), "--indicator", "pib"]
    )

    assert out.exit_code != 0 and "fora do catálogo" in out.output


def test_macro_context_command_says_to_collect_first_when_there_is_no_data(tmp_path):
    out = CliRunner().invoke(cli, ["macro-context", "--vault", str(tmp_path)])

    assert out.exit_code == 1 and "iip collect-macro" in out.output


def test_macro_context_command_prints_and_writes_the_note(monkeypatch, tmp_path):
    store = MacroStore(tmp_path)
    _seed(store, "selic_meta", [("2026-09-19", 13.75)])

    out = CliRunner().invoke(
        cli, ["macro-context", "--vault", str(tmp_path), "--report"]
    )

    assert out.exit_code == 0, out.output
    assert "Contexto, não recomendação" in out.output
    assert (tmp_path / "07_Research" / "Macro" / "Contexto_Macro.md").exists()
