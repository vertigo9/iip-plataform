#!/usr/bin/env python3

"""
IIP HISTORICAL BATCH DISCOVERY R1

Read-only discovery of historical evidence/canonicalization datasets.

Purpose:
- Discover historical CSV datasets under reports/.
- Identify candidate evidence/canonicalization files.
- Count rows.
- Detect ticker, period, metric and identity fields when available.
- Detect already-persisted Knowledge_Evidence_IDs when available.
- Never modify the Vault.
- Never execute persistence.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "reports"

OUTPUT_CSV = REPORTS / "IIP_HISTORICAL_BATCH_DISCOVERY_R1.csv"
OUTPUT_MD = REPORTS / "IIP_HISTORICAL_BATCH_DISCOVERY_R1.md"


DISCOVERY_PATTERNS = (
    "EVIDENCE",
    "CANONICALIZATION",
    "HISTORICAL",
    "STRUCTURED_EVIDENCE",
    "METRIC_EVIDENCE",
    "EVIDENCE_VALIDATION",
)


def norm(value: str | None) -> str:
    return (value or "").strip()


def first_value(row: dict[str, str], *names: str) -> str:
    for name in names:
        value = norm(row.get(name))
        if value:
            return value
    return ""


def is_candidate(filename: str) -> bool:
    upper = filename.upper()

    if not upper.endswith(".CSV"):
        return False

    return any(pattern in upper for pattern in DISCOVERY_PATTERNS)


def classify_file(path: Path) -> str:
    name = path.name.upper()

    if "CANONICALIZATION" in name:
        return "CANONICALIZATION"

    if "STRUCTURED_EVIDENCE" in name:
        return "STRUCTURED_EVIDENCE"

    if "METRIC_EVIDENCE" in name:
        return "METRIC_EVIDENCE"

    if "EVIDENCE_VALIDATION" in name:
        return "EVIDENCE_VALIDATION"

    if "EVIDENCE" in name:
        return "EVIDENCE"

    if "HISTORICAL" in name:
        return "HISTORICAL"

    return "OTHER"


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or [])

    return rows, fields


def unique_values(
    rows: list[dict[str, str]],
    *field_names: str,
) -> list[str]:
    values = set()

    for row in rows:
        value = first_value(row, *field_names)
        if value:
            values.add(value)

    return sorted(values)


def detect_column(fields: list[str], patterns: tuple[str, ...]) -> str:
    normalized = {field.upper(): field for field in fields}

    for pattern in patterns:
        for upper, original in normalized.items():
            if pattern in upper:
                return original

    return ""


def main() -> int:
    print("=" * 90)
    print("IIP HISTORICAL BATCH DISCOVERY R1")
    print("=" * 90)

    if not REPORTS.exists():
        print(f"ERROR: reports directory not found: {REPORTS}")
        return 2

    files = sorted(path for path in REPORTS.glob("*.csv") if is_candidate(path.name))

    results = []

    total_rows = 0
    readable_files = 0
    unreadable_files = 0

    global_tickers = Counter()
    global_metrics = Counter()
    global_periods = Counter()

    for path in files:
        try:
            rows, fields = read_csv(path)
            readable = True
            error = ""
            readable_files += 1
        except Exception as exc:
            rows = []
            fields = []
            readable = False
            error = f"{type(exc).__name__}: {exc}"
            unreadable_files += 1

        ticker_field = detect_column(
            fields,
            (
                "CANONICAL_TICKER",
                "TICKER",
                "ORIGINAL_TICKER",
                "ORIGINAL_IDENTITY",
            ),
        )

        metric_field = detect_column(
            fields,
            (
                "METRIC",
                "METRIC_NAME",
            ),
        )

        period_field = detect_column(
            fields,
            (
                "RESOLVED_PERIOD",
                "PERIOD",
            ),
        )

        metric_id_field = detect_column(
            fields,
            ("METRIC_ID",),
        )

        knowledge_id_field = detect_column(
            fields,
            (
                "KNOWLEDGE_EVIDENCE_ID",
                "KNOWLEDGE_ID",
            ),
        )

        status_field = detect_column(
            fields,
            (
                "PERSISTENCE_STATUS",
                "CANONICALIZATION_STATUS",
                "STATUS",
            ),
        )

        tickers = unique_values(
            rows,
            *(
                filter(
                    None,
                    (
                        ticker_field,
                        "Canonical_Ticker",
                        "Ticker",
                        "Original_Ticker",
                    ),
                )
            ),
        )

        metrics = unique_values(
            rows,
            *(
                filter(
                    None,
                    (
                        metric_field,
                        "Metric",
                        "Metric_Name",
                    ),
                )
            ),
        )

        periods = unique_values(
            rows,
            *(
                filter(
                    None,
                    (
                        period_field,
                        "Resolved_Period",
                        "Period",
                    ),
                )
            ),
        )

        metric_ids = unique_values(
            rows,
            *(
                filter(
                    None,
                    (
                        metric_id_field,
                        "Metric_ID",
                    ),
                )
            ),
        )

        knowledge_ids = unique_values(
            rows,
            *(
                filter(
                    None,
                    (
                        knowledge_id_field,
                        "Knowledge_Evidence_ID",
                        "Knowledge_ID",
                    ),
                )
            ),
        )

        status_counts = Counter()

        if status_field:
            for row in rows:
                status = first_value(row, status_field)
                if status:
                    status_counts[status] += 1

        total_rows += len(rows)

        global_tickers.update(tickers)
        global_metrics.update(metrics)
        global_periods.update(periods)

        results.append(
            {
                "File": path.name,
                "Path": str(path),
                "File_Type": classify_file(path),
                "Readable": "YES" if readable else "NO",
                "Rows": len(rows),
                "Columns": len(fields),
                "Ticker_Field": ticker_field,
                "Metric_Field": metric_field,
                "Period_Field": period_field,
                "Metric_ID_Field": metric_id_field,
                "Knowledge_ID_Field": knowledge_id_field,
                "Status_Field": status_field,
                "Unique_Tickers": len(tickers),
                "Unique_Metrics": len(metrics),
                "Unique_Periods": len(periods),
                "Unique_Metric_IDs": len(metric_ids),
                "Unique_Knowledge_IDs": len(knowledge_ids),
                "Ticker_Sample": ";".join(tickers[:10]),
                "Metric_Sample": ";".join(metrics[:10]),
                "Period_Sample": ";".join(periods[:10]),
                "Status_Summary": ";".join(
                    f"{key}={value}" for key, value in sorted(status_counts.items())
                ),
                "Error": error,
            }
        )

    fields_out = [
        "File",
        "Path",
        "File_Type",
        "Readable",
        "Rows",
        "Columns",
        "Ticker_Field",
        "Metric_Field",
        "Period_Field",
        "Metric_ID_Field",
        "Knowledge_ID_Field",
        "Status_Field",
        "Unique_Tickers",
        "Unique_Metrics",
        "Unique_Periods",
        "Unique_Metric_IDs",
        "Unique_Knowledge_IDs",
        "Ticker_Sample",
        "Metric_Sample",
        "Period_Sample",
        "Status_Summary",
        "Error",
    ]

    with OUTPUT_CSV.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields_out,
        )
        writer.writeheader()
        writer.writerows(results)

    canonicalization_files = sum(
        1 for result in results if result["File_Type"] == "CANONICALIZATION"
    )

    evidence_files = sum(
        1
        for result in results
        if result["File_Type"]
        in {
            "EVIDENCE",
            "STRUCTURED_EVIDENCE",
            "METRIC_EVIDENCE",
            "EVIDENCE_VALIDATION",
        }
    )

    md = f"""# IIP Historical Batch Discovery R1

