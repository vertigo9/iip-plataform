"""Safe projection of IIP-owned sections into Obsidian asset notes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .vault import AssetVaultLocator, normalize_ticker

_NOTE_ROLE_FILENAMES = {
    "index": "00_{ticker}_Index.md",
    "identity": "{ticker} - Identidade e Estrutura.md",
    "portfolio": "{ticker} - Carteira e Crédito.md",
    "distributions": "{ticker} - Distribuições.md",
    "events": "{ticker} - Eventos e Reestruturações.md",
    "performance": "{ticker} - Performance Histórica.md",
    "sources": "{ticker} - Fontes.md",
    "scoring": "{ticker} - Score e Ranking.md",
}
_ROLE_ALIASES = {
    "index": "index",
    "identidade": "identity",
    "identity": "identity",
    "carteira": "portfolio",
    "portfolio": "portfolio",
    "distribuicoes": "distributions",
    "distributions": "distributions",
    "eventos": "events",
    "events": "events",
    "performance": "performance",
    "fontes": "sources",
    "sources": "sources",
    "score": "scoring",
    "scoring": "scoring",
    "ranking": "scoring",
}


@dataclass(frozen=True)
class AssetNoteProjection:
    ticker: str
    asset_class: str
    role: str
    path: Path


class AssetNoteProjector:
    """Project controlled IIP sections without replacing human-authored Markdown."""

    BEGIN_TEMPLATE = "<!-- IIP:BEGIN {section} -->"
    END_TEMPLATE = "<!-- IIP:END {section} -->"
    _FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)

    def __init__(self, vault: str | Path):
        self.locator = AssetVaultLocator(vault)

    @staticmethod
    def normalize_role(role: str) -> str:
        key = str(role).strip().lower().replace("-", "_").replace(" ", "_")
        try:
            return _ROLE_ALIASES[key]
        except KeyError as exc:
            raise ValueError(f"Unsupported asset note role: {role}") from exc

    def locate(self, ticker: str, asset_class: str, role: str) -> AssetNoteProjection:
        ticker = normalize_ticker(ticker)
        role = self.normalize_role(role)
        loc = self.locator.locate(ticker, asset_class)
        return AssetNoteProjection(
            ticker,
            loc.asset_class,
            role,
            loc.path / _NOTE_ROLE_FILENAMES[role].format(ticker=ticker),
        )

    def project_section(self, path: str | Path, section: str, content: str) -> Path:
        path = Path(path)
        section = self._normalize_section(section)
        content = str(content).strip("\n")
        begin = self.BEGIN_TEMPLATE.format(section=section)
        end = self.END_TEMPLATE.format(section=section)
        block = f"{begin}\n{content}\n{end}"
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        pattern = re.compile(
            rf"(?ms)^\s*{re.escape(begin)}\n.*?^\s*{re.escape(end)}\s*$"
        )
        if pattern.search(existing):
            updated = pattern.sub(block, existing, count=1)
        else:
            if not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
            updated = (
                existing.rstrip()
                + (("\n\n") if existing.strip() else "")
                + block
                + "\n"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(updated, encoding="utf-8")
        return path

    def project_asset_section(
        self, ticker: str, asset_class: str, role: str, section: str, content: str
    ) -> Path:
        return self.project_section(
            self.locate(ticker, asset_class, role).path, section, content
        )

    @classmethod
    def _parse_frontmatter(cls, text: str) -> tuple[dict[str, str], str]:
        """Hand-rolled parse (same convention as ObsidianRepository.save_evidence's
        hand-written frontmatter, no YAML dependency needed for simple scalars).
        Values keep their raw string form -- callers that need numbers back
        parse them themselves; Dataview reads frontmatter as text either way."""
        match = cls._FRONTMATTER_RE.match(text)
        if not match:
            return {}, text
        fields: dict[str, str] = {}
        for line in match.group(1).splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                fields[key.strip()] = value.strip()
        return fields, text[match.end() :]

    @staticmethod
    def _format_frontmatter(fields: dict[str, str]) -> str:
        body = "\n".join(f"{key}: {value}" for key, value in fields.items())
        return f"---\n{body}\n---\n"

    def project_frontmatter(self, path: str | Path, updates: dict[str, object]) -> Path:
        """Idempotently merge ``updates`` into the note's YAML frontmatter,
        preserving both the rest of the file and any existing frontmatter
        keys not in ``updates``. None values are dropped (not written as
        the literal string "None") rather than fabricated as empty."""
        path = Path(path)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        fields, rest = self._parse_frontmatter(existing)
        for key, value in updates.items():
            if value is None:
                fields.pop(key, None)
            else:
                fields[key] = str(value)
        updated = self._format_frontmatter(fields) + rest
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(updated, encoding="utf-8")
        return path

    def project_asset_frontmatter(
        self, ticker: str, asset_class: str, role: str, updates: dict[str, object]
    ) -> Path:
        return self.project_frontmatter(
            self.locate(ticker, asset_class, role).path, updates
        )

    @staticmethod
    def _normalize_section(section: str) -> str:
        value = str(section).strip()
        if not value:
            raise ValueError("section must not be empty")
        if "\n" in value or "\r" in value:
            raise ValueError("section must be a single line")
        if "<!--" in value or "-->" in value:
            raise ValueError("section contains unsafe marker characters")
        return value
