from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path.cwd()
REPORTS = ROOT / "reports"

CANDIDATES = (
    REPORTS
    / "PCIP11_METRIC_PROMOTION_CANDIDATES_0695_6R2.csv"
)

TRIAGE = (
    REPORTS
    / "PCIP11_MULTIFORMAT_TRIAGE_0695_2R3_FIXED.csv"
)


def load_csv(path: Path):
    if not path.exists():
        raise SystemExit(f"Arquivo não encontrado: {path}")

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    candidates = load_csv(CANDIDATES)
    triage = load_csv(TRIAGE)

    triage_by_sha = {
        row.get("SHA256", "").strip().upper(): row
        for row in triage
        if row.get("SHA256", "").strip()
    }

    print("0695 TEMPORAL SIGNAL INSPECTION")
    print("=" * 100)
    print(f"Candidates : {len(candidates)}")
    print(f"Triage     : {len(triage)}")
    print()

    for index, candidate in enumerate(candidates, start=1):
        sha = candidate.get("SHA256", "").strip().upper()
        triage_row = triage_by_sha.get(sha, {})

        print("-" * 100)
        print(f"[{index:03d}] {candidate.get('Metric', '')}")
        print(f"SHA256                  : {sha}")
        print(f"FileName                : {candidate.get('FileName', '')}")
        print(f"Original_Identity       : {candidate.get('Original_Identity', '')}")
        print(f"Current Period          : {candidate.get('Period', '')}")
        print(
            f"Document_Year           : "
            f"{triage_row.get('Document_Year', '')}"
        )
        print(
            f"Storage_Year            : "
            f"{triage_row.get('Storage_Year', '')}"
        )
        print(
            f"Document_Period_Manifest: "
            f"{triage_row.get('Document_Period_Manifest', '')}"
        )
        print(
            f"Content_Periods        : "
            f"{triage_row.get('Content_Periods', '')}"
        )
        print(
            f"Content_Dates          : "
            f"{triage_row.get('Content_Dates', '')}"
        )
        print(
            f"Content_Quarters       : "
            f"{triage_row.get('Content_Quarters', '')}"
        )
        print(
            f"Content_Months         : "
            f"{triage_row.get('Content_Months', '')}"
        )

    print()
    print("=" * 100)
    print("Temporal inspection complete.")
    print("Vault changed: NO")
    print("Metric promoted: NO")


if __name__ == "__main__":
    main()