## Mode

READ-ONLY

## Safety

- Vault modified: NO
- Persistence executed: NO
- KnowledgeBridge executed: NO
- Repository writes: NO

## Discovery

- Reports directory: `{REPORTS}`
- Candidate CSV files: {len(files)}
- Readable files: {readable_files}
- Unreadable files: {unreadable_files}
- Total rows discovered: {total_rows}
- Canonicalization files: {canonicalization_files}
- Evidence-related files: {evidence_files}

## Global dimensions

### Tickers

"""

    for ticker, count in global_tickers.most_common(50):
        md += f"- {ticker}: {count}\n"

    md += "\n### Metrics\n\n"

    for metric, count in global_metrics.most_common(50):
        md += f"- {metric}: {count}\n"

    md += "\n### Periods\n\n"

    for period, count in global_periods.most_common(50):
        md += f"- {period}: {count}\n"

    md += "\n## Files\n\n"

    for result in results:
        md += (
            f"### `{result['File']}`\n\n"
            f"- Type: `{result['File_Type']}`\n"
            f"- Readable: `{result['Readable']}`\n"
            f"- Rows: {result['Rows']}\n"
            f"- Columns: {result['Columns']}\n"
            f"- Tickers: {result['Unique_Tickers']}\n"
            f"- Metrics: {result['Unique_Metrics']}\n"
            f"- Periods: {result['Unique_Periods']}\n"
            f"- Metric IDs: {result['Unique_Metric_IDs']}\n"
            f"- Knowledge IDs: {result['Unique_Knowledge_IDs']}\n"
        )

        if result["Ticker_Sample"]:
            md += f"- Ticker sample: `{result['Ticker_Sample']}`\n"

        if result["Metric_Sample"]:
            md += f"- Metric sample: `{result['Metric_Sample']}`\n"

        if result["Period_Sample"]:
            md += f"- Period sample: `{result['Period_Sample']}`\n"

        if result["Status_Summary"]:
            md += f"- Status: `{result['Status_Summary']}`\n"

        if result["Error"]:
            md += f"- Error: `{result['Error']}`\n"

        md += "\n"

    md += """## Next gate

This discovery report is informational only.

No dataset is authorized for persistence by this script.

The next step is to select the historical datasets that satisfy the
IIP persistence contract and process them through the existing
idempotent pipeline.
"""

    OUTPUT_MD.write_text(md, encoding="utf-8")

    print(f"Candidate CSV files          : {len(files)}")
    print(f"Readable files               : {readable_files}")
    print(f"Unreadable files             : {unreadable_files}")
    print(f"Total rows discovered        : {total_rows}")
    print(f"Canonicalization files       : {canonicalization_files}")
    print(f"Evidence-related files       : {evidence_files}")
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
