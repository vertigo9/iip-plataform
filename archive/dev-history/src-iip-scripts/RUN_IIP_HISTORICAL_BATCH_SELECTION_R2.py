from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "reports"

DISCOVERY_CSV = REPORTS / "IIP_HISTORICAL_BATCH_DISCOVERY_R1.csv"
OUTPUT_CSV = REPORTS / "IIP_HISTORICAL_BATCH_SELECTION_R2.csv"
OUTPUT_MD = REPORTS / "IIP_HISTORICAL_BATCH_SELECTION_R2.md"

FINAL_CANONICALIZATION = "PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R4.csv"


CONTROL_PATTERNS = (
    "PIPELINE",
    "DISCOVERY",
    "SELECTION",
    "PREFLIGHT",
    "AUDIT",
    "CONTRACT",
    "BRIDGE",
    "RELEASE",
    "POST_AUDIT",
    "EXECUTION",
)


def classify_file(row: dict) -> tuple[str, str, int]:

    name = (row.get("File") or "").strip()
    upper = name.upper()

    try:
        rows = int(row.get("Rows") or 0)
    except (ValueError, TypeError):
        rows = 0

    # ==========================================================
    # 1. FINAL CANONICALIZATION
    # ==========================================================

    if upper == FINAL_CANONICALIZATION.upper():
        return (
            "READY_CANDIDATE",
            "canonicalização final R4; fonte prioritária para persistência histórica",
            100,
        )

    # ==========================================================
    # 2. CONTROL / PIPELINE ARTIFACTS
    # ==========================================================

    if any(pattern in upper for pattern in CONTROL_PATTERNS):
        return (
            "CONTROL_ARTIFACT",
            "artefato de controle, auditoria ou pipeline; excluído da seleção histórica",
            0,
        )

    # ==========================================================
    # 3. PREVIOUS CANONICALIZATION
    # ==========================================================

    if "CANONICALIZATION" in upper:
        return (
            "SUPERSEDED",
            "canonicalização anterior à R4; mantida apenas para rastreabilidade histórica",
            20,
        )

    # ==========================================================
    # 4. STRUCTURED / VALIDATED EVIDENCE
    # ==========================================================

    if (
        "STRUCTURED_EVIDENCE" in upper
        or "METRIC_EVIDENCE" in upper
        or "EVIDENCE_VALIDATION" in upper
    ):
        return (
            "REVIEW_REQUIRED",
            "dataset histórico de evidência; requer canonicalização antes da persistência",
            60,
        )

    # ==========================================================
    # 5. OTHER EVIDENCE DATASETS
    # ==========================================================

    if "EVIDENCE" in upper:
        return (
            "REVIEW_REQUIRED",
            "dataset relacionado a evidências; requer validação de identidade",
            50,
        )

    # ==========================================================
    # 6. GENERIC HISTORICAL DATASET
    # ==========================================================

    if rows > 0:
        return (
            "REVIEW_REQUIRED",
            "dataset histórico legível, mas sem autorização para persistência automática",
            30,
        )

    return (
        "REVIEW_REQUIRED",
        "arquivo sem linhas úteis identificadas",
        0,
    )


def main() -> int:

    print("=" * 90)
    print("IIP HISTORICAL BATCH SELECTION R2")
    print("=" * 90)

    if not REPORTS.exists():
        print(f"ERROR: reports directory not found: {REPORTS}")
        return 1

    if not DISCOVERY_CSV.exists():
        print(f"ERROR: discovery input not found: {DISCOVERY_CSV}")
        return 1

    with DISCOVERY_CSV.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    selected = []

    for index, row in enumerate(rows, start=1):
        filename = (row.get("File") or "").strip()

        classification, reason, priority = classify_file(row)

        selected.append(
            {
                "selection_row": index,
                "file": filename,
                "path": row.get("Path", ""),
                "file_type": row.get("File_Type", ""),
                "readable": row.get("Readable", ""),
                "rows": row.get("Rows", ""),
                "columns": row.get("Columns", ""),
                "ticker_field": row.get("Ticker_Field", ""),
                "metric_field": row.get("Metric_Field", ""),
                "period_field": row.get("Period_Field", ""),
                "metric_id_field": row.get("Metric_ID_Field", ""),
                "knowledge_id_field": row.get("Knowledge_ID_Field", ""),
                "status_field": row.get("Status_Field", ""),
                "classification": classification,
                "priority": priority,
                "reason": reason,
            }
        )

    # Final candidate first, then review, superseded and control.
    selected.sort(
        key=lambda row: (
            -int(row["priority"]),
            row["classification"],
            row["file"],
        )
    )

    fieldnames = [
        "selection_row",
        "file",
        "path",
        "file_type",
        "readable",
        "rows",
        "columns",
        "ticker_field",
        "metric_field",
        "period_field",
        "metric_id_field",
        "knowledge_id_field",
        "status_field",
        "classification",
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
        writer.writerows(selected)

    counts = Counter(row["classification"] for row in selected)

    ready = counts.get("READY_CANDIDATE", 0)
    review = counts.get("REVIEW_REQUIRED", 0)
    superseded = counts.get("SUPERSEDED", 0)
    control = counts.get("CONTROL_ARTIFACT", 0)

    md = f"""# IIP Historical Batch Selection R2

## Safety

- Selection mode: READ-ONLY
- Vault modified: NO
- Persistence executed: NO
- KnowledgeBridge executed: NO
- Repository writes: NO

## Discovery source

- Input: `{DISCOVERY_CSV}`
- Candidate files: {len(rows)}

## Result

- READY_CANDIDATE: {ready}
- REVIEW_REQUIRED: {review}
- SUPERSEDED: {superseded}
- CONTROL_ARTIFACT: {control}

## Priority rule

### 100 — READY_CANDIDATE

`{FINAL_CANONICALIZATION}`

This is the final canonicalization already validated through the
0695.7 persistence chain.

### 60/50 — REVIEW_REQUIRED

Historical evidence datasets that require canonicalization or identity
validation before persistence.

### 20 — SUPERSEDED

Previous canonicalization versions.

### 0 — CONTROL_ARTIFACT

Discovery, pipeline, audit, execution, contract, bridge and other
technical control artifacts.

## Safety invariant

Selection does not modify the Vault.

Selection does not execute persistence.

Selection does not execute KnowledgeBridge.

Selection does not write repository evidence.

Only `READY_CANDIDATE` may proceed to an explicit historical persistence gate.

## Expected canonical candidate

- File: `{FINAL_CANONICALIZATION}`
- Expected classification: `READY_CANDIDATE`
- Expected priority: `100`

This report is read-only.
"""

    OUTPUT_MD.write_text(
        md,
        encoding="utf-8",
    )

    print(f"Candidate files              : {len(rows)}")
    print(f"READY_CANDIDATE              : {ready}")
    print(f"REVIEW_REQUIRED              : {review}")
    print(f"SUPERSEDED                   : {superseded}")
    print(f"CONTROL_ARTIFACT             : {control}")
    print(f"CSV                          : {OUTPUT_CSV}")
    print(f"MD                           : {OUTPUT_MD}")
    print()
    print("Vault modified               : NO")
    print("Persistence executed         : NO")
    print("KnowledgeBridge executed     : NO")
    print("Repository writes            : NO")

    if ready != 1:
        print()
        print("WARNING: expected exactly 1 READY_CANDIDATE")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
