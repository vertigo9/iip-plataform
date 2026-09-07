from iip.product.audit import AuditEvent, AuditLog
from iip.product.decision_api import view
from iip.product.readiness import Readiness
from iip.product.recovery import RecoveryStore
from iip.product.release import evaluate_release
from iip.product.rmg import RMGSection, build
from iip.product.scenario import Scenario, evaluate
from iip.product.scheduler import JobScheduler, ScheduledJob
from iip.product.service import PortfolioService
from iip.product.state_store import PortfolioStateStore


def test_service_contract():
    service = PortfolioService({"health": lambda x: x == "ok"})
    assert service.execute("health", x="ok").ok
    assert not service.execute("missing").ok


def test_state_store_versions():
    store = PortfolioStateStore()
    first = store.save("portfolio", {"value": 1})
    second = store.save("portfolio", {"value": 2})
    assert first.version == 1
    assert second.version == 2
    assert store.latest("portfolio").value["value"] == 2
    assert len(store.history("portfolio")) == 2


def test_scheduler():
    scheduler = JobScheduler()
    scheduler.register(ScheduledJob("daily-rmg", "daily"))
    scheduler.register(ScheduledJob("weekly-rmg", "weekly"))
    assert tuple(x.name for x in scheduler.due("daily")) == ("daily-rmg",)


def test_rmg():
    report = build(
        "2026-08-29",
        (RMGSection("Income", (("annual", 36000),)),),
    )
    assert report.metric_count == 1


def test_audit():
    log = AuditLog()
    log.record(AuditEvent("e1", "decision", "system", ("src1",), "2026-08-29"))
    assert len(log.for_operation("decision")) == 1


def test_decision_api():
    result = view("cpfe3", "aportar", 12, -1, ("quality", "quality"))
    assert result.ticker == "CPFE3"
    assert result.action == "APORTAR"
    assert result.score == 10
    assert result.confidence == 0
    assert result.rationale == ("quality",)


def test_scenario_engine():
    result = evaluate(
        (
            Scenario("base", (("growth", 0.05),)),
            Scenario("bull", (("growth", 0.10),)),
        ),
        lambda s: dict(s.parameters)["growth"] * 100,
    )
    assert result[0].score == 5
    assert result[1].score == 10


def test_recovery_is_idempotent():
    store = RecoveryStore()
    state = store.checkpoint("r1", "valuation")
    store.checkpoint("r1", "valuation")
    assert state.completed_steps == ("valuation",)
    assert store.is_completed("r1", "valuation")


def test_readiness():
    good = Readiness(True, 0.90, True, True)
    bad = Readiness(True, 0.89, True, True)
    assert good.ready
    assert not bad.ready


def test_release_gate():
    readiness = Readiness(True, 0.95, True, True)
    release = evaluate_release("06.2.100000", readiness)
    assert release.releasable
