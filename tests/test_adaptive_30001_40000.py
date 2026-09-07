from iip.adaptive.adaptive_report import AdaptiveReport
from iip.adaptive.adaptive_router import RouteCandidate, choose
from iip.adaptive.anomaly import detect
from iip.adaptive.decision_explanation import build
from iip.adaptive.portfolio_alerts import yield_alert
from iip.adaptive.refresh_policy import build_policy
from iip.adaptive.run_registry import RunRegistry
from iip.adaptive.signal_fusion import Signal, fuse
from iip.adaptive.source_priority import rank


def test_refresh_policy_is_bounded():
    result = build_policy(10, 0)
    assert result.criticality == 5
    assert result.change_frequency == 1
    assert result.max_age_hours > 0


def test_source_priority():
    result = rank("sparta", 0.9, 0.8)
    assert result.priority == 0.87


def test_adaptive_router_chooses_best_eligible():
    result = choose(
        (
            RouteCandidate("xp", True, False, 0.99),
            RouteCandidate("patria", True, True, 0.80),
            RouteCandidate("sparta", False, True, 1.00),
        )
    )
    assert result.provider == "patria"


def test_anomaly_detection():
    result = detect((10.0, 10.0, 10.0), 15.0)
    assert result.anomalous
    assert result.baseline_mean == 10.0


def test_signal_fusion():
    result = fuse(
        (
            Signal("valuation", 9, 2),
            Signal("quality", 7, 1),
        )
    )
    assert result.score == 8.333333333333
    assert result.contributors == ("valuation", "quality")


def test_explanation_deduplicates():
    result = build("Manter", ("qualidade", "qualidade"), ("e1", "e1"))
    assert result.factors == ("qualidade",)
    assert result.evidence_ids == ("e1",)


def test_yield_alert():
    assert yield_alert("HGRU11", 0.08, 0.10).severity == "medium"
    assert yield_alert("HGRU11", 0.07, 0.10).severity == "high"
    assert yield_alert("HGRU11", 0.095, 0.10) is None


def test_run_registry_resumes():
    registry = RunRegistry()
    registry.start("r1")
    registry.checkpoint("r1", "hgru11")
    registry.checkpoint("r1", "cpfe3")
    state = registry.complete("r1")
    assert state.status == "complete"
    assert state.completed_assets == ("HGRU11", "CPFE3")


def test_adaptive_report():
    report = AdaptiveReport("r1", 20, 1, 2, 1, "ok")
    assert report.healthy
