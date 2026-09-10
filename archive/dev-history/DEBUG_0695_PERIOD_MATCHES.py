from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path.cwd()
REPORTS = ROOT / "reports"

CANDIDATES = REPORTS / "PCIP11_METRIC_PROMOTION_CANDIDATES_0695_6R2.csv"

MONTHS = {
    "janeiro": "01",
    "fevereiro": "02",
    "março": "03",
    "marco": "03",
    "abril": "04",
    "maio": "05",
    "junho": "06",
    "julho": "07",
    "agosto": "08",
    "setembro": "09",
    "outubro": "10",
    "novembro": "11",
    "dezembro": "12",
}


def main() -> None:
    if not CANDIDATES.exists():
        raise SystemExit(f"Arquivo não encontrado: {CANDIDATES}")

    with CANDIDATES.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as fh:
        rows = list(csv.DictReader(fh))

    print("0695 PERIOD MATCH DEBUG")
    print("=" * 80)
    print(f"Candidate rows: {len(rows)}")
    print()

    found = 0

    for row in rows:
        filename = row.get("FileName", "")
        period = row.get("Period", "")

        if period != "2003-12":
            continue

        text = " ".join(
            [
                str(row.get("Evidence_Text", "")),
                str(row.get("FileName", "")),
            ]
        )

        for month, number in MONTHS.items():
            pattern = month + r".{0,30}?((?:19|20)\d{2})"

            for match in re.finditer(
                pattern,
                text,
                re.IGNORECASE,
            ):
                detected = match.group(1) + "-" + number

                if detected != "2003-12":
                    continue

                found += 1

                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)

                context = text[start:end]

                print()
                print("-" * 80)
                print(f"Row      : {row.get('Row')}")
                print(f"File     : {filename}")
                print(f"Metric   : {row.get('Metric')}")
                print(f"Identity : {row.get('Original_Identity')}")
                print(f"Detected : {detected}")
                print(f"Matched  : {repr(match.group(0))}")
                print()
                print("CONTEXT:")
                print(context)

                if found >= 20:
                    print()
                    print("20 matches displayed; stopping diagnostic.")
                    print()
                    print("DEBUG COMPLETE")
                    print("Vault changed: NO")
                    print("Metric promoted: NO")
                    return

    print()
    print(f"Total matches displayed: {found}")
    print()
    print("DEBUG COMPLETE")
    print("Vault changed: NO")
    print("Metric promoted: NO")


if __name__ == "__main__":
    main()