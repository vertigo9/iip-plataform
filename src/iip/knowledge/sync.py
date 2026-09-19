"""Incremental synchronization for IIP-owned Obsidian projection blocks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path

from .projection import AssetNoteProjector


class ProjectionStatus(str, Enum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    UNCHANGED = "UNCHANGED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class ProjectionFingerprint:
    """Deterministic fingerprint of the managed projection payload."""

    section: str
    digest: str

    @classmethod
    def from_content(cls, section: str, content: str) -> ProjectionFingerprint:
        normalized = str(content).replace("\r\n", "\n").replace("\r", "\n").strip("\n")
        payload = f"{section}\n{normalized}".encode()
        return cls(section=str(section), digest=sha256(payload).hexdigest())


@dataclass(frozen=True)
class ProjectionSyncResult:
    status: ProjectionStatus
    path: Path
    fingerprint: ProjectionFingerprint


class ProjectionSyncEngine:
    """Synchronize one IIP-owned section without touching unrelated Markdown."""

    def __init__(self, projector: AssetNoteProjector):
        self.projector = projector

    @staticmethod
    def _markers(section: str) -> tuple[str, str]:
        section = AssetNoteProjector._normalize_section(section)
        return (
            AssetNoteProjector.BEGIN_TEMPLATE.format(section=section),
            AssetNoteProjector.END_TEMPLATE.format(section=section),
        )

    @staticmethod
    def _compose_footer(content: str, notes: str | None) -> str:
        """FIX: rodapé do relatório precisa entrar no conteúdo sincronizado.

        Sem isto, uma mudança apenas em report.notes gera o mesmo
        fingerprint e o sync responde UNCHANGED com a nota desatualizada.
        """
        clean = str(notes or "").strip()
        if not clean or clean.lower() == "none":
            return content
        footer = f"> Rodapé: {clean}"
        if footer in content:
            return content
        return f"{content.rstrip()}\n\n{footer}"

    @classmethod
    def _extract_content(cls, text: str, section: str) -> str | None:
        begin, end = cls._markers(section)
        pattern = re.compile(
            rf"(?ms)^\s*{re.escape(begin)}\n(.*?)^\s*{re.escape(end)}\s*$"
        )
        match = pattern.search(text)
        if not match:
            return None
        return match.group(1).strip("\n")

    def sync_section(
        self,
        path: str | Path,
        section: str,
        content: str,
        notes: str | None = None,
    ) -> ProjectionSyncResult:
        path = Path(path)
        section = AssetNoteProjector._normalize_section(section)
        if not str(content).strip():
            return ProjectionSyncResult(
                ProjectionStatus.SKIPPED,
                path,
                ProjectionFingerprint.from_content(section, ""),
            )
        content = self._compose_footer(content, notes)
        fingerprint = ProjectionFingerprint.from_content(section, content)

        if not path.exists():
            self.projector.project_section(path, section, content)
            return ProjectionSyncResult(ProjectionStatus.CREATED, path, fingerprint)

        existing = path.read_text(encoding="utf-8")
        managed = self._extract_content(existing, section)
        if managed is not None:
            current = ProjectionFingerprint.from_content(section, managed)
            if current.digest == fingerprint.digest:
                return ProjectionSyncResult(
                    ProjectionStatus.UNCHANGED, path, fingerprint
                )

        self.projector.project_section(path, section, content)
        return ProjectionSyncResult(ProjectionStatus.UPDATED, path, fingerprint)

    def sync_asset_section(
        self,
        ticker: str,
        asset_class: str,
        role: str,
        section: str,
        content: str,
        notes: str | None = None,
    ) -> ProjectionSyncResult:
        projection = self.projector.locate(ticker, asset_class, role)
        return self.sync_section(projection.path, section, content, notes)
