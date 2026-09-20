import ast
import json
from datetime import date
from pathlib import Path

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.macro.collector import collect_indicator
from iip.macro.contract import indicator
from iip.macro.scenarios import (
    DEFAULT_SCENARIOS,
    MAX_ABS_SHOCK_PP,
    SCENARIOS_RELATIVE_PATH,
    Scenario,
    ScenarioSet,
    load_scenarios,
    save_scenarios,
    validate,
)
from iip.macro.sensitivity import (
    MAX_INPUT_AGE_DAYS,
    SENSITIVITY_MODEL_VERSION,
    model_parameters,
    run_sensitivity,
)
from iip.macro.store import MacroStore
from iip.obsidian.sensitivity_report import render_sensitivity_report
from iip.portfolio.batch_value import ValuationOutcome, ValuationRunResult
from iip.portfolio.valuation_inputs import (
    BaseRate,
    PositionInputs,
    ValuationInputs,
    build_valuation_inputs,
    load_valuation_inputs,
    save_valuation_inputs,
)
from iip.portfolio_data import valuation_methods as vm
from iip.sources.tesouro_direto import (
    NtnbRate,
    TesouroRateRow,
    long_ntnb_series,
)

TODAY = date(2026, 9, 20)
BASE = 0.10  # uma taxa redonda torna as contas conferíveis à mão


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --- the scenarios --------------------------------------------------------------


def test_the_real_yield_shift_follows_the_stated_transmission_rule():
    assert Scenario("a", "a", nominal_rate_shock_pp=1.0).real_yield_shift_pp == 1.0
    assert Scenario("a", "a", inflation_shock_pp=1.0).real_yield_shift_pp == -1.0
    both = Scenario("a", "a", nominal_rate_shock_pp=1.0, inflation_shock_pp=1.0)
    assert both.real_yield_shift_pp == 0.0
    direct = Scenario(
        "a",
        "a",
        nominal_rate_shock_pp=2.0,
        inflation_shock_pp=0.5,
        real_yield_shock_pp=0.25,
    )
    assert direct.real_yield_shift_pp == pytest.approx(1.75)


def test_the_default_set_is_valid_and_has_a_pass_through_scenario_that_does_not_move_the_rate():
    validate(DEFAULT_SCENARIOS)
    assert any(s.real_yield_shift_pp == 0 for s in DEFAULT_SCENARIOS.scenarios)


def test_the_hash_is_stable_and_changes_with_any_shock_or_the_version():
    a = ScenarioSet("v1", "o", (Scenario("x", "x", nominal_rate_shock_pp=1.0),))
    same = ScenarioSet(
        "v1", "outra origem", (Scenario("x", "outro nome", nominal_rate_shock_pp=1.0),)
    )
    shock = ScenarioSet("v1", "o", (Scenario("x", "x", nominal_rate_shock_pp=1.5),))
    version = ScenarioSet("v2", "o", (Scenario("x", "x", nominal_rate_shock_pp=1.0),))

    assert a.content_hash == same.content_hash  # nome e origem não são parâmetros
    assert len({a.content_hash, shock.content_hash, version.content_hash}) == 3


@pytest.mark.parametrize(
    ("scenario_set", "message"),
    [
        (ScenarioSet("", "o", (Scenario("x", "x"),)), "versão"),
        (ScenarioSet("v", "o", ()), "vazio"),
        (ScenarioSet("v", "o", (Scenario("base", "x"),)), "reservado"),
        (ScenarioSet("v", "o", (Scenario("a", "x"), Scenario("a", "y"))), "repetido"),
        (
            ScenarioSet(
                "v",
                "o",
                (Scenario("a", "x", nominal_rate_shock_pp=MAX_ABS_SHOCK_PP + 1),),
            ),
            "pontos percentuais",
        ),
    ],
)
def test_an_invalid_scenario_set_is_refused_with_the_reason(scenario_set, message):
    with pytest.raises(ValueError, match=message):
        validate(scenario_set)


