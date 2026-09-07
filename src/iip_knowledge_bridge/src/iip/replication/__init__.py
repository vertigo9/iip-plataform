"""IIP Replication Engine — track and propagate changes."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class ChangeType(Enum):
    FEATURE = "feature"
    FIX = "fix"
    BREAKING = "breaking"
    DEPRECATION = "deprecation"
    CONFIG = "config"


class ChangeStatus(Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    IMPLEMENTED = "implemented"
    CERTIFIED = "certified"
    ROLLED_BACK = "rolled_back"


@dataclass
class RFC:
    """Request For Change proposal."""

    id: str
    title: str
    description: str
    author: str
    change_type: ChangeType
    status: ChangeStatus = ChangeStatus.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    approved_at: datetime | None = None

    def approve(self) -> None:
        self.status = ChangeStatus.APPROVED
        self.approved_at = datetime.now(UTC)


@dataclass
class ADR:
    """Architecture Decision Record."""

    id: str
    rfc_id: str
    decision: str
    rationale: str
    consequences: str
    status: str = "accepted"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ReplicationLog:
    """Record of replicated change."""

    id: str
    rfc_id: str
    adr_id: str
    target_system: str
    status: ChangeStatus
    replicated_at: str | None = None
    certified_at: str | None = None


class ReplicationEngine:
    """Track and replicate changes through the pipeline."""

    _rfcs: dict[str, RFC] = {}
    _adrs: dict[str, ADR] = {}
    _logs: dict[str, ReplicationLog] = {}

    @classmethod
    def propose(
        cls, title: str, description: str, author: str, change_type: ChangeType
    ) -> RFC:
        """Create a new RFC."""
        rfc = RFC(
            id=str(uuid.uuid4())[:8],
            title=title,
            description=description,
            author=author,
            change_type=change_type,
        )
        cls._rfcs[rfc.id] = rfc
        return rfc

    @classmethod
    def approve_rfc(cls, rfc_id: str) -> bool:
        """Approve an RFC."""
        rfc = cls._rfcs.get(rfc_id)
        if not rfc:
            return False
        rfc.approve()
        return True

    @classmethod
    def record_adr(
        cls, rfc_id: str, decision: str, rationale: str, consequences: str
    ) -> ADR:
        """Record an ADR."""
        adr = ADR(
            id=str(uuid.uuid4())[:8],
            rfc_id=rfc_id,
            decision=decision,
            rationale=rationale,
            consequences=consequences,
        )
        cls._adrs[adr.id] = adr
        return adr

    @classmethod
    def replicate(cls, rfc_id: str, adr_id: str, target: str) -> ReplicationLog:
        """Mark change as replicated to target system."""
        log = ReplicationLog(
            id=str(uuid.uuid4())[:8],
            rfc_id=rfc_id,
            adr_id=adr_id,
            target_system=target,
            status=ChangeStatus.IMPLEMENTED,
            replicated_at=datetime.now(UTC).isoformat(),
        )
        cls._logs[log.id] = log
        return log

    @classmethod
    def certify(cls, log_id: str) -> bool:
        """Certify a replication as regression-free."""
        log = cls._logs.get(log_id)
        if not log:
            return False
        log.certified_at = datetime.now(UTC).isoformat()
        log.status = ChangeStatus.CERTIFIED
        return True

    @classmethod
    def status(cls) -> dict[str, object]:
        """Return replication status."""
        return {
            "rfcs_total": len(cls._rfcs),
            "rfcs_approved": sum(
                1 for r in cls._rfcs.values() if r.status == ChangeStatus.APPROVED
            ),
            "adrs_total": len(cls._adrs),
            "replications_total": len(cls._logs),
            "replications_certified": sum(
                1
                for log_entry in cls._logs.values()
                if log_entry.status == ChangeStatus.CERTIFIED
            ),
            "changes_by_type": {
                t.value: sum(1 for r in cls._rfcs.values() if r.change_type == t)
                for t in ChangeType
            },
        }
