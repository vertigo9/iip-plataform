from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from iip.health import (
    ConfigurationHealthCheck,
    FileSystemHealthCheck,
    HealthEngine,
    HealthResult,
    PythonVersionHealthCheck,
    SystemHealth,
)
from iip.knowledge.audit import DecisionAuditor
from iip.knowledge.models import Decision, DecisionChange, Evidence, Exposure, Verdict
from iip.knowledge.redundancy import find_redundant_exposures
from iip.knowledge.repository import ObsidianRepository


def test_repository_decision_evidence_and_append_only(tmp_path):
    repo = ObsidianRepository(tmp_path / "vault")

    decision = Decision(
        "DEC-CPFE3-1",
        "CPFE3",
        datetime.now(tz=UTC).date(),
        Verdict.MANTER,
        change_type=DecisionChange.NO_CHANGE,
        confidence=0.8,
        reasons=("r1",),
        risks=("risk",),
        evidence_ids=("EV-1",),
        review_triggers=("trigger",),
    )
    evidence = Evidence(
        "EV-1",
        "CPFE3",
        datetime.now(tz=UTC).date(),
        "FNET",
        source_url="https://example.invalid",
        document_hash="abc",
        relevant_facts=("fact",),
    )

    dpath = repo.save_decision(decision)
    epath = repo.save_evidence(evidence)

    assert dpath.exists()
    assert epath.exists()
    assert "CPFE3" in dpath.read_text(encoding="utf-8")
    assert "fact" in epath.read_text(encoding="utf-8")

    try:
        repo.save_decision(decision)
    except FileExistsError:
        pass
    else:
        raise AssertionError("decision repository is not append-only")

    try:
        repo.save_evidence(evidence)
    except FileExistsError:
        pass
    else:
        raise AssertionError("evidence repository is not append-only")


def test_decision_auditor_missing_and_invalid(tmp_path):
    repo = ObsidianRepository(tmp_path / "vault")
    auditor = DecisionAuditor(repo)

    invalid = Decision(
        "D-1",
        "CPFE3",
        datetime.now(tz=UTC).date(),
        Verdict.MANTER,
        confidence=1.5,
        evidence_ids=("missing",),
    )
    issues = auditor.audit(invalid)
    assert {i.code for i in issues} == {"MISSING_EVIDENCE", "INVALID_CONFIDENCE"}

    valid = Decision(
        "D-2", "CPFE3", datetime.now(tz=UTC).date(), Verdict.MANTER, confidence=0.5
    )
    assert auditor.audit(valid) == []


def test_redundancy_threshold_and_sorting():
    exposures = [
        Exposure("A", "banking", 0.12),
        Exposure("B", "banking", 0.11),
        Exposure("C", "energy", 0.19),
        Exposure("D", "energy", 0.01),
    ]
    result = find_redundant_exposures(exposures, threshold=0.20)
    assert result[0]["factor"] == "banking"
    assert result[0]["aggregate_weight"] == 0.23
    assert result[0]["assets"] == ["A", "B"]


def test_health_results_system_and_engine(tmp_path):
    healthy = HealthResult("ok", True, "ok", metadata={"x": "1"})
    unhealthy = HealthResult("bad", False, "bad")
    assert SystemHealth([healthy]).healthy
    assert not SystemHealth([healthy, unhealthy]).healthy
    payload = SystemHealth([healthy, unhealthy]).to_dict()
    assert payload["status"] == "unhealthy"

    class Boom:
        name = "boom"

        def check(self, _):
            raise RuntimeError("boom")

    engine = HealthEngine(SimpleNamespace(app_name="IIP"))
    engine.register(Boom())
    result = engine.run_all()
    assert len(result.checks) == 1
    assert not result.checks[0].healthy


def test_health_builtin_checks(tmp_path):
    settings = SimpleNamespace(
        app_name="IIP",
        environment=SimpleNamespace(value="testing"),
        base_dir=Path(tmp_path),
    )
    missing = SimpleNamespace(
        app_name="",
        environment=SimpleNamespace(value="testing"),
        base_dir=Path(tmp_path) / "missing",
    )

    assert ConfigurationHealthCheck().check(settings).healthy
    assert not ConfigurationHealthCheck().check(missing).healthy
    assert FileSystemHealthCheck().check(settings).healthy
    assert not FileSystemHealthCheck().check(missing).healthy
    assert PythonVersionHealthCheck().check(settings).healthy
