from iip.enterprise.change_control import ChangeRequest, ChangeType, can_promote
from iip.enterprise.data_contracts import AssetSnapshot, DecisionSnapshot
from iip.enterprise.export_contract import serialize
from iip.enterprise.model_registry import ModelRegistry, ModelVersion
from iip.enterprise.monitoring import PipelineMonitor
from iip.enterprise.orchestrator import EnterpriseOrchestrator, Stage
from iip.enterprise.portfolio_batch import partition
from iip.enterprise.readiness import EnterpriseReadiness
from iip.enterprise.reporting import PortfolioReport, ReportRow


def test_enterprise_orchestrator_runs_in_order():
    calls = []

    def handler(name):
        def _run(ticker, *args, **kwargs):
            calls.append(name)
            return name

        return _run

    handlers = {stage: handler(stage.value) for stage in EnterpriseOrchestrator.ORDER}
    result = EnterpriseOrchestrator(handlers).run("hgru11")
    assert result.success
    assert calls == [stage.value for stage in EnterpriseOrchestrator.ORDER]


def test_orchestrator_stops_on_failure():
    calls = []

    def ok(ticker):
        calls.append("ok")

    def fail(ticker):
        calls.append("fail")
        raise RuntimeError("boom")

    result = EnterpriseOrchestrator(
        {
            Stage.DISCOVERY: ok,
            Stage.ATLAS: fail,
        }
    ).run("XPML11")
    assert not result.success
    assert [item.stage for item in result.results] == [Stage.DISCOVERY, Stage.ATLAS]
    assert calls == ["ok", "fail"]


def test_portfolio_partition():
    result = partition(["hgru11", "xpml11", "cpfe3"], size=2)
    assert result[0].tickers == ("HGRU11", "XPML11")
    assert result[1].tickers == ("CPFE3",)


def test_reporting_top_is_deterministic():
    report = PortfolioReport(
        "2026-08-29",
        (
            ReportRow("B", "APORTAR", 8.0, 0.8, 2),
            ReportRow("A", "APORTAR", 8.0, 0.9, 3),
            ReportRow("C", "MANTER", 7.0, 0.8, 1),
        ),
    )
    assert tuple(row.ticker for row in report.top(2)) == ("A", "B")


def test_change_control_requires_approval_and_tests():
    assert can_promote(ChangeRequest("1", ChangeType.RULE, "rule", True, True))
    assert not can_promote(ChangeRequest("2", ChangeType.RULE, "rule", True, False))


def test_model_registry_promotion_is_explicit():
    registry = ModelRegistry()
    registry.register(ModelVersion("decision", "1", "aaa"))
    registry.register(ModelVersion("decision", "2", "bbb"))
    assert registry.promote("decision", "2")
    assert registry.get("decision", "2").production
    assert not registry.get("decision", "1").production


def test_data_contracts_are_stable():
    asset = AssetSnapshot(
        "HGRU11", "fund", "Renda Urbana", "Patria", "Baixo", "2026-08-29"
    )
    decision = DecisionSnapshot("HGRU11", "APORTAR", 8.5, 0.9, ("e1",), "decision-1.0")
    assert asset.ticker == decision.ticker
    assert decision.model_version == "decision-1.0"


def test_monitoring():
    monitor = PipelineMonitor()
    monitor.record("success")
    monitor.record("success")
    monitor.record("failed")
    monitor.record("degraded")
    assert monitor.runs == 4
    assert monitor.success_rate == 0.5


def test_export_contract():
    asset = AssetSnapshot("CPFE3", "equity", None, None, None, "2026-08-29")
    data = serialize(asset)
    assert data["ticker"] == "CPFE3"


def test_enterprise_readiness():
    gate = EnterpriseReadiness(True, 87.0, True, True, True, True, True)
    assert gate.ready
    assert not EnterpriseReadiness(True, 79.0, True, True, True, True, True).ready
