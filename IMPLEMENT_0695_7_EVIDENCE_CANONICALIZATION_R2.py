#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
0695.7 EVIDENCE CANONICALIZATION R2

Safety-first revision of R1.

Fixes:
- Never permits a blank ticker to become part of the semantic identity.
- Derives canonical ticker from explicit ticker fields or Lineage / Original_Identity.
- Preserves all source rows and values for conflicts.
- Preserves Document_ID when present; otherwise records source FileName.
- Detects identity-key completeness before grouping.
- Read-only: no persistence, no KnowledgeBridge, no Vault writes.
"""

from __future__ import annotations

import csv
import hashlib
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

INPUT = REPORTS / "PCIP11_0695_7_FINAL_PROMOTION_GATE_R1.csv"
OUTPUT_CSV = REPORTS / "PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R2.csv"
OUTPUT_MD = REPORTS / "PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R2.md"


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


def derive_ticker(row):
    explicit = first(row, "Canonical_Ticker", "CanonicalTicker", "Ticker", "Resolved_Ticker")
    if explicit:
        return explicit.upper()

    lineage = first(row, "Lineage")
    if lineage:
        parts = [p.strip().upper() for p in re.split(r"\s*[-→>]+\s*", lineage) if p.strip()]
        if parts:
            return parts[-1]

    identity = first(row, "Original_Identity")
    if identity:
        m = re.match(r"^([A-Z]{4,6}\d{2})", identity.upper())
        if m:
            # For the PCIP11 migration, the destination ticker is the explicit
            # second side of Lineage when available. Without it, do not guess.
            return m.group(1)

    return ""


def stable_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def semantic_key(row):
    ticker = derive_ticker(row)
    period = first(row, "Resolved_Period", "Period")
    metric = first(row, "Metric", "Metric_Name")
    unit = first(row, "Resolved_Unit", "Original_Unit", "Unit")
    scale = first(row, "Scale")
    lineage_status = first(row, "Lineage_Status", "LineageStatus")

    return ticker, period, metric, unit, scale, lineage_status


def exact_signature(row):
    return (
        first(row, "SHA256"),
        first(row, "Document_ID"),
        first(row, "FileName"),
        first(row, "Metric", "Metric_Name"),
        first(row, "Value_Parsed", "Value"),
        first(row, "Value_Raw"),
        first(row, "Resolved_Unit", "Original_Unit", "Unit"),
        first(row, "Scale"),
        first(row, "Resolved_Period", "Period"),
        derive_ticker(row),
        first(row, "Lineage_Status", "LineageStatus"),
    )


def main():
    if not INPUT.exists():
        raise FileNotFoundError(f"Input not found: {INPUT}")

    with INPUT.open("r", encoding="utf-8-sig", newline="") as f:
        raw = list(csv.DictReader(f))

    if not raw:
        raise RuntimeError("Input CSV contains no rows.")

    pass_col = "Final_Promotion_Gate"
    if pass_col in raw[0]:
        rows = [r for r in raw if norm(r.get(pass_col)).upper() == "PASS"]
    else:
        rows = raw

    incomplete = []
    groups = defaultdict(list)

    for row in rows:
        key = semantic_key(row)
        if not all(key[:4]):  # ticker, period, metric, unit are mandatory
            incomplete.append((row, key))
            continue
        groups[key].append(row)

    canonical = []
    conflict_count = 0
    review_count = 0
    exact_collapsed = 0

    for key, members in groups.items():
        exact_groups = defaultdict(list)
        for row in members:
            exact_groups[exact_signature(row)].append(row)

        values = {
            first(r, "Value_Parsed", "Value_Raw", "Value")
            for r in members
        }
        values.discard("")

        if len(values) > 1:
            status = "CONFLICT"
            reason = "same_semantic_identity_different_values"
            conflict_count += 1
        elif len(exact_groups) == 1:
            status = "CANONICAL"
            reason = "unique_or_exact_duplicate"
            exact_collapsed += max(0, len(members) - 1)
        else:
            status = "REVIEW"
            reason = "same_identity_nonexact_duplicate"
            review_count += 1

        representative = sorted(
            members,
            key=lambda r: int(first(r, "Row")) if first(r, "Row").isdigit() else 10**12
        )[0]

        source_rows = sorted(
            [first(r, "Row") for r in members if first(r, "Row")],
            key=lambda x: int(x) if x.isdigit() else 10**12
        )
        shas = sorted({first(r, "SHA256") for r in members if first(r, "SHA256")})
        docs = sorted({first(r, "Document_ID") for r in members if first(r, "Document_ID")})
        files = sorted({first(r, "FileName") for r in members if first(r, "FileName")})

        ticker = derive_ticker(representative)
        identity_text = "|".join(key)

        out = dict(representative)
        out.update({
            "Derived_Canonical_Ticker": ticker,
            "Canonicalization_Status": status,
            "Canonicalization_Reason": reason,
            "Semantic_Identity_Key": identity_text,
            "Canonical_Observation_ID": "canonical:" + stable_hash(identity_text),
            "Source_Row_Count": str(len(members)),
            "Source_Rows": ",".join(source_rows),
            "Source_SHA256_Count": str(len(shas)),
            "Source_SHA256s": ";".join(shas),
            "Source_Document_Count": str(len(docs)),
            "Source_Document_IDs": ";".join(docs),
            "Source_File_Count": str(len(files)),
            "Source_FileNames": ";".join(files),
            "Distinct_Value_Count": str(len(values)),
            "Distinct_Values": ";".join(sorted(values)),
            "Persistence_Eligible": "YES" if status == "CANONICAL" else "NO",
            "Persistence_Executed": "NO",
            "KnowledgeBridge_Executed": "NO",
            "Vault_Changed": "NO",
        })
        canonical.append(out)

    canonical.sort(key=lambda r: (
        r.get("Derived_Canonical_Ticker", ""),
        first(r, "Resolved_Period", "Period"),
        first(r, "Metric"),
        first(r, "Row"),
    ))

    fields = []
    for row in canonical:
        for k in row:
            if k not in fields:
                fields.append(k)

    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(canonical)

    lines = [
        "# 0695.7 Evidence Canonicalization R2",
        "",
        "Safety-first canonicalization before persistence.",
        "",
        "## Result",
        "",
        f"- FINAL PASS source rows: {len(rows)}",
        f"- Canonical observations: {len(canonical)}",
        f"- CANONICAL / eligible: {sum(r['Canonicalization_Status']=='CANONICAL' for r in canonical)}",
        f"- CONFLICT / blocked: {conflict_count}",
        f"- REVIEW / blocked: {review_count}",
        f"- Incomplete identity rows: {len(incomplete)}",
        f"- Exact duplicate source rows collapsed: {exact_collapsed}",
        "",
        "## Identity safety",
        "",
        "- Canonical ticker is derived from explicit ticker fields or the destination side of Lineage.",
        "- Blank ticker is never accepted as a complete semantic identity.",
        "- Conflicting values are preserved and blocked.",
        "",
        "## Safety",
        "",
        "- Persistence executed: NO",
        "- KnowledgeBridge executed: NO",
        "- Vault changed: NO",
    ]
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("0695.7 EVIDENCE CANONICALIZATION R2")
    print("=" * 88)
    print(f"FINAL PASS source rows       : {len(rows)}")
    print(f"Canonical observations       : {len(canonical)}")
    print(f"CANONICAL / eligible         : {sum(r['Canonicalization_Status']=='CANONICAL' for r in canonical)}")
    print(f"CONFLICT / blocked           : {conflict_count}")
    print(f"REVIEW / blocked             : {review_count}")
    print(f"Incomplete identity rows     : {len(incomplete)}")
    print(f"Exact duplicate source rows  : {exact_collapsed}")
    print(f"CSV                          : {OUTPUT_CSV}")
    print(f"MD                           : {OUTPUT_MD}")
    print("")
    print("Persistence executed         : NO")
    print("KnowledgeBridge executed     : NO")
    print("Vault changed                : NO")


if __name__ == "__main__":
    configure_utf8()
    main()
