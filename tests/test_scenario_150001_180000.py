from iip.scenario_engine.decision_stability import assess
from iip.scenario_engine.models import DecisionScenario, Scenario, ScenarioScore
from iip.scenario_engine.pipeline import ScenarioPipelineInput, run
from iip.scenario_engine.portfolio_scenarios import PortfolioScenario, summarize
from iip.scenario_engine.release_scenarios import certify
from iip.scenario_engine.scenario_compare import compare
from iip.scenario_engine.scenario_evaluator import evaluate, evaluate_many
from iip.scenario_engine.stress_matrix import StressPoint, rank
from iip.scenario_engine.thresholds import bounded, meets, pass_rate
from iip.scenario_engine.validation_gate import evaluate as gate_evaluate


def test_scenario_evaluator():
    scenario = Scenario("base", (("growth", 0.05),))
    result = evaluate(scenario, lambda s: 7.5)
    assert result.score == 7.5
    assert result.passed


def test_scenario_evaluator_many():
    scenarios = (
        Scenario("base", ()),
        Scenario("stress", ()),
    )
    result = evaluate_many(scenarios, lambda s: 4.0)
    assert len(result) == 2
    assert not result[0].passed


def test_stress_rank():
    result = rank(
        (
            StressPoint("B", "stress", 7, 3),
            StressPoint("A", "stress", 8, 4),
        )
    )
    assert result[0].ticker == "A"


def test_decision_stability():
    stable = assess(DecisionScenario("HGRU11", "APORTAR", "APORTAR", 8, 7))
    changed = assess(DecisionScenario("CPFE3", "APORTAR", "MANTER", 8, 7))
    assert stable.stable
    assert not changed.stable
    assert changed.action_changed


def test_threshold_helpers():
    assert bounded(2) == 1
    assert bounded(-1) == 0
    assert pass_rate(3, 4) == 0.75
    assert pass_rate(0, 0) == 0
    assert meets(7, 6)


def test_portfolio_scenario_summary():
    scenario = PortfolioScenario(
        "base",
        (
            ScenarioScore("A", 8, True),
            ScenarioScore("B", 6, True),
        ),
    )
    result = summarize(scenario)
    assert result.average_score == 7
    assert result.pass_rate == 1


def test_scenario_compare():
    result = compare("base", 8, "stress", 6)
    assert result.score_delta == -2


def test_validation_gate():
    good = gate_evaluate(stable=True, evidence_complete=True, risk_acceptable=True)
    bad = gate_evaluate(stable=True, evidence_complete=False, risk_acceptable=True)
    assert good.passed
    assert not bad.passed


def test_pipeline():
    data = ScenarioPipelineInput(
        "2026-08-29",
        (DecisionScenario("HGRU11", "APORTAR", "APORTAR", 8, 7),),
        True,
        True,
    )
    result = run(data)
    assert result.report.stable_count == 1
    assert result.gate.passed


def test_release_scenario_certification():
    gates = (
        gate_evaluate(stable=True, evidence_complete=True, risk_acceptable=True),
        gate_evaluate(stable=True, evidence_complete=True, risk_acceptable=True),
    )
    cert = certify(gates)
    assert cert.certified
    assert cert.actual_pass_rate == 1


def test_release_scenario_failure():
    gate = gate_evaluate(stable=False, evidence_complete=True, risk_acceptable=True)
    cert = certify((gate,))
    assert not cert.certified
