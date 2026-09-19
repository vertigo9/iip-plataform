"""Filesystem-backed Knowledge repository.

Semantic identifiers are preserved in content; filesystem filenames are
sanitized for Windows. Compatibility helpers are retained for the existing
Knowledge/Vault/Projection layers.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any

from .models import Decision, Evidence, PortfolioSnapshot

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class AssetDirectory:
    """Compatibility wrapper that behaves like the historic Path return."""

    path: Path
    ticker: str
    asset_class: str

    def __fspath__(self) -> str:
        return str(self.path)

    def __str__(self) -> str:
        return str(self.path)

    def exists(self) -> bool:
        """Path-compatible existence check retained for legacy callers."""
        return self.path.exists()

    def is_dir(self) -> bool:
        return self.path.is_dir()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AssetDirectory):
            return self.path == other.path
        if isinstance(other, (str, Path)):
            return self.path == Path(other)
        return NotImplemented


class ObsidianRepository:
    def __init__(self, vault_path: Path | str) -> None:
        self.vault_path = Path(vault_path)
        self.vault = self.vault_path

    @staticmethod
    def _safe_filename(value: str) -> str:
        safe = _INVALID_FILENAME_CHARS.sub("_", str(value))
        safe = _CONTROL_CHARS.sub("_", safe)
        safe = re.sub(r"_+", "_", safe).strip(" ._")
        if not safe:
            safe = "record"
        if safe.upper() in {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10)),
        }:
            safe = f"_{safe}"
        return safe

    def asset_location(self, ticker: str, asset_class: str) -> AssetDirectory:
        """Legacy flat-path resolver (``vault/<CLASS>/<TICKER>``).

        Not used by the live persistence/projection pipeline. Kept only so
        the legacy-compatibility test suite (test_repository_*_compatibility)
        keeps passing. New code that needs the canonical asset folder
        (``vault/01_Assets/<Category>/<TICKER>``) should use
        ``iip.knowledge.vault.AssetVaultLocator`` instead — that is what
        ``KnowledgeProjection`` and the real vault on disk already use.
        """
        normalized_ticker = ticker.strip().upper()
        normalized_class = asset_class.strip().upper()
        path = (
            self.vault_path
            / self._safe_filename(normalized_class)
            / self._safe_filename(normalized_ticker)
        )
        path.mkdir(parents=True, exist_ok=True)
        return AssetDirectory(path, normalized_ticker, normalized_class)

    def ensure_asset_directory(self, ticker: str, asset_class: str) -> AssetDirectory:
        """Alias of :meth:`asset_location`. See its docstring — legacy only."""
        return self.asset_location(ticker, asset_class)

    @staticmethod
    def _ticker_match(path: Path, ticker: str) -> bool:
        return ticker.strip().upper() in path.stem.upper()

    def _write_once(self, path: Path, content: str) -> Path:
        if path.exists():
            raise FileExistsError(f"append-only record already exists: {path.name}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def _read_matching(self, directory: Path, ticker: str) -> tuple[Path, ...]:
        if not directory.exists():
            return ()
        return tuple(
            sorted(
                (p for p in directory.glob("*.md") if self._ticker_match(p, ticker)),
                key=lambda p: p.name,
            )
        )

    def list_decisions(self, ticker: str) -> tuple[Path, ...]:
        return self._read_matching(self.vault_path / "03_Decisions", ticker)

    def list_evidence(self, ticker: str) -> tuple[Path, ...]:
        return self._read_matching(self.vault_path / "04_Evidence", ticker)

    def list_snapshots(self, ticker: str | None = None) -> tuple[Path, ...]:
        directory = self.vault_path / "02_Portfolio" / "Snapshots"
        if not directory.exists():
            return ()
        paths = tuple(sorted(directory.glob("*.md"), key=lambda p: p.name))
        if ticker is None:
            return paths
        return tuple(p for p in paths if self._ticker_match(p, ticker))

    def save_evidence(self, evidence: Evidence) -> Path:
        path = (
            self.vault_path
            / "04_Evidence"
            / (f"{self._safe_filename(evidence.evidence_id)}.md")
        )
        content = (
            "---\n"
            "type: evidence\n"
            f"evidence_id: {evidence.evidence_id}\n"
            f"ticker: {evidence.ticker}\n"
            f"date: {evidence.date.isoformat()}\n"
            f"source_type: {evidence.source_type}\n"
            f"source_url: {evidence.source_url or ''}\n"
            f"title: {evidence.title or ''}\n"
            f"document_hash: {evidence.document_hash or ''}\n"
            "relevant_facts:\n"
            + "".join(f"- {fact}\n" for fact in evidence.relevant_facts)
            + "---\n"
        )
        return self._write_once(path, content)

    def save_decision(self, decision: Decision) -> Path:
        path = (
            self.vault_path
            / "03_Decisions"
            / (f"{self._safe_filename(decision.decision_id)}.md")
        )
        content = (
            "---\n"
            "type: decision\n"
            f"decision_id: {decision.decision_id}\n"
            f"ticker: {decision.ticker}\n"
            f"date: {decision.date.isoformat()}\n"
            f"new_verdict: {decision.new_verdict.value}\n"
            f"confidence: {decision.confidence}\n"
        )

        if decision.thesis_exit_state is not None:
            content += (
                f"thesis_exit_state: {decision.thesis_exit_state}\n"
                "thesis_exit_failed_gates:\n"
                + "".join(f"- {gate}\n" for gate in decision.thesis_exit_failed_gates)
                + "thesis_exit_attention_gates:\n"
                + "".join(
                    f"- {gate}\n" for gate in decision.thesis_exit_attention_gates
                )
                + "thesis_exit_unknown_gates:\n"
                + "".join(f"- {gate}\n" for gate in decision.thesis_exit_unknown_gates)
                + f"thesis_exit_critical_failure: "
                f"{decision.thesis_exit_critical_failure}\n"
            )

        content += "---\n"
        return self._write_once(path, content)

    @staticmethod
    def _position_lines(positions: tuple[Any, ...]) -> str:
        lines: list[str] = []
        for position in positions:
            if is_dataclass(position):
                data = asdict(position)
            elif hasattr(position, "__dict__"):
                data = dict(position.__dict__)
            else:
                data = {"repr": repr(position)}
            rendered = "; ".join(
                f"{key}: {value}" for key, value in sorted(data.items())
            )
            lines.append(f"- {rendered}\n")
        return "".join(lines)

    def save_snapshot(self, snapshot: PortfolioSnapshot) -> Path:
        path = (
            self.vault_path
            / "02_Portfolio"
            / "Snapshots"
            / (f"{self._safe_filename(snapshot.snapshot_id)}.md")
        )
        content = (
            "---\n"
            "type: portfolio_snapshot\n"
            f"snapshot_id: {snapshot.snapshot_id}\n"
            f"created_at: {snapshot.created_at.isoformat()}\n"
            f"portfolio_value: {snapshot.portfolio_value}\n"
            "positions:\n" + self._position_lines(snapshot.positions) + "---\n"
        )
        return self._write_once(path, content)
