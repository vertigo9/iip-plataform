#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
0695.7 PERSISTENCE ADAPTER R3

Schema-compatible dry-run adapter for the R3 canonicalization output.

Important:
- R3 does not expose Canonical_Ticker / Value_Parsed consistently.
- Canonical ticker is recovered from the canonical lineage:
      CVBI11 -> PCIP11
  using the terminal ticker as the canonical destination.
- Value is recovered from Value_Parsed, Value, or Selected/Resolved value fields.
- Persistence_Eligible is derived from Canonicalization_Status when the
  explicit field is absent, rather than treating a missing field as NO.

No persistence, KnowledgeBridge, or Vault write is performed.
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

INPUT_CSV = REPORTS / "PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R4.csv"
OUTPUT_CSV = REPORTS / "PCIP11_0695_7_PERSISTENCE_ADAPTER_R3.csv"
OUTPUT_MD = REPORTS / "PCIP11_0695_7_PERSISTENCE_ADAPTER_R3.md"


def norm(v):
    return (v or "").strip()


def first_value(row, *names):
    for name in names:
        v = norm(row.get(name))
        if v:
            return v
    return ""


def canonical_ticker(row):
    explicit = first_value(row, "Canonical_Ticker", "CanonicalTicker")
    if explicit:
        return explicit

    lineage = first_value(row, "Lineage", "lineage")
    if "->" in lineage:
        return lineage.split("->")[-1].strip()

    # R3 is a PCIP11 canonicalization output. Use original identity only
    # as a final fallback when it is already a current PCIP11 identity.
    original = first_value(row, "Original_Identity")
    if original.startswith("PCIP11"):
        return "PCIP11"

    return ""


def resolved_value(row):
    return first_value(
        row,
        "Value_Parsed",
        "Value",
        "Resolved_Value",
        "Selected_Value",
        "ResolvedValue",
    )


def persistence_eligible(row, canonical_status):
    explicit = first_value(row, "Persistence_Eligible")
    if explicit:
        return explicit.upper() == "YES"

    # R3 canonical rows are persistence candidates unless blocked by
    # canonicalization status.
    return canonical_status == "CANONICAL"


def persistence_key(row, ticker):
    return "|".join([
        ticker,
        first_value(row, "Resolved_Period"),
        first_value(row, "Metric"),
        first_value(row, "Resolved_Unit", "Original_Unit"),
        first_value(row, "Scale") or "1",
    ])


def make_evidence_id(row, key):
    existing = first_value(row, "Knowledge_Evidence_ID", "Canonical_Observation_ID")
    if existing:
        return existing
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    return f"canonical:{digest}"


