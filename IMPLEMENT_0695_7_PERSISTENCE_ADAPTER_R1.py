#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
0695.7 PERSISTENCE ADAPTER R1

Generic, read-only persistence adapter dry-run.

Input:
    reports/PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R3.csv

Purpose:
    Transform canonical observations into a persistence-facing
    Knowledge Evidence contract without writing to the Obsidian Vault,
    KnowledgeBridge, or any external persistence layer.

Safety:
    - CSV/MD reports only
    - no Vault write
    - no KnowledgeBridge write
    - no source mutation
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

INPUT_CSV = REPORTS / "PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R3.csv"
OUTPUT_CSV = REPORTS / "PCIP11_0695_7_PERSISTENCE_ADAPTER_R1.csv"
OUTPUT_MD = REPORTS / "PCIP11_0695_7_PERSISTENCE_ADAPTER_R1.md"


def norm(value: str | None) -> str:
    return (value or "").strip()


def truthy(value: str | None) -> bool:
    return norm(value).upper() in {
        "YES", "TRUE", "1", "PASS", "CANONICAL"
    }


def safe_part(value: str) -> str:
    value = norm(value)
    value = re.sub(r"[^A-Za-z0-9_.:-]+", "_", value)
    return value[:160]


def persistence_key(row: dict) -> str:
    """
    Stable semantic persistence key.

    The source SHA is intentionally NOT the primary identity because
    persistence identity must remain semantic/document-period based.
    """
    ticker = norm(row.get("Canonical_Ticker") or row.get("Original_Ticker"))
    period = norm(row.get("Resolved_Period"))
    metric = norm(row.get("Metric"))
    unit = norm(row.get("Resolved_Unit") or row.get("Original_Unit"))
    scale = norm(row.get("Scale"))
    return "|".join([ticker, period, metric, unit, scale])


def evidence_id(row: dict, key: str) -> str:
    existing = norm(row.get("Canonical_Observation_ID"))
    if existing:
        return existing

    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    return f"canonical:{digest}"


