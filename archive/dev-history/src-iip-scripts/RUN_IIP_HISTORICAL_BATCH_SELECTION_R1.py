from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "reports"

DISCOVERY_CSV = REPORTS / "IIP_HISTORICAL_BATCH_DISCOVERY_R1.csv"
OUTPUT_CSV = REPORTS / "IIP_HISTORICAL_BATCH_SELECTION_R1.csv"
OUTPUT_MD = REPORTS / "IIP_HISTORICAL_BATCH_SELECTION_R1.md"


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
    name = (row.get("file_name") or row.get("filename") or "").strip()
    upper = name.upper()

    try:
        rows = int(row.get("rows") or row.get("row_count") or 0)
    except ValueError:
        rows = 0

    # Controle / artefatos de execução
    if any(pattern in upper for pattern in CONTROL_PATTERNS):
        return (
            "CONTROL_ARTIFACT",
            "arquivo de controle, auditoria ou pipeline; não entra na seleção histórica",
            0,
        )

    # Canonicalização final conhecida
    if upper == FINAL_CANONICALIZATION.upper():
        return (
            "READY_CANDIDATE",
            "canonicalização final R4; fonte prioritária para persistência histórica",
            100,
        )

    # Canonicalizações anteriores
    if "CANONICALIZATION" in upper:
        return (
            "SUPERSEDED",
            "canonicalização anterior à R4; mantida apenas como histórico técnico",
            20,
        )

    # Evidências estruturadas
    if (
        "STRUCTURED_EVIDENCE" in upper
        or "METRIC_EVIDENCE" in upper
        or "EVIDENCE_VALIDATION" in upper
    ):
        return (
            "REVIEW_REQUIRED",
            "dataset de evidência histórica; precisa passar pela canonicalização antes da persistência",
            60,
        )

    if "EVIDENCE" in upper:
        return (
            "REVIEW_REQUIRED",
            "dataset relacionado a evidências; requer validação de identidade antes da persistência",
            50,
        )

    # Outros CSVs históricos
    if rows > 0:
        return (
            "REVIEW_REQUIRED",
            "dataset histórico legível, mas sem evidência suficiente para seleção automática",
            30,
        )

    return (
        "REVIEW_REQUIRED",
        "arquivo sem linhas úteis identificadas",
        0,
    )


def main() -> int:
    print("=" * 90)
    print("IIP HISTORICAL BATCH SELECTION R1")
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
        filename = (
            row.get("file_name") or row.get("filename") or row.get("name") or ""
        ).strip()

        classification, reason, priority = classify_file(row)

        selected.append(
            {
                "selection_row": index,
                "file_name": filename,
                "classification": classification,
                "priority": priority,
                "reason": reason,
                "rows": row.get("rows") or row.get("row_count") or "",
                "ticker": row.get("ticker", ""),
                "metric_name": row.get("metric_name", ""),
                "period": row.get("period", ""),
                "metric_id": row.get("metric_id") or row.get("Metric_ID") or "",
                "knowledge_evidence_id": row.get("knowledge_evidence_id")
                or row.get("Knowledge_Evidence_ID")
                or row.get("knowledge_id")
                or row.get("Knowledge_ID")
                or "",
                "status": row.get("status", ""),
                "source_path": row.get("source_path") or row.get("path") or "",
            }
        )

    selected.sort(
        key=lambda row: (
            -int(row["priority"]),
            row["classification"],
            row["file_name"],
        )
    )

    fieldnames = [
        "selection_row",
        "file_name",
        "classification",
        "priority",
        "reason",
        "rows",
        "ticker",
        "metric_name",
        "period",
        "metric_id",
        "knowledge_evidence_id",
        "status",
        "source_path",
    ]

    with OUTPUT_CSV.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(selected)

    counts = Counter(row["classification"] for row in selected)

    ready = counts.get("READY_CANDIDATE", 0)
    review = counts.get("REVIEW_REQUIRED", 0)
    superseded = counts.get("SUPERSEDED", 0)
    control = counts.get("CONTROL_ARTIFACT", 0)

    md = f"""# IIP Historical Batch Selection R1

## Safety

- Selection mode: READ-ONLY
- Vault modified: NO
- Persistence executed: NO
- KnowledgeBridge executed: NO
- Repository writes: NO

## Discovery input

- Input: `{DISCOVERY_CSV}`
- Candidate rows: {len(rows)}

## Selection result

- READY_CANDIDATE: {ready}
- REVIEW_REQUIRED: {review}
- SUPERSEDED: {superseded}
- CONTROL_ARTIFACT: {control}

## Selection rule

The selection stage does not persist evidence.

The final known canonicalization
`{FINAL_CANONICALIZATION}` is prioritized as the historical persistence candidate.

Previous canonicalization versions are classified as SUPERSEDED.

Control, pipeline, audit, bridge, contract and execution artifacts are excluded
from historical persistence.

Evidence datasets that have not passed the final canonicalization are classified
as REVIEW_REQUIRED.

## Priority

- 100 = final canonicalization candidate
- 60/50 = historical evidence requiring validation
- 30 = generic historical dataset requiring review
- 20 = superseded canonicalization
- 0 = control artifact

## Next gate

Only rows classified as `READY_CANDIDATE` may proceed automatically.

`REVIEW_REQUIRED` rows must not be persisted automatically.

This report is read-only and does not modify the Obsidian Vault.
"""

    OUTPUT_MD.write_text(md, encoding="utf-8")

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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
