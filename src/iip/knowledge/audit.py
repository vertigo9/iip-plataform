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
            # Bug real encontrado via teste de aceitacao de ponta a ponta
            # (12/09/2026): save_evidence() grava com o nome sanitizado
            # por ObsidianRepository._safe_filename() (ex: ":" vira "_"),
            # mas esta checagem comparava contra o evidence_id CRU --
            # qualquer evidencia com caracteres sanitizaveis no id (como
            # o formato "{provider}:{document_id}" que a camada
            # intelligence usa) sempre falhava aqui mesmo tendo sido
            # persistida corretamente. Usa a MESMA sanitizacao do
            # repositorio, nao uma copia dela, pra nao poder divergir de
            # novo no futuro.
            safe_id = self.repo._safe_filename(evidence_id)
            path = self.repo.vault / "04_Evidence" / f"{safe_id}.md"
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
