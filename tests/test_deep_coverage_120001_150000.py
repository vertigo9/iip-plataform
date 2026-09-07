from iip.coverage.cli_adapter import handle
from iip.coverage.core_adapter import CoreAdapter
from iip.coverage.export_adapter import export
from iip.coverage.health_deep import HealthCheck, HealthReport
from iip.coverage.portfolio_integration import IntegrationNode, plan
from iip.coverage.portfolio_matrix import MatrixPoint, rank
from iip.coverage.portfolio_validation import validate
from iip.coverage.provider_certification import ProviderCertification
from iip.coverage.provider_runtime import RuntimeProbe, ready
from iip.coverage.regression_report import CoverageReport


def test_core_adapter_paths():
    adapter = CoreAdapter(
        {"echo": lambda x: x, "fail": lambda: (_ for _ in ()).throw(ValueError("x"))}
    )
    assert adapter.run("echo", 5).value == 5
    assert not adapter.run("missing").ok
    assert not adapter.run("fail").ok


def test_integration_plan_deduplicates():
    result = plan(
        (
            IntegrationNode("portfolio"),
            IntegrationNode("atlas"),
            IntegrationNode("portfolio", False),
        )
    )
    assert result.ready
    assert tuple(x.name for x in result.nodes) == ("atlas", "portfolio")


def test_portfolio_matrix_rank():
    result = rank(
        (
            MatrixPoint("B", 8, 3, 0.2, "MANTER"),
            MatrixPoint("A", 9, 5, 0.5, "APORTAR"),
        )
    )
    assert result[0].ticker == "A"


def test_portfolio_validation():
    good = validate(
        identifiers_ok=True, weights_ok=True, evidence_ok=True, decisions_ok=True
    )
    bad = validate(
        identifiers_ok=True, weights_ok=False, evidence_ok=False, decisions_ok=True
    )
    assert good.passed
    assert bad.failures == ("weights", "evidence")


def test_export_adapter():
    assert export("json", {"b": 1, "a": 2}).payload == '{"a": 2, "b": 1}'
    assert export("text", 42).payload == "42"


def test_health_deep():
    report = HealthReport(
        (
            HealthCheck("atlas", True),
            HealthCheck("provider", False, "critical"),
        )
    )
    assert not report.healthy
    assert report.critical_failures[0].name == "provider"


def test_provider_certification():
    cert = ProviderCertification("sparta", True, ("FI-Infra",), 9, 10)
    assert cert.coverage == 0.9
    assert cert.ready
    assert not ProviderCertification("xp", True, (), 8, 10).ready


def test_provider_runtime():
    assert ready(RuntimeProbe("patria", True, 150, 0.01))
    assert not ready(RuntimeProbe("patria", True, 150, 0.10))
    assert not ready(RuntimeProbe("patria", False, 150, 0.01))


def test_cli_adapter():
    assert handle("report", available=("report",)).exit_code == 0
    assert handle("x", available=("report",)).exit_code == 2


def test_regression_report():
    good = CoverageReport(579, 580, 0.90, 0.91)
    bad = CoverageReport(579, 578, 0.90, 0.91)
    assert good.passed
    assert bad.regressions == ("test_count",)
