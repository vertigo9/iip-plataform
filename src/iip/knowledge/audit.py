from __future__ import annotations

from dataclasses import dataclass

from .models import Decision
from .repository import ObsidianRepository


@dataclass(frozen=True)
class AuditIssue:
    severity: str
    code: str
    message: str


class DecisionAuditor:
    def __init__(self, repository: ObsidianRepository):
        self.repo = repository

    def audit(self, d: Decision) -> list[AuditIssue]:
        issues: list[AuditIssue] = []
        for evidence_id in d.evidence_ids:
            path = self.repo.vault / "04_Evidence" / f"{evidence_id}.md"
            if not path.exists():
                issues.append(
                    AuditIssue(
                        "ERROR",
                        "MISSING_EVIDENCE",
                        f"Evidence not found: {evidence_id}",
                    )
                )
        if not (0 <= d.confidence <= 1):
            issues.append(
                AuditIssue(
                    "ERROR", "INVALID_CONFIDENCE", "Confidence must be between 0 and 1"
                )
            )
        return issues
