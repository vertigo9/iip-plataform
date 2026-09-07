#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
0695.7 CONFLICT RESOLUTION R1

Purpose
-------
Analyze the remaining canonicalization conflict without making any persistence
decision by frequency alone.

Current conflict:
    PCIP11 / 2024-01 / dividend_yield_annualized
    values: 13,40 and 13,09
    source rows: 17,18,21

Safety
------
- READ-ONLY.
- No Obsidian/Vault writes.
- No KnowledgeBridge writes.
- Does not automatically select the most frequent value.
- A value can be marked RESOLVED only when the source records contain
  sufficient distinguishing evidence. Otherwise the result remains UNRESOLVED.

The resolver first inspects the canonicalization R2 CSV and then attempts to
locate source artifacts in the repository using the SHA256 and FileName
metadata. It reports what is actually available locally; it does not invent
missing document content.
"""

from __future__ import annotations

import csv
import hashlib
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

INPUT = REPORTS / "PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R2.csv"
OUTPUT_CSV = REPORTS / "PCIP11_0695_7_CONFLICT_RESOLUTION_R1.csv"
OUTPUT_MD = REPORTS / "PCIP11_0695_7_CONFLICT_RESOLUTION_R1.md"

CONFLICT_METRIC = "dividend_yield_annualized"
CONFLICT_PERIOD = "2024-01"
CONFLICT_TICKER = "PCIP11"


def configure_utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def norm(v):
    return "" if v is None else str(v).strip()


def first(row, *names):
    for n in names:
        if n in row and norm(row[n]):
            return norm(row[n])
    return ""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def derive_ticker(row):
    explicit = first(row, "Derived_Canonical_Ticker", "Canonical_Ticker", "Ticker")
    if explicit:
        return explicit.upper()
    lineage = first(row, "Lineage")
    if lineage:
        parts = [p.strip().upper() for p in re.split(r"\s*[-→>]+\s*", lineage) if p.strip()]
        if parts:
            return parts[-1]
    return ""


def find_local_sources(filename: str, expected_sha: str):
    matches = []

    # First use the exact filename where practical.
    if filename:
        for p in ROOT.rglob(filename):
            if p.is_file():
                try:
                    actual = sha256_file(p)
                except Exception:
                    continue
                matches.append((p, actual, actual == expected_sha.upper()))

    # Then, if no exact filename was found, use basename matching and SHA scan
    # only over likely document locations to avoid traversing generated reports.
    if not matches and expected_sha:
        for base in [ROOT / "documents", ROOT / "data", ROOT / "inputs", ROOT / "sources", ROOT]:
            if not base.exists():
                continue
            try:
                iterator = base.rglob("*")
                for p in iterator:
                    if not p.is_file():
                        continue
                    if p.suffix.lower() not in {".pdf", ".txt", ".html", ".htm"}:
                        continue
                    # Skip reports and scripts.
                    if "reports" in p.parts:
                        continue
                    try:
                        actual = sha256_file(p)
                    except Exception:
                        continue
                    if actual == expected_sha.upper():
                        matches.append((p, actual, True))
            except Exception:
                pass

    # de-duplicate paths
    seen = set()
    out = []
    for item in matches:
        key = str(item[0].resolve())
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def main():
    if not INPUT.exists():
        raise FileNotFoundError(f"Input not found: {INPUT}")

    with INPUT.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    conflicts = [
        r for r in rows
        if first(r, "Canonicalization_Status") == "CONFLICT"
        and derive_ticker(r) == CONFLICT_TICKER
        and first(r, "Resolved_Period", "Period") == CONFLICT_PERIOD
        and first(r, "Metric", "Metric_Name") == CONFLICT_METRIC
    ]

    if len(conflicts) != 1:
        raise RuntimeError(
            f"Expected exactly one target conflict; found {len(conflicts)}."
        )

    conflict = conflicts[0]
    source_rows = [x for x in first(conflict, "Source_Rows").split(",") if x]
    values = [x for x in first(conflict, "Distinct_Values").split(";") if x]
    shas = [x for x in first(conflict, "Source_SHA256s").split(";") if x]
    files = [x for x in first(conflict, "Source_FileNames").split(";") if x]

    # The R2 output already establishes that the three rows share one SHA.
    # We preserve that fact and do not treat repetition as independent evidence.
    value_counts = Counter(values)

    source_inventory = []
    for filename in files:
        expected_sha = shas[0] if len(shas) == 1 else ""
        found = find_local_sources(filename, expected_sha)
        if found:
            for p, actual, sha_ok in found:
                source_inventory.append({
                    "FileName": filename,
                    "LocalPath": str(p),
                    "SHA256_Expected": expected_sha,
                    "SHA256_Actual": actual,
                    "SHA256_Match": "YES" if sha_ok else "NO",
                })
        else:
            source_inventory.append({
                "FileName": filename,
                "LocalPath": "",
                "SHA256_Expected": expected_sha,
                "SHA256_Actual": "",
                "SHA256_Match": "NOT_FOUND",
            })

    # Conservative decision: metadata alone cannot resolve 13,40 vs 13,09.
    # Only a future document-content comparison may resolve it.
    decision = "UNRESOLVED"
    decision_reason = (
        "same source SHA contains multiple values; metadata does not establish "
        "which value is semantically correct"
    )

    out = {
        "Canonical_Ticker": CONFLICT_TICKER,
        "Resolved_Period": CONFLICT_PERIOD,
        "Metric": CONFLICT_METRIC,
        "Source_Row_Count": first(conflict, "Source_Row_Count"),
        "Source_Rows": ",".join(source_rows),
        "Source_SHA256s": ";".join(shas),
        "Source_FileNames": ";".join(files),
        "Distinct_Value_Count": str(len(values)),
        "Distinct_Values": ";".join(values),
        "Value_Frequencies": ";".join(f"{k}={v}" for k, v in sorted(value_counts.items())),
        "Resolution_Status": decision,
        "Resolution_Reason": decision_reason,
        "Resolved_Value": "",
        "Independent_Source_Count": "1" if len(shas) == 1 else str(len(shas)),
        "Local_Source_Match_Count": str(sum(1 for x in source_inventory if x["SHA256_Match"] == "YES")),
        "Persistence_Eligible": "NO",
        "Persistence_Executed": "NO",
        "KnowledgeBridge_Executed": "NO",
        "Vault_Changed": "NO",
    }

    fields = list(out.keys())
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerow(out)

    lines = [
        "# 0695.7 Conflict Resolution R1",
        "",
        "Conservative resolution of the remaining PCIP11 2024-01 dividend-yield conflict.",
        "",
        "## Conflict",
        "",
        f"- Ticker: `{CONFLICT_TICKER}`",
        f"- Period: `{CONFLICT_PERIOD}`",
        f"- Metric: `{CONFLICT_METRIC}`",
        f"- Source rows: `{','.join(source_rows)}`",
        f"- Values: `{'; '.join(values)}`",
        f"- Source SHA count: `{len(shas)}`",
        "",
        "## Decision",
        "",
        f"- Status: **{decision}**",
        f"- Reason: {decision_reason}.",
        "- Frequency is not treated as independent evidence because all three rows share the same SHA.",
        "- No resolved value is assigned by this component.",
        "",
        "## Local source inventory",
        "",
    ]

    for item in source_inventory:
        lines.append(
            f"- `{item['FileName']}` → "
            f"{item['LocalPath'] or 'NOT FOUND'}; "
            f"SHA match: `{item['SHA256_Match']}`"
        )

    lines += [
        "",
        "## Safety",
        "",
        "- Persistence executed: NO",
        "- KnowledgeBridge executed: NO",
        "- Vault changed: NO",
        "- Persistence authorization: NOT GRANTED",
    ]

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("0695.7 CONFLICT RESOLUTION R1")
    print("=" * 88)
    print(f"Conflict                     : {CONFLICT_TICKER} / {CONFLICT_PERIOD} / {CONFLICT_METRIC}")
    print(f"Source rows                  : {','.join(source_rows)}")
    print(f"Distinct values              : {', '.join(values)}")
    print(f"Source SHA count             : {len(shas)}")
    print(f"Independent source count    : {out['Independent_Source_Count']}")
    print(f"Resolution status            : {decision}")
    print(f"Resolved value               : NOT ASSIGNED")
    print(f"Local SHA matches            : {out['Local_Source_Match_Count']}")
    print(f"CSV                          : {OUTPUT_CSV}")
    print(f"MD                           : {OUTPUT_MD}")
    print("")
    print("Persistence executed         : NO")
    print("KnowledgeBridge executed     : NO")
    print("Vault changed                : NO")


if __name__ == "__main__":
    configure_utf8()
    main()
