from iip.production.audit import AuditEvent, AuditLog
from iip.production.automation import JobRunner, JobSpec, JobStatus
from iip.production.config import ProductionConfig, can_execute_live
from iip.production.guardrails import AutomationContext, GuardrailDecision, evaluate
from iip.production.health import HealthSnapshot
from iip.production.portfolio_snapshot import PortfolioSnapshot
from iip.production.reconciliation import reconcile
from iip.production.recovery import RetryPolicy, should_retry
from iip.production.release import ReleaseGate
from iip.production.schedule import ScheduleSpec, validate_schedule


def test_job_runner_success_and_failure():
    runner = JobRunner(
        (
            JobSpec("ok", lambda: 42),
            JobSpec("fail", lambda: (_ for _ in ()).throw(RuntimeError("x"))),
        )
    )
    assert runner.run("ok").status == JobStatus.SUCCESS
    assert runner.run("ok").value == 42
    assert runner.run("fail").status == JobStatus.FAILED


def test_schedule_validation():
    ok, errors = validate_schedule(ScheduleSpec("daily", "DAILY"))
    assert ok and not errors


def test_guardrails_fail_closed():
    assert (
        evaluate(AutomationContext(False, 3, True)).decision == GuardrailDecision.DENY
    )
    assert (
        evaluate(AutomationContext(True, 0, True)).decision == GuardrailDecision.REVIEW
    )
    assert (
        evaluate(AutomationContext(True, 2, True, simulated=True)).decision
        == GuardrailDecision.REVIEW
    )


def test_audit_log_is_append_only_from_public_api():
    log = AuditLog()
    log.append(AuditEvent("1", "decision", "system", "2026-08-29T00:00:00Z", "hash"))
    assert len(log.events()) == 1
    assert log.events()[0].event_id == "1"


def test_reconciliation():
    result = reconcile(("A", "B"), ("B", "C"))
    assert not result.consistent
    assert result.missing == ("A",)
    assert result.unexpected == ("C",)


def test_live_execution_is_fail_closed():
    assert not can_execute_live(ProductionConfig())
    assert can_execute_live(
        ProductionConfig(
            environment="production",
            automation_enabled=True,
            live_execution_enabled=True,
        )
    )


def test_production_health():
    healthy = HealthSnapshot(True, True, True, True, True)
    unhealthy = HealthSnapshot(True, True, False, True, True)
    assert healthy.production_healthy
    assert not unhealthy.production_healthy


def test_retry_policy():
    policy = RetryPolicy(attempts=3)
    assert should_retry(0, policy)
    assert should_retry(2, policy)
    assert not should_retry(3, policy)


def test_release_gate():
    assert ReleaseGate(True, 87, True, True, True).pass_gate
    assert not ReleaseGate(True, 79, True, True, True).pass_gate


def test_portfolio_snapshot_weight():
    snapshot = PortfolioSnapshot("2026-08-29", (("HGRU11", 100), ("XPML11", 300)), 400)
    assert snapshot.weight("hgru11") == 0.25
