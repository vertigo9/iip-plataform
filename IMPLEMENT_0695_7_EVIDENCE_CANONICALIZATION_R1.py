#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
0695.7 EVIDENCE CANONICALIZATION R1

Purpose
-------
Canonicalize the 0695.7 FINAL PROMOTION PASS population before persistence.

Safety contract
---------------
- READ-ONLY with respect to the Obsidian Vault.
- Does NOT execute metric persistence.
- Does NOT execute KnowledgeBridge writes.
- Produces CSV/MD reports only.
- Never silently chooses between conflicting values.
- Exact duplicate observations are collapsed canonically while all source
  rows remain represented in provenance fields.
- Same semantic identity with different values is marked CONFLICT and remains
  blocked for persistence.

Input
-----
reports/PCIP11_0695_7_FINAL_PROMOTION_GATE_R1.csv

Output
------
reports/PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R1.csv
reports/PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R1.md
"""

from __future__ import annotations

import csv
import hashlib
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

INPUT = REPORTS / "PCIP11_0695_7_FINAL_PROMOTION_GATE_R1.csv"
OUTPUT_CSV = REPORTS / "PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R1.csv"
OUTPUT_MD = REPORTS / "PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R1.md"


def configure_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def norm(value) -> str:
    return "" if value is None else str(value).strip()


def first(row, *names) -> str:
    for name in names:
        if name in row and norm(row[name]):
            return norm(row[name])
    return ""


def stable_hash(text: str, size: int = 24) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:size]


def semantic_key(row) -> tuple[str, ...]:
    """
    Identity deliberately excludes value so conflicting values for the same
    semantic observation cannot bypass the conflict gate.
    """
    return (
        first(row, "Canonical_Ticker", "CanonicalTicker", "Ticker"),
        first(row, "Resolved_Period", "Period"),
        first(row, "Metric", "Metric_Name"),
        first(row, "Resolved_Unit", "Original_Unit", "Unit"),
        first(row, "Scale"),
        first(row, "Lineage_Status", "LineageStatus"),
    )


def exact_signature(row) -> tuple[str, ...]:
    """
    Signature for exact observational duplicates. SHA is included because
    source-document identity is part of the evidence provenance.
    """
    return (
        first(row, "SHA256"),
        first(row, "Document_ID"),
        first(row, "Metric"),
        first(row, "Value_Parsed", "Value"),
        first(row, "Resolved_Unit", "Original_Unit", "Unit"),
        first(row, "Scale"),
        first(row, "Resolved_Period", "Period"),
        first(row, "Canonical_Ticker", "CanonicalTicker", "Ticker"),
        first(row, "Lineage_Status", "LineageStatus"),
    )


def classify(rows):
    by_semantic = defaultdict(list)
    for row in rows:
        by_semantic[semantic_key(row)].append(row)

    output = []
    for key, members in by_semantic.items():
        exact_groups = defaultdict(list)
        for row in members:
            exact_groups[exact_signature(row)].append(row)

        values = {
            first(r, "Value_Parsed", "Value_Raw", "Value")
            for r in members
        }
        nonempty_values = {v for v in values if v != ""}

        if len(nonempty_values) > 1:
            status = "CONFLICT"
            reason = "same_semantic_identity_different_values"
        elif len(exact_groups) == 1:
            status = "CANONICAL"
            reason = "unique_or_exact_duplicate"
        else:
            status = "REVIEW"
            reason = "same_identity_nonexact_duplicate"

        # Deterministic representative: lowest numeric Row where available.
        def row_num(r):
            try:
                return int(first(r, "Row"))
            except Exception:
                return 10**12

        representative = sorted(members, key=row_num)[0]

        source_rows = sorted(
            (first(r, "Row") for r in members if first(r, "Row")),
            key=lambda x: int(x) if x.isdigit() else 10**12,
        )
        source_shas = sorted({first(r, "SHA256") for r in members if first(r, "SHA256")})
        source_docs = sorted({first(r, "Document_ID") for r in members if first(r, "Document_ID")})

        canonical_id = (
            "canonical:"
            + stable_hash("|".join(key))
        )

        record = dict(representative)
        record.update({
            "Canonicalization_Status": status,
            "Canonicalization_Reason": reason,
            "Semantic_Identity_Key": "|".join(key),
            "Canonical_Observation_ID": canonical_id,
            "Source_Row_Count": str(len(members)),
            "Source_Rows": ",".join(source_rows),
            "Source_SHA256_Count": str(len(source_shas)),
            "Source_SHA256s": ";".join(source_shas),
            "Source_Document_Count": str(len(source_docs)),
            "Source_Document_IDs": ";".join(source_docs),
            "Distinct_Value_Count": str(len(nonempty_values)),
            "Distinct_Values": ";".join(sorted(nonempty_values)),
            "Persistence_Eligible": "YES" if status == "CANONICAL" else "NO",
            "Persistence_Executed": "NO",
            "KnowledgeBridge_Executed": "NO",
            "Vault_Changed": "NO",
        })
        output.append(record)

    output.sort(key=lambda r: (
        first(r, "Canonical_Ticker", "Ticker"),
        first(r, "Resolved_Period", "Period"),
        first(r, "Metric"),
        first(r, "Row"),
    ))
    return output


def main():
    if not INPUT.exists():
        raise FileNotFoundError(f"Input not found: {INPUT}")

    with INPUT.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    pass_col = "Final_Promotion_Gate"
    if rows and pass_col in rows[0]:
        rows = [r for r in rows if norm(r.get(pass_col)).upper() == "PASS"]
    elif rows and "Validation_Status" in rows[0]:
        rows = [r for r in rows if norm(r.get("Validation_Status")).upper() == "PASS"]

    canonical = classify(rows)

    fieldnames = []
    for row in canonical:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)

    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(canonical)

    status_counts = defaultdict(int)
    for row in canonical:
        status_counts[row["Canonicalization_Status"]] += 1

    exact_duplicate_rows = sum(
        max(0, int(r["Source_Row_Count"]) - 1)
        for r in canonical
        if r["Canonicalization_Status"] == "CANONICAL"
    )

    conflict_source_rows = sum(
        int(r["Source_Row_Count"])
        for r in canonical
        if r["Canonicalization_Status"] == "CONFLICT"
    )

    ready = status_counts["CANONICAL"]
    blocked = len(canonical) - ready

    lines = [
        "# 0695.7 Evidence Canonicalization R1",
        "",
        "Read-only canonicalization of the 0695.7 FINAL PROMOTION PASS population.",
        "",
        "## Input",
        "",
        f"- `{INPUT}`",
        f"- FINAL PASS source rows consumed: {len(rows)}",
        "",
        "## Result",
        "",
        f"- Canonical observations: {len(canonical)}",
        f"- CANONICAL / persistence eligible: {ready}",
        f"- CONFLICT / blocked: {status_counts['CONFLICT']}",
        f"- REVIEW / blocked: {status_counts['REVIEW']}",
        f"- Exact duplicate source rows collapsed: {exact_duplicate_rows}",
        f"- Conflict source rows retained for review: {conflict_source_rows}",
        "",
        "## Safety",
        "",
        "- Persistence executed: NO",
        "- KnowledgeBridge executed: NO",
        "- Vault changed: NO",
        "",
        "## Rule",
        "",
        "- Exact duplicate evidence is represented once canonically, with all source rows and source SHA256 values preserved.",
        "- Same semantic identity with different values is CONFLICT and is never silently resolved.",
        "- This component does not grant persistence authorization.",
    ]

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("0695.7 EVIDENCE CANONICALIZATION R1")
    print("=" * 88)
    print(f"FINAL PASS source rows       : {len(rows)}")
    print(f"Canonical observations       : {len(canonical)}")
    print(f"CANONICAL / eligible         : {ready}")
    print(f"CONFLICT / blocked           : {status_counts['CONFLICT']}")
    print(f"REVIEW / blocked             : {status_counts['REVIEW']}")
    print(f"Exact duplicate source rows  : {exact_duplicate_rows}")
    print(f"Conflict source rows         : {conflict_source_rows}")
    print(f"CSV                          : {OUTPUT_CSV}")
    print(f"MD                           : {OUTPUT_MD}")
    print("")
    print("Persistence executed         : NO")
    print("KnowledgeBridge executed     : NO")
    print("Vault changed                : NO")


if __name__ == "__main__":
    configure_utf8()
    main()
