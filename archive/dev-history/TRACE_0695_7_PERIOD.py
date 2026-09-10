from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path.cwd()
REPORTS = ROOT / "reports"

FILES = [
    REPORTS / "PCIP11_0695_7_DOMAIN_ASSESSMENT_R1.csv",
    REPORTS / "PCIP11_SEMANTIC_RESOLUTION_0695_6R4R4.csv",
    REPORTS / "PCIP11_METRIC_PROMOTION_CANDIDATES_0695_6R2.csv",
]


def load(path: Path):
    if not path.exists():
        print(f"\nMISSING: {path}")
        return []

    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    print("0695.7 PERIOD TRACE")
    print("=" * 80)

    for path in FILES:
        print()
        print(f"FILE: {path.name}")
        print("-" * 80)

        rows = load(path)

        if not rows:
            continue

        print(f"Rows: {len(rows)}")

        period_fields = [
            field
            for field in rows[0].keys()
            if "period" in field.lower()
            or "date" in field.lower()
            or "year" in field.lower()
        ]

        print("Temporal fields:")
        for field in period_fields:
            values = sorted(
                {
                    str(row.get(field, "")).strip()
                    for row in rows
                    if str(row.get(field, "")).strip()
                }
            )

            print(f"  {field}: {len(values)} distinct")
            for value in values[:30]:
                print(f"    {value}")

        print()
        print("First 5 rows - temporal fields:")
        for row in rows[:5]:
            data = {
                field: row.get(field, "")
                for field in period_fields
            }
            print(data)

    print()
    print("TRACE COMPLETE")
    print("Vault changed: NO")
    print("Metric promoted: NO")


if __name__ == "__main__":
    main()