def test_scenarios_round_trip_through_the_vault_file(tmp_path):
    save_scenarios(tmp_path, DEFAULT_SCENARIOS)

    loaded = load_scenarios(tmp_path)

    assert loaded == DEFAULT_SCENARIOS
    assert loaded.content_hash == DEFAULT_SCENARIOS.content_hash
    assert (tmp_path / SCENARIOS_RELATIVE_PATH).exists()


def test_the_shocks_live_in_the_file_not_in_the_code(tmp_path):
    save_scenarios(tmp_path, DEFAULT_SCENARIOS)
    path = tmp_path / SCENARIOS_RELATIVE_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["scenarios"][0]["nominal_rate_shock_pp"] = 3.0
    payload["version"] = "editado"
    path.write_text(json.dumps(payload), encoding="utf-8")

    edited = load_scenarios(tmp_path)

    assert edited.scenarios[0].nominal_rate_shock_pp == 3.0
    assert (
        edited.version == "editado"
        and edited.content_hash != DEFAULT_SCENARIOS.content_hash
    )


def test_a_missing_file_is_none_but_a_broken_one_is_an_error_never_the_default(
    tmp_path,
):
    assert load_scenarios(tmp_path) is None
    path = tmp_path / SCENARIOS_RELATIVE_PATH
    path.parent.mkdir(parents=True)
    path.write_text("{nao e json", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON"):
        load_scenarios(tmp_path)
    path.write_text(
        json.dumps({"rule": "outra", "version": "v", "scenarios": []}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="regra"):
        load_scenarios(tmp_path)


# --- the sensitivity ------------------------------------------------------------


def _equity(dps=1.0, price=10.0):
    return PositionInputs(
        "EQ3",
        "equity",
        "Materiais Básicos",
        "Madeiras e Papel",
        price,
        {"dividend_per_share": dps, "lpa": 1.5, "vpa": 4.6},
    )


def _fii(dps=9.0, nav=100.0, price=95.0):
    return PositionInputs(
        "FII11",
        "fii",
        "Tijolo",
        "Logístico",
        price,
        {"dividend_per_share": dps, "nav_per_share": nav},
    )


def _inputs(*positions, run="2026-09-20", rate=BASE, reference="2026-09-18"):
    base = (
        BaseRate(rate, reference, "2060-08-15", "Tesouro IPCA+ com Juros Semestrais")
        if rate
        else None
    )
    return ValuationInputs(run, base, tuple(positions))


def _set(*scenarios):
    return ScenarioSet("t1", "teste", tuple(scenarios))


UP = Scenario("up", "juros +1", nominal_rate_shock_pp=1.0)
DOWN = Scenario("down", "juros -1", nominal_rate_shock_pp=-1.0)
INFLATION = Scenario("infl", "inflação +1", inflation_shock_pp=1.0)
PASS_THROUGH = Scenario(
    "pass", "repasse", nominal_rate_shock_pp=1.0, inflation_shock_pp=1.0
)


def _asset(result, ticker):
    return next(a for a in result.assets if a.ticker == ticker)


def _method(values, name):
    return next(v for v in values if v.method == name)


def test_bazin_moves_exactly_with_the_real_yield_by_the_ceiling_formula(tmp_path):
    result = run_sensitivity(
        _inputs(_equity(dps=1.0)), _set(UP, DOWN), store=None, today=TODAY
    )

    asset = _asset(result, "EQ3")
    assert _method(asset.base, "Bazin").fair_value == pytest.approx(
        1.0 / 0.10, abs=0.01
    )
    up = _method(asset.scenarios[0].methods, "Bazin")
    down = _method(asset.scenarios[1].methods, "Bazin")
    assert up.fair_value == pytest.approx(1.0 / 0.11, abs=0.01)
    assert down.fair_value == pytest.approx(1.0 / 0.09, abs=0.01)
    assert up.margin == pytest.approx(up.fair_value / 10.0 - 1, abs=1e-6)


def test_yield_capitalises_over_the_real_yield_plus_the_fii_premium(tmp_path):
    result = run_sensitivity(_inputs(_fii(dps=9.0)), _set(UP), store=None, today=TODAY)

    asset = _asset(result, "FII11")
    premium = vm.FII_YIELD_RISK_PREMIUM
    assert _method(asset.base, "Yield").fair_value == pytest.approx(
        9.0 / (0.10 + premium), abs=0.01
    )
    assert _method(asset.scenarios[0].methods, "Yield").fair_value == pytest.approx(
        9.0 / (0.11 + premium), abs=0.01
    )


def test_methods_that_do_not_read_the_rate_are_insensitive_by_comparison(tmp_path):
    result = run_sensitivity(
        _inputs(_equity(), _fii()), _set(UP, DOWN), store=None, today=TODAY
    )

    equity, fii = _asset(result, "EQ3"), _asset(result, "FII11")
    assert (
        equity.sensitive_methods == ("Bazin",)
        and "Graham" in equity.insensitive_methods
    )
    assert fii.sensitive_methods == ("Yield",) and "NAV" in fii.insensitive_methods
    graham = [_method(o.methods, "Graham").fair_value for o in equity.scenarios]
    assert (
        len(set(graham))
        == 1
        == len({_method(equity.base, "Graham").fair_value, *graham})
    )


def test_inflation_up_with_the_same_nominal_rate_lowers_the_real_yield_and_raises_the_ceiling():
    result = run_sensitivity(
        _inputs(_equity()), _set(INFLATION), store=None, today=TODAY
    )

    asset = _asset(result, "EQ3")
    assert asset.scenarios[0].real_yield == pytest.approx(0.09)
    assert (
        _method(asset.scenarios[0].methods, "Bazin").fair_value
        > _method(asset.base, "Bazin").fair_value
    )


def test_a_pass_through_scenario_leaves_the_models_unchanged_and_the_report_says_so():
    result = run_sensitivity(
        _inputs(_equity()), _set(PASS_THROUGH), store=None, today=TODAY
    )

    asset = _asset(result, "EQ3")
    assert asset.sensitive_methods == () and "Bazin" in asset.insensitive_methods


def test_a_real_yield_that_reaches_zero_removes_bazin_and_warns():
    big = Scenario("crash", "queda de 10 p.p.", nominal_rate_shock_pp=-10.0)

    result = run_sensitivity(_inputs(_equity()), _set(big), store=None, today=TODAY)

    outcome = _asset(result, "EQ3").scenarios[0]
    assert _method(outcome.methods, "Bazin").fair_value is None
    assert any("<= 0" in w for w in result.warnings)
    assert "Bazin" in _asset(result, "EQ3").sensitive_methods  # havia valor na base


def test_without_a_base_rate_nothing_is_computed_from_it_and_it_says_why():
    result = run_sensitivity(
        _inputs(_equity(), rate=None), _set(UP), store=None, today=TODAY
    )

    assert result.base_rate is None
    assert _method(_asset(result, "EQ3").base, "Bazin").fair_value is None
    assert any("sem taxa-base" in w for w in result.warnings)


def test_the_result_carries_everything_needed_to_trace_it(tmp_path):
    store = MacroStore(tmp_path)
    store.ingest(
        "ntnb_longa_real",
        (("2026-09-18", 10.0, False),),
        collected_at="2026-09-20",
        notes={"2026-09-18": "NTN-B 2060"},
    )
    scenarios = _set(UP, DOWN)

    result = run_sensitivity(
        _inputs(_equity(), _fii()), scenarios, store=store, today=TODAY
    )

    assert result.model_version == SENSITIVITY_MODEL_VERSION
    assert result.model_parameters == model_parameters()
    assert (
        result.model_parameters["FII_YIELD_RISK_PREMIUM"] == vm.FII_YIELD_RISK_PREMIUM
    )
    assert (result.scenario_version, result.scenario_hash) == (
        "t1",
        scenarios.content_hash,
    )
    assert result.base_rate.reference_date == "2026-09-18"
    assert result.stored_observation.collected_at == "2026-09-20"
    assert result.stored_observation.note == "NTN-B 2060"
    assert result.inputs_run_date == "2026-09-20" and result.today == "2026-09-20"
    assert {n for n, _, _ in result.scenarios} == set() or len(result.scenarios) == 2


def test_the_same_inputs_and_scenarios_reproduce_the_same_numbers():
    args = (_inputs(_equity(), _fii()), _set(UP, DOWN, INFLATION))

    first = run_sensitivity(*args, store=None, today=TODAY)
    second = run_sensitivity(*args, store=None, today=TODAY)

    assert first == second


def test_old_inputs_and_a_rate_from_another_day_are_flagged():
    stale = _inputs(_equity(), run="2026-09-01", reference="2026-08-20")

    result = run_sensitivity(stale, _set(UP), store=None, today=TODAY)

    text = " ".join(result.warnings)
    assert (
        f"{(TODAY - date(2026, 9, 1)).days} dias" in text
        and (TODAY - date(2026, 9, 1)).days > MAX_INPUT_AGE_DAYS
    )
    assert "datas diferentes" in text


def test_a_newer_rate_in_the_store_is_flagged_but_not_silently_used(tmp_path):
    store = MacroStore(tmp_path)
    store.ingest(
        "ntnb_longa_real",
        (("2026-09-18", 10.0, False), ("2026-09-19", 10.4, False)),
        collected_at="2026-09-20",
    )

    result = run_sensitivity(_inputs(_equity()), _set(UP), store=store, today=TODAY)

    assert result.newer_observation.reference == "2026-09-19"
    assert any("taxa mais nova" in w for w in result.warnings)
    assert result.base_rate.real_yield == BASE  # a base continua a da rodada


def test_a_rate_that_differs_from_the_stored_one_for_the_same_day_is_flagged(tmp_path):
    store = MacroStore(tmp_path)
    store.ingest(
        "ntnb_longa_real", (("2026-09-18", 9.0, False),), collected_at="2026-09-20"
    )

    result = run_sensitivity(_inputs(_equity()), _set(UP), store=store, today=TODAY)

    assert any("difere da guardada" in w for w in result.warnings)


def test_a_position_that_depends_on_another_valuation_is_marked_not_recomputed():
    fmp = PositionInputs(
        "FMP",
        "fmp_fgts",
        "Utilities",
        "Electric",
        1.9,
        {
            "nav_per_share": 1.9,
            "look_through_margin": 0.02,
            "look_through_coverage": 0.99,
        },
    )

    result = run_sensitivity(_inputs(fmp), _set(UP), store=None, today=TODAY)

    assert "não é recalculada" in _asset(result, "FMP").note


# --- the note ---------------------------------------------------------------------


def _report(tmp_path=None):
    scenarios = _set(UP, DOWN, PASS_THROUGH)
    result = run_sensitivity(
        _inputs(_equity(), _fii()), scenarios, store=None, today=TODAY
    )
    return render_sensitivity_report(result, scenarios), result


def test_the_note_separates_the_observed_rate_from_the_scenario_premises():
    text, _ = _report()

    assert "## Taxa observada (a base)" in text and "IPCA + 10.00%" in text
    assert "taxa REAL, sobre o IPCA" in text
    assert "## Cenários (premissas, não observações)" in text
    assert "IPCA + 11.00%" in text and "IPCA + 9.00%" in text


def test_the_note_explains_the_impact_by_asset_and_model():
    text, _ = _report()

    rows = [
        ln
        for ln in text.splitlines()
        if ln.startswith("| EQ3") or ln.startswith("| FII11")
    ]
    assert any("Bazin" in r for r in rows) and any("Yield" in r for r in rows)
    assert "-9%" in text and "+11%" in text  # Bazin: 1/0.11 vs 1/0.10 e 1/0.09
    assert (
        "## Métodos que não reagem à taxa" in text
        and "Graham" in text
        and "NAV" in text
    )


def test_the_note_states_it_is_not_a_recommendation_and_touches_no_contribution_or_weight():
    text, _ = _report()

    assert "não é previsão nem recomendação" in text.replace("**", "").replace(
        "É sensibilidade das premissas, ", ""
    ) or "Não altera aporte, peso-alvo nem rebalanceamento" in text.replace("**", "")
    assert "Nenhum aporte, peso-alvo ou rebalanceamento é sugerido" in text
    assert "Real e nominal não se misturam" in text


def test_the_note_lists_the_traceability_fields():
    text, result = _report()

    assert result.model_version in text and result.scenario_hash in text
    assert "FII_YIELD_RISK_PREMIUM" in text and "insumos_valuation.json" in text
    assert "ntnb_longa_real" in text and "NÃO entram nas contas" in text


# --- the valuation inputs ---------------------------------------------------------


def _run_result():
    outcome = ValuationOutcome(
        "EQ3",
        "ok",
        "d",
        price=10.0,
        attempts=(),
        asset_class="equity",
        segment="s / i",
        sector="Materiais Básicos",
        industry="Madeiras e Papel",
        inputs={
            "dividend_per_share": 1.0,
            "lpa": 1.5,
            "nota": "texto",
            "flag": True,
            "vazio": None,
        },
    )
    no_inputs = ValuationOutcome("SKIP3", "pulado", "x")
    rate = NtnbRate(date(2026, 9, 18), date(2060, 8, 15), 0.0731)
    return ValuationRunResult((outcome, no_inputs), rate, "nota")


def test_only_numeric_inputs_are_kept_and_positions_without_inputs_are_left_out():
    snapshot = build_valuation_inputs(_run_result(), run_date=TODAY)

    assert [p.ticker for p in snapshot.positions] == ["EQ3"]
    assert snapshot.positions[0].inputs == {
        "dividend_per_share": 1.0,
        "lpa": 1.5,
        "vazio": None,
    }
    assert (
        snapshot.base_rate.real_yield == 0.0731
        and snapshot.base_rate.reference_date == "2026-09-18"
    )
    assert snapshot.run_date == "2026-09-20"


def test_the_inputs_round_trip_and_a_bad_file_reads_as_none(tmp_path):
    snapshot = build_valuation_inputs(_run_result(), run_date=TODAY)

    save_valuation_inputs(tmp_path, snapshot)
    assert load_valuation_inputs(tmp_path) == snapshot

    path = tmp_path / "07_Research" / "Macro" / "insumos_valuation.json"
    path.write_text("{nao e json", encoding="utf-8")
    assert load_valuation_inputs(tmp_path) is None
    assert load_valuation_inputs(tmp_path / "vazio") is None


# --- the NTN-B in the macro store -----------------------------------------------------


def _row(day, maturity, taxa, titulo="Tesouro IPCA+ com Juros Semestrais"):
    return TesouroRateRow(titulo, maturity, day, taxa - 0.1, taxa)


def test_the_series_takes_the_longest_maturity_of_each_day_and_ignores_other_bonds():
    rows = (
        _row(date(2026, 9, 18), date(2035, 5, 15), 7.60),
        _row(date(2026, 9, 18), date(2060, 8, 15), 7.31),
        _row(date(2026, 9, 17), date(2060, 8, 15), 7.29),
        _row(date(2026, 9, 18), date(2029, 1, 1), 14.0, titulo="Tesouro Prefixado"),
        _row(date(2026, 9, 16), date(2060, 8, 15), 99.0),  # fora da faixa plausível
    )

    series = long_ntnb_series(rows)

    assert [(r.reference_date, r.real_yield) for r in series] == [
        (date(2026, 9, 17), 0.0729),
        (date(2026, 9, 18), 0.0731),
    ]
    assert series[-1].maturity == date(2060, 8, 15)


def test_the_collector_stores_the_ntnb_in_percent_with_the_bond_as_provenance(tmp_path):
    class Tesouro:
        def fetch_long_ntnb_series(self):
            return (NtnbRate(date(2026, 9, 18), date(2060, 8, 15), 0.0731),)

    store = MacroStore(tmp_path)

    outcome = collect_indicator(
        indicator("ntnb_longa_real"),
        store,
        today=TODAY,
        bacen=None,
        ibge=None,
        tesouro=Tesouro(),
    )

    assert outcome.status == "ok"
    obs = store.latest("ntnb_longa_real")[0]
    assert (obs.reference, obs.value, obs.collected_at) == (
        "2026-09-18",
        7.31,
        "2026-09-20",
    )
    assert "vencimento 15/08/2060" in obs.note


# --- the commands -------------------------------------------------------------------


def _vault(tmp_path):
    save_scenarios(tmp_path, _set(UP, DOWN))
    save_valuation_inputs(tmp_path, _inputs(_equity(), _fii()))
    return tmp_path


def test_scenarios_command_needs_init_and_never_overwrites_an_edited_file(tmp_path):
    runner = CliRunner()
    missing = runner.invoke(cli, ["macro-scenarios", "--vault", str(tmp_path)])
    assert missing.exit_code == 1 and "--init" in missing.output

    created = runner.invoke(
        cli, ["macro-scenarios", "--vault", str(tmp_path), "--init"]
    )
    assert created.exit_code == 0 and DEFAULT_SCENARIOS.content_hash in created.output

    path = tmp_path / SCENARIOS_RELATIVE_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = "meu-conjunto"
    path.write_text(json.dumps(payload), encoding="utf-8")
    again = runner.invoke(cli, ["macro-scenarios", "--vault", str(tmp_path), "--init"])
    assert again.exit_code == 0 and "meu-conjunto" in again.output
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == "meu-conjunto"


def test_scenarios_command_reports_a_broken_file(tmp_path):
    path = tmp_path / SCENARIOS_RELATIVE_PATH
    path.parent.mkdir(parents=True)
    path.write_text("{nao e json", encoding="utf-8")

    out = CliRunner().invoke(cli, ["macro-scenarios", "--vault", str(tmp_path)])

    assert out.exit_code == 1 and "Cenários inválidos" in out.output


def test_sensitivity_command_prints_writes_the_note_and_states_its_limits(tmp_path):
    vault = _vault(tmp_path)

    out = CliRunner().invoke(
        cli, ["macro-sensitivity", "--vault", str(vault), "--report"]
    )

    assert out.exit_code == 0, out.output
    assert (
        "Taxa observada" in out.output
        and "Bazin" in out.output
        and "Yield" in out.output
    )
    assert "não altera aporte nem peso" in out.output
    assert (vault / "07_Research" / "Macro" / "Sensibilidade.md").exists()


def test_sensitivity_command_asks_for_the_missing_pieces(tmp_path):
    runner = CliRunner()
    no_scenarios = runner.invoke(cli, ["macro-sensitivity", "--vault", str(tmp_path)])
    assert (
        no_scenarios.exit_code == 1 and "macro-scenarios --init" in no_scenarios.output
    )

    save_scenarios(tmp_path, _set(UP))
    no_inputs = runner.invoke(cli, ["macro-sensitivity", "--vault", str(tmp_path)])
    assert no_inputs.exit_code == 1 and "value-portfolio --report" in no_inputs.output


# --- limits: nothing here touches contributions, weights or decisions ---------------------

_FORBIDDEN = (
    "iip.decision",
    "iip.integration",
    "iip.strategy",
    "iip.orchestration",
    "iip.portfolio_decision",
    "iip.portfolio.batch_decide",
    "iip.portfolio.exposure",
    "iip.portfolio.decision_alerts",
    "iip.knowledge",
)


def _imports(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_the_macro_layer_does_not_import_decision_contribution_or_weight_code():
    root = Path("src/iip")
    files = [
        *(root / "macro").glob("*.py"),
        root / "obsidian" / "sensitivity_report.py",
        root / "obsidian" / "macro_report.py",
    ]

    offenders = {
        (f.name, name)
        for f in files
        for name in _imports(f)
        if any(name == bad or name.startswith(bad + ".") for bad in _FORBIDDEN)
    }

    assert offenders == set()


def test_the_decision_and_income_layers_do_not_import_the_macro_layer():
    root = Path("src/iip")
    files = [
        root / "portfolio" / "batch_decide.py",
        root / "portfolio" / "decision_alerts.py",
        root / "portfolio" / "exposure.py",
        root / "portfolio" / "income.py",
    ]

    assert not any(n.startswith("iip.macro") for f in files for n in _imports(f))


def test_the_only_macro_input_of_the_valuation_models_is_still_the_ntnb_rate():
    # o Bazin e o Yield leem `ntnb_real_yield`; o resto do macro não entra nas contas
    source = Path("src/iip/portfolio_data/valuation_methods.py").read_text(
        encoding="utf-8"
    )

    assert source.count('inputs.get("ntnb_real_yield")') == 2
    assert "selic" not in source.lower() and "ipca_" not in source.lower()
