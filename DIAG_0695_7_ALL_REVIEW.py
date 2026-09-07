from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

ROOT = Path.cwd()
REPORTS = ROOT / "reports"
PATH = REPORTS / "PCIP11_0695_7_DOMAIN_ASSESSMENT.csv"

if not PATH.exists():
    raise SystemExit(f"Missing: {PATH}")

with PATH.open("r", encoding="utf-8-sig", newline="") as fh:
    rows = list(csv.DictReader(fh))

print("0695.7 DIAGNOSTIC - WHY ALL REVIEW")
print("=" * 72)
print(f"Rows: {len(rows)}")
print(f"Columns: {len(rows[0]) if rows else 0}")

reason_counter = Counter()
status_counter = Counter()
unit_counter = Counter()
period_counter = Counter()
confidence_buckets = Counter()
lineage_counter = Counter()

for row in rows:
    status_counter[row.get("Promotion_Status", "")] += 1
    reason_counter[row.get("Promotion_Reasons", "")] += 1
    unit_counter[row.get("Unit_Status", "")] += 1
    period_counter[row.get("Period_Status", "")] += 1
    lineage_counter[row.get("Lineage_Status", "")] += 1

    try:
        c = float(row.get("Confidence", "0") or 0)
    except ValueError:
        c = 0
    if c >= 0.90:
        bucket = ">=0.90"
    elif c >= 0.80:
        bucket = "0.80-0.899"
    elif c >= 0.50:
        bucket = "0.50-0.799"
    elif c > 0:
        bucket = "0.01-0.499"
    else:
        bucket = "0"
    confidence_buckets[bucket] += 1

print("\nSTATUS")
for k, v in status_counter.most_common():
    print(f"  {k or '<blank>'}: {v}")

print("\nREASONS")
for k, v in reason_counter.most_common(20):
    print(f"  {v}: {k or '<blank>'}")

print("\nUNIT_STATUS")
for k, v in unit_counter.most_common():
    print(f"  {k or '<blank>'}: {v}")

print("\nPERIOD_STATUS")
for k, v in period_counter.most_common():
    print(f"  {k or '<blank>'}: {v}")

print("\nCONFIDENCE")
for k, v in confidence_buckets.items():
    print(f"  {k}: {v}")

print("\nLINEAGE")
for k, v in lineage_counter.most_common():
    print(f"  {k or '<blank>'}: {v}")

print("\nFIRST 10 ROWS")
for row in rows[:10]:
    print("-" * 72)
    for key in (
        "Row", "Evidence_ID", "Original_Ticker", "Canonical_Ticker",
        "Lineage_Status", "Source_Role", "Metric_Name", "Value", "Unit",
        "Scale", "Period", "Period_Status", "Unit_Status",
        "Confidence", "Promotion_Status", "Promotion_Reasons"
    ):
        print(f"{key}: {row.get(key, '')}")

print("\nDIAGNOSTIC COMPLETED")
