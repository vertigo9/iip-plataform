from dataclasses import dataclass

from iip.system.core_adapter import CoreCommandAdapter
from iip.system.e2e import run_checks
from iip.system.export_adapter import SystemExportAdapter
from iip.system.health_adapter import ComponentHealth, SystemHealth
from iip.system.models import SystemStage
from iip.system.pipeline import FullSystemPipeline, StageHandler
from iip.system.portfolio_system import run_portfolio
from iip.system.regression import RegressionBaseline, RegressionCurrent, compare
from iip.system.release_simulation import SimulationGate


def handlers():
    return tuple(
        StageHandler(
            stage, lambda ticker, ctx, trace, _stage=stage: f"{_stage.value}:{ticker}"
        )
        for stage in FullSystemPipeline.ORDER
    )


def test_full_system_pipeline_runs_all_stages():
    result = FullSystemPipeline(handlers()).run("r1", "hgru11")
    assert result.success
    assert len(result.trace.artifacts) == 8
    assert result.trace.artifacts[-1].stage == SystemStage.EXPORT


def test_pipeline_stops_without_stage():
    pipeline = FullSystemPipeline(handlers()[:-1])
    result = pipeline.run("r2", "XPML11")
    assert not result.success
    assert "stage_not_registered:export" in result.error


def test_core_command_adapter():
    adapter = CoreCommandAdapter({"analyze": lambda ticker: ticker.upper()})
    assert adapter.execute("analyze", "cpfe3").value == "CPFE3"
    assert not adapter.execute("missing").success


def test_system_health():
    health = SystemHealth(
        (ComponentHealth("atlas", True, "ok"), ComponentHealth("knowledge", True, "ok"))
    )
    assert health.healthy
    assert health.degraded() == ()


def test_export_adapter():
    @dataclass(frozen=True)
    class Value:
        ticker: str

    assert SystemExportAdapter().export(Value("HGRU11"))["ticker"] == "HGRU11"


def test_e2e_checks():
    report = run_checks(
        (
            ("atlas", lambda: True),
            ("knowledge", lambda: 1 == 1),
        )
    )
    assert report.passed


def test_regression_compare():
    baseline = RegressionBaseline(424, 87.0, ("atlas", "knowledge", "decision"))
    current = RegressionCurrent(430, 88.0, ("atlas", "knowledge", "decision"))
    assert compare(baseline, current)[0]
    bad = RegressionCurrent(423, 86.0, ("atlas", "knowledge"))
    ok, issues = compare(baseline, bad)
    assert not ok
    assert "test_count_decreased" in issues


def test_portfolio_system():
    def runner(ticker):
        return FullSystemPipeline(handlers()).run(ticker, ticker)

    result = run_portfolio(("HGRU11", "XPML11", "CPFE3"), runner)
    assert result.success_count == 3
    assert result.failure_count == 0


def test_release_simulation_requires_live_execution_off():
    assert SimulationGate(True, True, True, False).pass_gate
    assert not SimulationGate(True, True, True, True).pass_gate
