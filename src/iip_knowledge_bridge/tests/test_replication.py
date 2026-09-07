"""Tests for IIP Replication Engine."""

from iip.replication import ChangeStatus, ChangeType, ReplicationEngine


def test_propose_rfc():
    rfc = ReplicationEngine.propose(
        "Test RFC", "Description", "Author", ChangeType.FEATURE
    )
    assert rfc.id is not None
    assert rfc.title == "Test RFC"
    assert rfc.status == ChangeStatus.DRAFT


def test_approve_rfc():
    rfc = ReplicationEngine.propose("Test RFC 2", "Desc", "Author", ChangeType.FIX)
    ReplicationEngine.approve_rfc(rfc.id)
    assert rfc.status == ChangeStatus.APPROVED


def test_record_adr():
    rfc = ReplicationEngine.propose("ADR Test", "Desc", "Author", ChangeType.CONFIG)
    ReplicationEngine.approve_rfc(rfc.id)
    adr = ReplicationEngine.record_adr(rfc.id, "Decision", "Rationale", "Consequences")
    assert adr.rfc_id == rfc.id


def test_replicate_and_certify():
    rfc = ReplicationEngine.propose("Repl Test", "Desc", "Author", ChangeType.FEATURE)
    ReplicationEngine.approve_rfc(rfc.id)
    adr = ReplicationEngine.record_adr(rfc.id, "Dec", "Rat", "Cons")
    log = ReplicationEngine.replicate(rfc.id, adr.id, "target1")
    ReplicationEngine.certify(log.id)
    status = ReplicationEngine.status()
    assert status["replications_certified"] >= 1