def main() -> int:
    print("0695.7 PERSISTENCE ADAPTER R1")
    print("=" * 88)

    if not INPUT_CSV.exists():
        print(f"ERROR: input not found: {INPUT_CSV}")
        return 2

    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    eligible = []
    blocked = []

    for row in rows:
        status = norm(row.get("Canonicalization_Status")).upper()
        eligible_flag = norm(row.get("Persistence_Eligible")).upper()

        reasons = []

        if status != "CANONICAL":
            reasons.append(f"canonicalization_status={status or 'MISSING'}")

        if eligible_flag != "YES":
            reasons.append(f"persistence_eligible={eligible_flag or 'MISSING'}")

        ticker = norm(row.get("Canonical_Ticker") or row.get("Original_Ticker"))
        period = norm(row.get("Resolved_Period"))
        metric = norm(row.get("Metric"))
        unit = norm(row.get("Resolved_Unit") or row.get("Original_Unit"))
        scale = norm(row.get("Scale"))
        sha = norm(row.get("SHA256"))

        if not ticker:
            reasons.append("missing_canonical_ticker")
        if not period:
            reasons.append("missing_resolved_period")
        if not metric:
            reasons.append("missing_metric")
        if not unit:
            reasons.append("missing_resolved_unit")
        if not scale:
            reasons.append("missing_scale")
        if not sha:
            reasons.append("missing_source_sha256")

        key = persistence_key(row)

        if reasons:
            blocked.append((row, reasons, key))
        else:
            eligible.append((row, [], key))

    key_counts = Counter(key for _, _, key in eligible)

    output_rows = []

    for row, reasons, key in eligible:
        duplicate = key_counts[key] > 1
        if duplicate:
            reasons = ["duplicate_persistence_key"]

        status = "BLOCKED" if reasons else "READY"

        ticker = norm(row.get("Canonical_Ticker") or row.get("Original_Ticker"))
        period = norm(row.get("Resolved_Period"))
        metric = norm(row.get("Metric"))
        unit = norm(row.get("Resolved_Unit") or row.get("Original_Unit"))
        scale = norm(row.get("Scale"))
        value = norm(row.get("Value_Parsed"))
        sha = norm(row.get("SHA256"))

        output_rows.append({
            "Persistence_Status": status,
            "Persistence_Reason": ";".join(reasons) if reasons else "ALL_PERSISTENCE_DRY_RUN_CHECKS_PASS",
            "Knowledge_Evidence_ID": evidence_id(row, key),
            "Persistence_Key": key,
            "Canonical_Observation_ID": norm(row.get("Canonical_Observation_ID")),
            "Canonical_Ticker": ticker,
            "Resolved_Period": period,
            "Metric": metric,
            "Value_Parsed": value,
            "Resolved_Unit": unit,
            "Scale": scale,
            "Source_SHA256": sha,
            "Original_Identity": norm(row.get("Original_Identity")),
            "Lineage": norm(row.get("Lineage")),
            "Domain_Status": norm(row.get("Domain_Status")),
            "Temporal_Status": norm(row.get("Temporal_Status")),
            "Final_Promotion_Gate": norm(row.get("Final_Promotion_Gate")),
            "Canonicalization_Status": norm(row.get("Canonicalization_Status")),
            "Persistence_Executed": "NO",
            "KnowledgeBridge_Executed": "NO",
            "Vault_Changed": "NO",
        })

    # Rows blocked before eligibility/key validation.
    for row, reasons, key in blocked:
        output_rows.append({
            "Persistence_Status": "BLOCKED",
            "Persistence_Reason": ";".join(reasons),
            "Knowledge_Evidence_ID": "",
            "Persistence_Key": key,
            "Canonical_Observation_ID": norm(row.get("Canonical_Observation_ID")),
            "Canonical_Ticker": norm(row.get("Canonical_Ticker") or row.get("Original_Ticker")),
            "Resolved_Period": norm(row.get("Resolved_Period")),
            "Metric": norm(row.get("Metric")),
            "Value_Parsed": norm(row.get("Value_Parsed")),
            "Resolved_Unit": norm(row.get("Resolved_Unit") or row.get("Original_Unit")),
            "Scale": norm(row.get("Scale")),
            "Source_SHA256": norm(row.get("SHA256")),
            "Original_Identity": norm(row.get("Original_Identity")),
            "Lineage": norm(row.get("Lineage")),
            "Domain_Status": norm(row.get("Domain_Status")),
            "Temporal_Status": norm(row.get("Temporal_Status")),
            "Final_Promotion_Gate": norm(row.get("Final_Promotion_Gate")),
            "Canonicalization_Status": norm(row.get("Canonicalization_Status")),
            "Persistence_Executed": "NO",
            "KnowledgeBridge_Executed": "NO",
            "Vault_Changed": "NO",
        })

    # Detect duplicate Knowledge Evidence IDs among READY rows.
    ready_ids = [
        r["Knowledge_Evidence_ID"]
        for r in output_rows
        if r["Persistence_Status"] == "READY"
    ]
    id_counts = Counter(ready_ids)

    for r in output_rows:
        if (
            r["Persistence_Status"] == "READY"
            and id_counts[r["Knowledge_Evidence_ID"]] > 1
        ):
            r["Persistence_Status"] = "BLOCKED"
            r["Persistence_Reason"] = "duplicate_knowledge_evidence_id"

    fieldnames = [
        "Persistence_Status",
        "Persistence_Reason",
        "Knowledge_Evidence_ID",
        "Persistence_Key",
        "Canonical_Observation_ID",
        "Canonical_Ticker",
        "Resolved_Period",
        "Metric",
        "Value_Parsed",
        "Resolved_Unit",
        "Scale",
        "Source_SHA256",
        "Original_Identity",
        "Lineage",
        "Domain_Status",
        "Temporal_Status",
        "Final_Promotion_Gate",
        "Canonicalization_Status",
        "Persistence_Executed",
        "KnowledgeBridge_Executed",
        "Vault_Changed",
    ]

    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    ready = sum(r["Persistence_Status"] == "READY" for r in output_rows)
    blocked_count = len(output_rows) - ready
    duplicate_keys = sum(c > 1 for c in key_counts.values())
    duplicate_ids = sum(c > 1 for c in id_counts.values())

    tickers = Counter(
        r["Canonical_Ticker"]
        for r in output_rows
        if r["Persistence_Status"] == "READY"
    )
    lineages = Counter(
        r["Lineage"]
        for r in output_rows
        if r["Persistence_Status"] == "READY"
    )

    global_status = "READY_FOR_PERSISTENCE_CONTRACT_REVIEW" if blocked_count == 0 else "BLOCKED_PENDING_ADAPTER_REVIEW"

    md = f"""# 0695.7 Persistence Adapter R1

Generic, read-only persistence adapter dry-run.

## Input

- `{INPUT_CSV}`
- Source rows: {len(rows)}

## Result

- READY: {ready}
- BLOCKED: {blocked_count}
- Duplicate persistence keys: {duplicate_keys}
- Duplicate Knowledge Evidence IDs: {duplicate_ids}
- Global status: `{global_status}`

## Canonical tickers

"""

    for ticker, count in tickers.most_common():
        md += f"- {ticker}: {count}\n"

    md += "\n## Lineage statuses\n\n"
    for lineage, count in lineages.most_common():
        md += f"- {lineage or 'MISSING'}: {count}\n"

    md += """
## Persistence contract mapping

- Canonical Observation is the normalized source observation.
- Knowledge Evidence ID is the persistence-facing evidence identity.
- Persistence Key is semantic: ticker + resolved period + metric + unit + scale.
- Source SHA-256 remains provenance.
- Lineage remains explicit and is not collapsed into ticker identity.
- EvidenceChain is not persisted by this dry-run.
- KnowledgeBridge persistence is NOT executed.
- Vault write authorization is NOT granted.

## Safety

- Persistence executed: NO
- KnowledgeBridge executed: NO
- Vault changed: NO
"""

    OUTPUT_MD.write_text(md, encoding="utf-8")

    print(f"Input canonicalization rows : {len(rows)}")
    print(f"READY                       : {ready}")
    print(f"BLOCKED                     : {blocked_count}")
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
