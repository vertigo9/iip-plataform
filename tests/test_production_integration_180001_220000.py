from iip.production_integration.allocation_review import build
from iip.production_integration.decision_guard import DecisionGuard
from iip.production_integration.evidence_bundle import EvidenceBundle
from iip.production_integration.evidence_bundle import normalize as normalize_bundle
from iip.production_integration.portfolio_contract import PortfolioIdentity, normalize
from iip.production_integration.production_cycle import run_cycle
from iip.production_integration.provider_consensus import Observation, calculate
from iip.production_integration.provider_mesh import ProviderCapability, candidates
from iip.production_integration.reconciliation import reconcile
from iip.production_integration.release_certificate import ReleaseCertificate
from iip.production_integration.service_health import ServiceHealth
from iip.production_integration.snapshot_manager import SnapshotManager


def test_portfolio_contract():
    identity = PortfolioIdentity("main", "owner", 1)
    contract = normalize(identity, ("cpfe3", "HGRU11", "cpfe3"))
    assert contract.valid
    assert contract.tickers == ("CPFE3", "HGRU11")


def test_snapshot_manager():
    manager = SnapshotManager()
    first = manager.save("main", "2026-08-29", "a", {"x": 1})
    second = manager.save("main", "2026-08-30", "b", {"x": 2})
    assert first.revision == 1
    assert second.revision == 2
    assert manager.latest("main").checksum == "b"


def test_reconciliation():
    result = reconcile(("HGRU11", "CPFE3"), ("cpfe3", "LVBI11"))
    assert result.matched == ("CPFE3",)
    assert result.missing == ("HGRU11",)
    assert result.unexpected == ("LVBI11",)
    assert not result.consistent


def test_provider_mesh():
    providers = (
        ProviderCapability("sparta", ("FI-Infra", "FII"), True, 2),
        ProviderCapability("patria", ("FII",), True, 1),
        ProviderCapability("xp", ("FII",), False, 0),
    )
    result = candidates(providers, "FII")
    assert tuple(x.provider for x in result) == ("patria", "sparta")


def test_provider_consensus():
    result = calculate(
        (
            Observation("xp", 100),
            Observation("patria", 102),
            Observation("sparta", 101),
        )
    )
    assert result.value == 101
    assert result.spread == 2


def test_decision_guard():
    good = DecisionGuard(True, True, True, True)
    bad = DecisionGuard(True, True, False, True)
    assert good.allowed
    assert not bad.allowed


def test_allocation_review():
    review = build("hgru11", "aportar", 0.12, concentration_breach=True)
    assert review.manual_review_required
    assert review.reason == "concentration"
    assert review.estimated_weight == 0.12


def test_evidence_bundle():
    bundle = EvidenceBundle("d1", ("s1", "s1"), ("doc1",), ("o1", "o1"))
    normalized = normalize_bundle(bundle)
    assert normalized.complete
    assert normalized.source_ids == ("s1",)
    assert normalized.observation_ids == ("o1",)


def test_service_health():
    healthy = ServiceHealth("atlas", True, 100, 0.01)
    degraded = ServiceHealth("atlas", True, 1500, 0.01)
    assert not healthy.degraded
    assert degraded.degraded


def test_production_cycle():
    identity = PortfolioIdentity("main", "owner", 1)
    portfolio = normalize(identity, ("HGRU11", "CPFE3"))
    guard = DecisionGuard(True, True, True, True)
    result = run_cycle(portfolio, ("hgru11", "cpfe3"), guard)
    assert result.portfolio_valid
    assert result.reconciliation_ok
    assert result.decision_allowed


def test_release_certificate():
    cert = ReleaseCertificate(True, 0.91, True, True, True, True)
    assert cert.certified
    assert not ReleaseCertificate(True, 0.89, True, True, True, True).certified
