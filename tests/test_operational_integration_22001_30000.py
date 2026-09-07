from iip.operational_integration.cli_commands import CommandDispatcher
from iip.operational_integration.export_pipeline import ExportPipeline
from iip.operational_integration.health_runtime import HealthComponent, HealthSummary
from iip.operational_integration.portfolio_e2e import AssetE2EResult, run
from iip.operational_integration.portfolio_integration import PortfolioIntegrationFacade
from iip.operational_integration.provider_runtime_matrix import (
    ProviderRuntimeMatrix,
    ProviderRuntimeState,
)
from iip.operational_integration.regression_gate import RegressionGate
from iip.operational_integration.system_reconciliation import reconcile
from iip.operational_integration.validation_matrix import build_matrix


def test_portfolio_integration_facade():
    facade = PortfolioIntegrationFacade({"registry": lambda x: x.upper()})
    result = facade.execute("registry", "hgru11")
    assert result.success and result.value == "HGRU11"
    assert not facade.execute("missing").success


def test_validation_matrix():
    matrix = build_matrix(
        ("HGRU11", "CPFE3"),
        ("source", "decision"),
        lambda asset, criterion: (asset != "CPFE3" or criterion == "source", "ok"),
    )
    assert not matrix.passed
    assert len(matrix.failures()) == 1


def test_health_runtime():
    summary = HealthSummary(
        (
            HealthComponent("xp", True, 100),
            HealthComponent("patria", True, 200),
        )
    )
    assert summary.healthy
    assert summary.average_latency_ms == 150


def test_provider_runtime_matrix():
    matrix = ProviderRuntimeMatrix(
        (
            ProviderRuntimeState("sparta", True, True, ("CDII11",)),
            ProviderRuntimeState("btg", True, False, ("BTCI11",)),
            ProviderRuntimeState("kinea", False, True, ("KNCR11",)),
        )
    )
    assert tuple(state.provider for state in matrix.ready()) == ("sparta",)


def test_export_pipeline():
    pipeline = ExportPipeline({"json": lambda payload: {"payload": payload}})
    artifact = pipeline.export("JSON", "report", 42)
    assert artifact.format == "json"
    assert artifact.payload["payload"] == 42


def test_cli_dispatcher():
    dispatcher = CommandDispatcher({"analyze": lambda ticker: ticker.upper()})
    assert dispatcher.dispatch("analyze", "cpfe3").payload == "CPFE3"
    assert not dispatcher.dispatch("missing").success


def test_reconciliation():
    result = reconcile(("A", "B"), ("B", "C"))
    assert not result.consistent
    assert result.missing == ("A",)
    assert result.unexpected == ("C",)


def test_portfolio_e2e():
    result = run(
        ("hgru11", "cpfe3"),
        lambda ticker: AssetE2EResult(
            ticker,
            ("snapshot", "decision", "report"),
            True,
        ),
    )
    assert result.success
    assert result.assets[0].ticker == "HGRU11"


def test_regression_gate():
    assert RegressionGate(488, 490, 89, 89.5).pass_gate
    assert not RegressionGate(488, 487, 89, 90).pass_gate
