from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "reports"

INPUT_CSV = REPORTS / "IIP_HISTORICAL_BATCH_SELECTION_R2.csv"

OUTPUT_CSV = REPORTS / "IIP_HISTORICAL_BATCH_REVIEW_R1.csv"
OUTPUT_MD = REPORTS / "IIP_HISTORICAL_BATCH_REVIEW_R1.md"


def read_csv(path: Path):
    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        return list(csv.DictReader(handle))


def safe_int(value):
    try:
        return int(value or 0)
    except (ValueError, TypeError):
        return 0


def review_row(row: dict) -> dict:

    filename = (row.get("file") or "").strip()
    classification = (row.get("classification") or "").strip()

    rows = safe_int(row.get("rows"))
    columns = safe_int(row.get("columns"))

    ticker_field = (row.get("ticker_field") or "").strip()
    metric_field = (row.get("metric_field") or "").strip()
    period_field = (row.get("period_field") or "").strip()
    metric_id_field = (row.get("metric_id_field") or "").strip()
    knowledge_id_field = (row.get("knowledge_id_field") or "").strip()
    status_field = (row.get("status_field") or "").strip()
    identity_fields = bool(ticker_field) and bool(metric_field) and bool(period_field)

    canonical_identity = (
        bool(ticker_field)
        and bool(metric_field)
        and bool(period_field)
        and bool(metric_id_field)
    )

    knowledge_identity = canonical_identity and bool(knowledge_id_field)

    identity_count = sum(
        1
        for field in (
            ticker_field,
            metric_field,
            period_field,
            metric_id_field,
            knowledge_id_field,
        )
        if field
    )

    if classification != "REVIEW_REQUIRED":
        decision = "NOT_REVIEWED"
        reason = "arquivo não pertence ao conjunto REVIEW_REQUIRED"
        priority = 0

    elif not rows:
        decision = "BLOCKED"
        reason = "dataset sem linhas"
        priority = 0

    elif identity_count >= 5:
        decision = "CANONICALIZATION_READY"
        reason = (
            "possui identidade completa: Ticker, Metric, Period, "
            "Metric_ID e Knowledge_ID"
        )
        priority = 90

    elif identity_count >= 4:
        decision = "CANONICALIZATION_CANDIDATE"
        reason = "possui identidade quase completa; requer resolução do campo ausente"
        priority = 70

    elif identity_fields:
        decision = "CANONICALIZATION_REQUIRED"
        reason = (
            "possui identidade básica Ticker/Metric/Period, "
            "mas ainda não possui identidade canônica completa"
        )
        priority = 60

    else:
        decision = "BLOCKED"
        reason = (
            "não possui os campos mínimos Ticker/Metric/Period "
            "para canonicalização automática"
        )
        priority = 0

    return {
        "file": filename,
        "classification": classification,
        "rows": rows,
        "columns": columns,
        "ticker_field": ticker_field,
        "metric_field": metric_field,
        "period_field": period_field,
        "metric_id_field": metric_id_field,
        "knowledge_id_field": knowledge_id_field,
        "status_field": status_field,
        "identity_field_count": identity_count,
        "has_basic_identity": "YES" if identity_fields else "NO",
        "has_metric_identity": "YES" if canonical_identity else "NO",
        "has_knowledge_identity": "YES" if knowledge_identity else "NO",
        "decision": decision,
        "priority": priority,
        "reason": reason,
    }


def main() -> int:

    print("=" * 90)
    print("IIP HISTORICAL BATCH REVIEW R1")
    print("=" * 90)

    if not REPORTS.exists():
        print(f"ERROR: reports directory not found: {REPORTS}")
        return 1

    if not INPUT_CSV.exists():
        print(f"ERROR: selection input not found: {INPUT_CSV}")
        return 1

    rows = read_csv(INPUT_CSV)

    review_candidates = [
        row
        for row in rows
        if (row.get("classification") or "").strip() == "REVIEW_REQUIRED"
    ]

    results = [review_row(row) for row in review_candidates]

    results.sort(
        key=lambda row: (
            -int(row["priority"]),
            row["decision"],
            row["file"],
        )
    )

    fieldnames = [
        "file",
        "classification",
        "rows",
        "columns",
        "ticker_field",
        "metric_field",
        "period_field",
        "metric_id_field",
        "knowledge_id_field",
        "status_field",
        "identity_field_count",
        "has_basic_identity",
        "has_metric_identity",
        "has_knowledge_identity",
        "decision",
        "priority",
        "reason",
    ]

    with OUTPUT_CSV.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(results)

    counts = Counter(row["decision"] for row in results)

    ready = counts.get("CANONICALIZATION_READY", 0)
    candidate = counts.get("CANONICALIZATION_CANDIDATE", 0)
    required = counts.get("CANONICALIZATION_REQUIRED", 0)
    blocked = counts.get("BLOCKED", 0)

    md = f"""# IIP Historical Batch Review R1

## Safety

- Review mode: READ-ONLY
- Vault modified: NO
- Persistence executed: NO
- KnowledgeBridge executed: NO
- Repository writes: NO

## Input

- Selection input: `{INPUT_CSV}`
- REVIEW_REQUIRED candidates: {len(review_candidates)}

## Review result

- CANONICALIZATION_READY: {ready}
- CANONICALIZATION_CANDIDATE: {candidate}
- CANONICALIZATION_REQUIRED: {required}
- BLOCKED: {blocked}

## Identity model

The review evaluates the availability of:

1. Ticker
2. Metric
3. Period
4. Metric_ID
5. Knowledge_ID

The presence of Ticker + Metric + Period is considered the minimum
identity required to begin canonicalization.

Metric_ID and Knowledge_ID are not manually generated here.

They must continue to follow the IIP identity contract.

## Decision model

### CANONICALIZATION_READY

The dataset already exposes the complete identity fields.

### CANONICALIZATION_CANDIDATE

The dataset is structurally close to canonicalization but has one
or more missing identity fields.

### CANONICALIZATION_REQUIRED

The dataset has basic observation identity but still requires the
canonicalization stage.

### BLOCKED

The dataset does not expose enough identity information for safe
automatic canonicalization.

## Safety invariant

This stage performs no persistence.

It does not modify the Vault.

It does not execute KnowledgeBridge.

It does not write repository evidence.

The output is an analytical review only.
"""

    OUTPUT_MD.write_text(
        md,
        encoding="utf-8",
    )

    print(f"REVIEW_REQUIRED candidates : {len(review_candidates)}")
    print(f"CANONICALIZATION_READY     : {ready}")
    print(f"CANONICALIZATION_CANDIDATE : {candidate}")
    print(f"CANONICALIZATION_REQUIRED  : {required}")
    print(f"BLOCKED                    : {blocked}")
    print(f"CSV                        : {OUTPUT_CSV}")
    print(f"MD                         : {OUTPUT_MD}")
    print()
    print("Vault modified             : NO")
    print("Persistence executed       : NO")
    print("KnowledgeBridge executed   : NO")
    print("Repository writes          : NO")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
