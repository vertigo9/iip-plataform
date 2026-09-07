from iip.hardening.certification_pipeline import CertificationInput, certify
from iip.hardening.compatibility import compare_keys
from iip.hardening.contracts import check_nonempty, check_version
from iip.hardening.determinism import stable_results
from iip.hardening.evidence_trace import EvidenceTrace
from iip.hardening.persistence import PersistedState, next_revision
from iip.hardening.provider_failover import ProviderState, choose_provider
from iip.hardening.scenario_harness import ScenarioCase, run
from iip.hardening.security import all_passed, guard


def test_contracts():
    assert check_nonempty("registry", ("A",)).passed
    assert not check_nonempty("registry", ()).passed
    assert check_version(2, 1).passed
    assert not check_version(1, 2).passed


def test_compatibility():
    result = compare_keys(("a", "b"), ("a", "b", "c"))
    assert result.compatible
    assert result.extra == ("c",)


def test_persistence_revision():
    first = next_revision(None, "abc", {"v": 1})
    second = next_revision(
        PersistedState("state", first.revision, first.checksum, first.payload),
        "def",
        {"v": 2},
    )
    assert first.revision == 1
    assert second.revision == 2


def test_provider_failover():
    result = choose_provider(
        (
            ProviderState("xp", False, 1),
            ProviderState("patria", True, 3),
            ProviderState("sparta", True, 2),
        )
    )
    assert result.name == "sparta"


def test_evidence_trace():
    complete = EvidenceTrace("d1", ("src1",), ("doc1",), ("ev1",))
    incomplete = EvidenceTrace("d2", (), ("doc2",), ())
    assert complete.complete
    assert not incomplete.complete


def test_scenario_harness():
    results = run(
        (
            ScenarioCase("ok", {"value": 1}),
            ScenarioCase("bad", {"value": 0}),
        ),
        lambda case: case.inputs["value"] == 1,
    )
    assert results[0].passed
    assert not results[1].passed


def test_determinism():
    assert stable_results(({"a": 1}, {"a": 1}))
    assert not stable_results((1, 2))


def test_security():
    checks = (guard("auth", True), guard("audit", True))
    assert all_passed(checks)
    assert not all_passed((guard("auth", False),))


def test_certification():
    cert = certify(CertificationInput(True, 0.90, True, True, True, True))
    assert cert.certified
    assert not certify(CertificationInput(True, 0.89, True, True, True, True)).certified
