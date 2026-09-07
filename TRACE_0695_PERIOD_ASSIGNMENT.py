from __future__ import annotations

from pathlib import Path
import re

ROOT = Path.cwd()

TARGETS = [
    "FIX_0695_2R2_PCIP11_CONTENT_TRIAGE.ps1",
    "FIX_0695_2R3_PCIP11_MULTIFORMAT_EXTRACTION.ps1",
    "FIX_0695_2R3_PCIP11_MULTIFORMAT_EXTRACTION (1).ps1",
    "FIX_0695_2R_PCIP11_MANIFEST_NORMALIZATION.ps1",
    "FIX_0695_3_PCIP11_CONTENT_CLASSIFICATION.ps1",
    "FIX_0695_4_PCIP11_METRIC_EVIDENCE_CANDIDATES.ps1",
    "FIX_0695_5R1_PCIP11_EVIDENCE_VALIDATION.ps1",
    "FIX_0695_5R2_PCIP11_EVIDENCE_VALIDATION.ps1",
    "FIX_0695_6R1_PCIP11_STRUCTURED_EVIDENCE_EXTRACTION.ps1",
    "FIX_0695_6R2_PCIP11_STRUCTURED_EVIDENCE_EXTRACTION.ps1",
    "FIX_0695_6R3_PCIP11_CANDIDATE_AUDIT.ps1",
    "FIX_0695_6R3R1_PCIP11_CANDIDATE_AUDIT.ps1",
    "FIX_0695_6R4R4_PCIP11_SEMANTIC_RESOLUTION.ps1",
]


def print_context(path: Path, lines: list[str], index: int) -> None:
    start = max(0, index - 5)
    end = min(len(lines), index + 6)

    print()
    print(f"--- {path.name} : lines {start + 1}-{end} ---")

    for i in range(start, end):
        marker = ">>>" if i == index else "   "
        print(f"{marker} {i + 1:04d}: {lines[i].rstrip()}")


def main() -> None:
    print("0695 PERIOD ASSIGNMENT TRACE")
    print("=" * 80)

    patterns = [
        re.compile(r"\bPeriod\b", re.IGNORECASE),
        re.compile(r"period\s*=", re.IGNORECASE),
        re.compile(r"period\s*:", re.IGNORECASE),
        re.compile(r"Add-Member.*Period", re.IGNORECASE),
        re.compile(r"PSCustomObject.*Period", re.IGNORECASE),
        re.compile(r"Select-Object.*Period", re.IGNORECASE),
        re.compile(r"Export-Csv", re.IGNORECASE),
        re.compile(r"fallback", re.IGNORECASE),
        re.compile(r"manifest", re.IGNORECASE),
        re.compile(r"year", re.IGNORECASE),
        re.compile(r"date", re.IGNORECASE),
    ]

    for name in TARGETS:
        path = ROOT / name

        if not path.exists():
            print()
            print(f"MISSING: {name}")
            continue

        try:
            text = path.read_text(
                encoding="utf-8-sig",
                errors="ignore",
            )
        except Exception as exc:
            print()
            print(f"ERROR reading {name}: {exc}")
            continue

        lines = text.splitlines()

        hits = set()

        for pattern in patterns:
            for index, line in enumerate(lines):
                if pattern.search(line):
                    hits.add(index)

        print()
        print("=" * 80)
        print(f"FILE: {name}")
        print(f"Total lines: {len(lines)}")
        print(f"Relevant locations: {len(hits)}")

        for index in sorted(hits):
            print_context(path, lines, index)

    print()
    print("=" * 80)
    print("TRACE COMPLETE")
    print("Vault changed: NO")
    print("Metric promoted: NO")


if __name__ == "__main__":
    main()