from iip.platform.contracts import Evidence, EvidenceKind, ExecutionState
from iip.platform.evidence import EvidenceStore, content_hash
from iip.platform.execution import ProviderExecutionEngine, ProviderExecutor
from iip.platform.observability import RuntimeMetrics
from iip.platform.policy import PolicyDecision, SafeSourcePolicy
from iip.platform.portfolio_batch import plan_batches
from iip.platform.readiness import ReadinessGate
from iip.platform.release import ReleaseCheckpoint


def test_explicit_provider_fallback():
    calls = []

    def fail():
        calls.append("xp")
        raise RuntimeError("offline")

    def succeed():
        calls.append("b3")
        return Evidence("e1", EvidenceKind.MARKET_DATA, "b3", "test")

    engine = ProviderExecutionEngine(
        {
            "xp_asset": ProviderExecutor("xp_asset", "discover", fail),
            "b3": ProviderExecutor("b3", "discover", succeed),
        }
    )
    result = engine.run_asset("XPML11", ("xp_asset", "b3"))
    assert result.state == ExecutionState.READY
    assert calls == ["xp", "b3"]
    assert result.evidence[0].evidence_id == "e1"


def test_missing_executor_does_not_break_run():
    engine = ProviderExecutionEngine()
    result = engine.run_asset("HGRU11", ("patria", "sparta"))
    assert result.state == ExecutionState.SKIPPED
    assert result.provider_runs[0].error == "no_executor"


def test_evidence_hash_and_idempotency():
    h = content_hash(b"abc")
    assert len(h) == 64
    store = EvidenceStore()
    evidence = Evidence("doc1", EvidenceKind.DOCUMENT, "xp_asset", "url", h)
    assert store.put(evidence) == "CREATED"
    assert store.put(evidence) == "UNCHANGED"
    updated = Evidence(
        "doc1", EvidenceKind.DOCUMENT, "xp_asset", "url", content_hash(b"abcd")
    )
    assert store.put(updated) == "UPDATED"


def test_safe_source_policy_fails_closed():
    policy = SafeSourcePolicy()
    assert (
        policy.evaluate("sparta", certified=False, healthy=True).decision
        == PolicyDecision.DENY
    )
    assert (
        policy.evaluate("sparta", certified=True, healthy=False).decision
        == PolicyDecision.REVIEW
    )
    assert (
        policy.evaluate("sparta", certified=True, healthy=True).decision
        == PolicyDecision.ALLOW
    )


def test_runtime_metrics():
    metrics = RuntimeMetrics()
    for state in ("ready", "ready", "failed", "skipped"):
        metrics.record(state)
    assert metrics.executions == 4
    assert metrics.success_rate == 0.5


def test_batch_planning():
    assert plan_batches(["XPML11", "HGRU11", "CDII11"], 2) == (
        ("XPML11", "HGRU11"),
        ("CDII11",),
    )


def test_readiness_gate():
    gate = ReadinessGate(True, 2, 1, True, True)
    assert gate.production_ready
    assert not ReadinessGate(True, 0, 1, True, True).production_ready


def test_release_checkpoint():
    assert ReleaseCheckpoint("06.2-51→100", 358, 80).summary().startswith("06.2-51")


def test_portfolio_run_counts():
    engine = ProviderExecutionEngine(
        {
            "b3": ProviderExecutor(
                "b3",
                "discover",
                lambda: Evidence("b", EvidenceKind.MARKET_DATA, "b3", "test"),
            )
        }
    )
    run = engine.run_portfolio({"XPML11": ("b3",), "HGRU11": ("b3",)})
    assert run.succeeded == 2
    assert run.failed == 0
