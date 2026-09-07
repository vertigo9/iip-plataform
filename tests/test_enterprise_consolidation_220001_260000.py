from iip.enterprise_consolidation.allocation_control import evaluate
from iip.enterprise_consolidation.audit_trail import AuditRecord, AuditTrail
from iip.enterprise_consolidation.consolidator import consolidate
from iip.enterprise_consolidation.decision_consistency import DecisionRecord, check
from iip.enterprise_consolidation.models import ConsolidationInput, PortfolioRef
from iip.enterprise_consolidation.pipeline import EnterprisePipelineInput, run
from iip.enterprise_consolidation.portfolio_registry import (
    PortfolioEntry,
    PortfolioRegistry,
)
from iip.enterprise_consolidation.provider_matrix import (
    ProviderCoverage,
    domain_coverage,
    matrix,
)
from iip.enterprise_consolidation.reconciliation import compare
from iip.enterprise_consolidation.release_gate import ReleaseGate
from iip.enterprise_consolidation.scenario_portfolio import PortfolioScenarioPoint, rank
from iip.enterprise_consolidation.source_governance import SourcePolicy, approve


def test_portfolio_registry():
    registry = PortfolioRegistry()
    registry.register(PortfolioEntry("main", "Main"))
    registry.register(PortfolioEntry("disabled", "Disabled", False))
    assert registry.get("main").name == "Main"
    assert tuple(x.portfolio_id for x in registry.enabled()) == ("main",)


def test_consolidation():
    data = ConsolidationInput(
        (PortfolioRef("main", 1), PortfolioRef("secondary", 1)), 5, 20, 10
    )
    result = consolidate(data)
    assert result.consistent
    assert result.unique_portfolios == 2


def test_provider_matrix():
    providers = (
        ProviderCoverage("sparta", ("FI-Infra",), True, 2),
        ProviderCoverage("patria", ("FII",), True, 1),
        ProviderCoverage("xp", ("FII",), False, 0),
    )
    assert matrix(providers)[0].provider == "patria"
    assert domain_coverage(providers) == (("FI-Infra", 1), ("FII", 1))


def test_source_governance():
    policy = SourcePolicy(2, True, False)
    assert approve(
        evidence_count=3, provider_available=True, stale=False, policy=policy
    )
    assert not approve(
        evidence_count=1, provider_available=True, stale=False, policy=policy
    )
    assert not approve(
        evidence_count=3, provider_available=False, stale=False, policy=policy
    )
    assert not approve(
        evidence_count=3, provider_available=True, stale=True, policy=policy
    )


def test_decision_consistency():
    result = check(
        (
            DecisionRecord("HGRU11", "APORTAR", 8),
            DecisionRecord("HGRU11", "MANTER", 7),
        )
    )
    assert not result.consistent
    assert result.conflicts == ("HGRU11",)


def test_allocation_control():
    result = evaluate("cpfe3", 0.10, 0.15, 0.05)
    assert result.approved
    assert result.ticker == "CPFE3"


def test_audit_trail():
    trail = AuditTrail()
    trail.append(AuditRecord("e1", "main", "decision", ("src1",)))
    trail.append(AuditRecord("e2", "secondary", "decision", ("src2",)))
    assert len(trail.portfolio("main")) == 1


def test_scenario_portfolio_rank():
    result = rank(
        (
            PortfolioScenarioPoint("main", "stress", 6),
            PortfolioScenarioPoint("secondary", "base", 8),
        )
    )
    assert result[0].portfolio_id == "secondary"


def test_reconciliation():
    result = compare(("HGRU11", "CPFE3"), ("cpfe3", "LVBI11"))
    assert result.matched == 1
    assert result.missing == 1
    assert result.unexpected == 1
    assert not result.consistent


def test_pipeline():
    data = EnterprisePipelineInput(
        "2026-08-29",
        ConsolidationInput((PortfolioRef("main", 1),), 3, 5, 4),
        True,
    )
    result = run(data)
    assert result.result.consistent
    assert result.release_ready


def test_release_gate():
    gate = ReleaseGate(True, 0.91, True, True, True)
    assert gate.certified
    assert not ReleaseGate(True, 0.89, True, True, True).certified
