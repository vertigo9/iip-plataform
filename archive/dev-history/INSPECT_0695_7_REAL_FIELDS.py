from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

ROOT = Path.cwd()
INPUT = ROOT / "reports" / "PCIP11_0695_7_PROMOTION_GATE.csv"


FIELDS = [
    "Row",
    "Historical_ID",
    "SHA256",
    "FileName",
    "Original_Identity",
    "Lineage",
    "Document_Role",
    "Metric",
    "Value",
    "Original_Unit",
    "Resolved_Unit",
    "Scale",
    "Scale_State",
    "Scale_Confidence",
    "Period",
    "Plausibility",
    "Resolution_Status",
    "Promotion_Action",
    "Domain_Status",
    "Domain_Reason",
]


def main() -> None:
    if not INPUT.exists():
        raise SystemExit(f"Arquivo não encontrado: {INPUT}")

    with INPUT.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    print("0695.7 REAL FIELD INSPECTION")
    print("=" * 80)
    print(f"Total rows : {len(rows)}")
    print(f"PASS       : {sum(r.get('Promotion_Gate') == 'PASS' for r in rows)}")
    print(f"BLOCKED    : {sum(r.get('Promotion_Gate') == 'BLOCKED' for r in rows)}")
    print()

    print("DISTRIBUTIONS")
    print("-" * 80)

    for field in [
        "Original_Identity",
        "Lineage",
        "Document_Role",
        "Metric",
        "Original_Unit",
        "Resolved_Unit",
        "Scale",
        "Scale_State",
        "Scale_Confidence",
        "Period",
        "Plausibility",
        "Resolution_Status",
        "Promotion_Action",
        "Domain_Status",
    ]:
        counts = Counter(r.get(field, "") for r in rows)
        print(f"\n{field}:")
        for value, count in counts.most_common():
            print(f"  {repr(value)} : {count}")

    print()
    print("MISSING REQUIRED/PROVENANCE FIELDS")
    print("-" * 80)

    for field in [
        "Historical_ID",
        "SHA256",
        "FileName",
        "Original_Identity",
        "Lineage",
        "Metric",
        "Value",
        "Original_Unit",
        "Resolved_Unit",
        "Scale",
        "Period",
    ]:
        missing = [
            r.get("Row", "")
            for r in rows
            if not str(r.get(field, "")).strip()
        ]
        print(f"{field}: {len(missing)} missing")
        if missing:
            print(f"  Rows: {', '.join(missing)}")

    print()
    print("PASS RECORDS")
    print("-" * 80)

    for r in rows:
        if r.get("Promotion_Gate") != "PASS":
            continue

        print(
            f"Row={r.get('Row')} | "
            f"Identity={r.get('Original_Identity')} | "
            f"Lineage={r.get('Lineage')} | "
            f"Metric={r.get('Metric')} | "
            f"Value={r.get('Value')} | "
            f"Original_Unit={r.get('Original_Unit')} | "
            f"Resolved_Unit={r.get('Resolved_Unit')} | "
            f"Scale={r.get('Scale')} | "
            f"Period={r.get('Period')} | "
            f"SHA256={r.get('SHA256')}"
        )

    print()
    print("PERIOD + EVIDENCE CONSISTENCY CHECK")
    print("-" * 80)

    periods = Counter(
        r.get("Period", "")
        for r in rows
        if r.get("Promotion_Gate") == "PASS"
    )

    print("PASS periods:")
    for period, count in periods.most_common():
        print(f"  {period}: {count}")

    print()
    print("Inspection complete.")
    print("Vault changed: NO")
    print("Metric promoted: NO")


if __name__ == "__main__":
    main()