def main():
    print("0695.7 PERSISTENCE ADAPTER R2")
    print("=" * 88)

    if not INPUT_CSV.exists():
        print(f"ERROR: input not found: {INPUT_CSV}")
        return 2

    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    prepared = []

    for row in rows:
        status = first_value(row, "Canonicalization_Status").upper()
        ticker = canonical_ticker(row)
        period = first_value(row, "Resolved_Period")
        metric = first_value(row, "Metric")
        value = resolved_value(row)
        unit = first_value(row, "Resolved_Unit", "Original_Unit")
        scale = first_value(row, "Scale") or "1"
        sha = first_value(row, "SHA256", "Source_SHA256")
        eligible = persistence_eligible(row, status)

        reasons = []

        if status != "CANONICAL":
            reasons.append(f"canonicalization_status={status or 'MISSING'}")
        if not eligible:
            reasons.append("persistence_eligible=NO")
        if not ticker:
            reasons.append("missing_canonical_ticker")
        if not period:
            reasons.append("missing_resolved_period")
        if not metric:
            reasons.append("missing_metric")
        if not value:
            reasons.append("missing_value")
        if not unit:
            reasons.append("missing_resolved_unit")
        if not sha:
            reasons.append("missing_source_sha256")

        key = persistence_key(row, ticker)

        prepared.append({
            "row": row,
            "reasons": reasons,
            "key": key,
            "ticker": ticker,
            "period": period,
            "metric": metric,
            "value": value,
            "unit": unit,
            "scale": scale,
            "sha": sha,
            "status": status,
        })

    eligible_keys = Counter(
        p["key"] for p in prepared if not p["reasons"]
    )

    output = []

    for p in prepared:
        reasons = list(p["reasons"])

        if not reasons and eligible_keys[p["key"]] > 1:
            reasons.append("duplicate_persistence_key")

        row = p["row"]
        output.append({
            "Persistence_Status": "READY" if not reasons else "BLOCKED",
            "Persistence_Reason": (
                "ALL_PERSISTENCE_DRY_RUN_CHECKS_PASS"
                if not reasons else ";".join(reasons)
            ),
            "Knowledge_Evidence_ID": (
                make_evidence_id(row, p["key"]) if not reasons else ""
            ),
            "Persistence_Key": p["key"],
            "Canonical_Observation_ID": first_value(row, "Canonical_Observation_ID"),
            "Canonical_Ticker": p["ticker"],
            "Resolved_Period": p["period"],
            "Metric": p["metric"],
            "Value_Parsed": p["value"],
            "Resolved_Unit": p["unit"],
            "Scale": p["scale"],
            "Source_SHA256": p["sha"],
            "Original_Identity": first_value(row, "Original_Identity"),
            "Lineage": first_value(row, "Lineage"),
            "Domain_Status": first_value(row, "Domain_Status"),
            "Temporal_Status": first_value(row, "Temporal_Status"),
            "Final_Promotion_Gate": first_value(row, "Final_Promotion_Gate"),
            "Canonicalization_Status": p["status"],
            "Persistence_Executed": "NO",
            "KnowledgeBridge_Executed": "NO",
            "Vault_Changed": "NO",
        })

    # Final uniqueness check on generated Knowledge Evidence IDs.
    ids = Counter(
        r["Knowledge_Evidence_ID"]
        for r in output if r["Persistence_Status"] == "READY"
    )

    for r in output:
        if r["Persistence_Status"] == "READY" and ids[r["Knowledge_Evidence_ID"]] > 1:
            r["Persistence_Status"] = "BLOCKED"
            r["Persistence_Reason"] = "duplicate_knowledge_evidence_id"

    fields = list(output[0].keys()) if output else []

    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output)

    ready = sum(r["Persistence_Status"] == "READY" for r in output)
    blocked = len(output) - ready
    duplicate_keys = sum(c > 1 for c in eligible_keys.values())
    duplicate_ids = sum(c > 1 for c in ids.values())

    tickers = Counter(
        r["Canonical_Ticker"] for r in output
        if r["Persistence_Status"] == "READY"
    )
    lineages = Counter(
        r["Lineage"] for r in output
        if r["Persistence_Status"] == "READY"
    )

    global_status = (
        "READY_FOR_PERSISTENCE_CONTRACT_REVIEW"
        if blocked == 0
        else "BLOCKED_PENDING_ADAPTER_REVIEW"
    )

    md = f"""# 0695.7 Persistence Adapter R2

Schema-compatible, read-only persistence adapter dry-run.

## Input

- `{INPUT_CSV}`
- Canonical observations: {len(rows)}

## Result

- READY: {ready}
- BLOCKED: {blocked}
- Duplicate persistence keys: {duplicate_keys}
- Duplicate Knowledge Evidence IDs: {duplicate_ids}
- Global status: `{global_status}`

## Normalization applied

- Canonical ticker recovered from the terminal ticker of `Lineage` when the R3 field is absent.
- Value recovered from `Value_Parsed`, `Value`, `Resolved_Value`, `Selected_Value`, or `ResolvedValue`.
- When `Persistence_Eligible` is absent, eligibility is derived from `Canonicalization_Status=CANONICAL`.
- Source SHA-256 remains provenance.
- Semantic persistence key remains ticker + resolved period + metric + unit + scale.

## Canonical tickers

"""
    for ticker, count in tickers.most_common():
        md += f"- {ticker}: {count}\n"

    md += "\n## Lineage\n\n"
    for lineage, count in lineages.most_common():
        md += f"- {lineage or 'MISSING'}: {count}\n"

    md += """
## Safety

- Persistence executed: NO
- KnowledgeBridge executed: NO
- Vault changed: NO
- Vault write authorization: NOT GRANTED
"""

    OUTPUT_MD.write_text(md, encoding="utf-8")

    print(f"Input canonicalization rows : {len(rows)}")
    print(f"READY                       : {ready}")
    print(f"BLOCKED                     : {blocked}")
    print(f"Duplicate persistence keys  : {duplicate_keys}")
    print(f"Duplicate Knowledge IDs     : {duplicate_ids}")
    print(f"Global status               : {global_status}")
    print(f"CSV                         : {OUTPUT_CSV}")
    print(f"MD                          : {OUTPUT_MD}")
    print()
    print("Persistence executed        : NO")
    print("KnowledgeBridge executed    : NO")
    print("Vault changed               : NO")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
