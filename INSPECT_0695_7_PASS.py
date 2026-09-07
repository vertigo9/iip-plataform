from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path.cwd()
INPUT = ROOT / "reports" / "PCIP11_0695_7_PROMOTION_GATE.csv"


def main() -> None:
    if not INPUT.exists():
        raise SystemExit(f"Arquivo não encontrado: {INPUT}")

    with INPUT.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    passed = [
        row
        for row in rows
        if row.get("Promotion_Gate") == "PASS"
    ]

    print("0695.7 PASS INSPECTION")
    print("=" * 80)
    print(f"Total rows : {len(rows)}")
    print(f"PASS       : {len(passed)}")
    print()

    for index, row in enumerate(passed, start=1):
        print(f"[{index:02d}]")
        print(f"  Metric                : {row.get('Metric', '')}")
        print(f"  Ticker                : {row.get('Ticker', '')}")
        print(f"  Lineage               : {row.get('Lineage', '')}")
        print(f"  Date                  : {row.get('Date', '')}")
        print(f"  Period                : {row.get('Period', '')}")
        print(f"  Value                 : {row.get('Value', '')}")
        print(f"  Unit                  : {row.get('Unit', '')}")
        print(f"  Scale_State           : {row.get('Scale_State', '')}")
        print(f"  Scale_Confidence      : {row.get('Scale_Confidence', '')}")
        print(f"  Resolution_Status     : {row.get('Resolution_Status', '')}")
        print(f"  Promotion_Action      : {row.get('Promotion_Action', '')}")
        print(f"  Plausibility          : {row.get('Plausibility', '')}")
        print(f"  Source                : {row.get('Source', '')}")
        print(f"  Document_ID           : {row.get('Document_ID', '')}")
        print(f"  Document_Hash         : {row.get('Document_Hash', '')}")
        print()


if __name__ == "__main__":
    main()