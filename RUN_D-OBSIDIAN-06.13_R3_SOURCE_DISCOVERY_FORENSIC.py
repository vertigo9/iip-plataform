#!/usr/bin/env python3
"""
D-OBSIDIAN-06.13 R3 — SOURCE DISCOVERY FORENSIC

READ-ONLY / NON-DESTRUCTIVE.

Purpose:
  Identify the exact CSV artifacts representing:
    1) the 2 historical REMOVE-CANDIDATE records from 06.09;
    2) the 66 forensic member records from 06.11.

The previous R2 schema matching was intentionally too permissive:
  - a 06.11 REMOVE_CANDIDATES file was selected as "members";
  - the 06.09 D_CANDIDATES file did not expose the expected Class value.

This diagnostic does NOT modify, delete, move, rename, or execute Git.
It inventories candidate CSVs and their semantic signatures so the next
gate can select sources deterministically.
"""

from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f), [])


def value_counter(rows: list[dict[str, str]], key: str) -> Counter:
    return Counter(
        (r.get(key) or "").strip()
        for r in rows
        if (r.get(key) or "").strip()
    )


def signature(rows: list[dict[str, str]]) -> str:
    keys = set(rows[0].keys()) if rows else set()
    parts = []

    for key in (
        "Class", "Type", "Decision", "Policy", "Reason",
        "GroupDecision", "CanonicalStatus", "ForensicDecision",
        "HumanApprovalRequired", "DeletionAuthorized",
    ):
        if key in keys:
            c = value_counter(rows, key)
            parts.append(
                f"{key}=" + ";".join(
                    f"{k}:{v}" for k, v in c.most_common(12)
                )
            )

    return " | ".join(parts)


def inspect_directory(directory: Path, label: str) -> list[dict[str, str]]:
    records = []

    print()
    print("=" * 88)
    print(label)
    print("=" * 88)
    print(f"Directory: {directory}")

    if not directory.exists():
        print("DIRECTORY NOT FOUND")
        return records

    files = sorted(directory.glob("*.csv"), key=lambda p: p.stat().st_mtime)

    for path in files:
        try:
            h = header(path)
            rows = read_csv(path)
        except Exception as exc:
            print(f"\n[ERROR] {path.name}: {exc}")
            continue

        keys = set(h)

        row = {
            "Directory": str(directory),
            "File": path.name,
            "Rows": str(len(rows)),
            "Headers": " | ".join(h),
            "Hash": str("Hash" in keys),
            "Path": str("Path" in keys),
            "Class": str("Class" in keys),
            "Type": str("Type" in keys),
            "Decision": str("Decision" in keys),
            "GroupDecision": str("GroupDecision" in keys),
            "CanonicalStatus": str("CanonicalStatus" in keys),
            "ForensicDecision": str("ForensicDecision" in keys),
            "Signature": signature(rows),
        }
        records.append(row)

        print()
        print(f"FILE : {path.name}")
        print(f"ROWS : {len(rows)}")
        print(f"HEAD : {h}")
        print(f"SIG  : {row['Signature']}")

        # Print useful exact populations.
        for key in (
            "Class", "Decision", "GroupDecision",
            "ForensicDecision", "Type"
        ):
            if key in keys:
                c = value_counter(rows, key)
                if c:
                    print(
                        f"  {key}: " +
                        ", ".join(f"{k}={v}" for k, v in c.most_common(20))
                    )

    return records


def main() -> int:
    repo = Path.cwd().resolve()
    d609 = repo / "reports" / "D-OBSIDIAN-06.9-R1"
    d611 = repo / "reports" / "D-OBSIDIAN-06.11-R1"
    out = repo / "reports" / "D-OBSIDIAN-06.13-R3"
    out.mkdir(parents=True, exist_ok=True)

    all_records = []
    all_records += inspect_directory(d609, "06.09 CSV INVENTORY")
    all_records += inspect_directory(d611, "06.11 CSV INVENTORY")

    # Candidate semantic matches are reported, never selected silently.
    print()
    print("=" * 88)
    print("SEMANTIC CANDIDATE ANALYSIS")
    print("=" * 88)

    d609_candidates = [
        r for r in all_records
        if r["Directory"].endswith("D-OBSIDIAN-06.9-R1")
        and r["Rows"] == "2"
    ]
    d611_candidates = [
        r for r in all_records
        if r["Directory"].endswith("D-OBSIDIAN-06.11-R1")
        and r["Rows"] == "66"
    ]

    print()
    print("06.09 files with exactly 2 rows:")
    for r in d609_candidates:
        print(f"  {r['File']} -> {r['Signature']}")

    print()
    print("06.11 files with exactly 66 rows:")
    for r in d611_candidates:
        print(f"  {r['File']} -> {r['Signature']}")

    # Export inventory.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    inventory = out / f"D-OBSIDIAN-06.13_R3_SOURCE_INVENTORY_{stamp}.csv"

    if all_records:
        with inventory.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(all_records[0].keys()))
            w.writeheader()
            w.writerows(all_records)

    summary = out / f"D-OBSIDIAN-06.13_R3_SUMMARY_{stamp}.txt"
    lines = [
        "D-OBSIDIAN-06.13 R3 - SOURCE DISCOVERY FORENSIC",
        "",
        "READ-ONLY / NON-DESTRUCTIVE",
        "",
        f"06.09 CSV files inspected: {sum(x['Directory'].endswith('D-OBSIDIAN-06.9-R1') for x in all_records)}",
        f"06.11 CSV files inspected: {sum(x['Directory'].endswith('D-OBSIDIAN-06.11-R1') for x in all_records)}",
        "",
        "06.09 files with exactly 2 rows:",
    ]
    lines += [f"  {x['File']}" for x in d609_candidates] or ["  NONE"]
    lines += [
        "",
        "06.11 files with exactly 66 rows:",
    ]
    lines += [f"  {x['File']}" for x in d611_candidates] or ["  NONE"]
    lines += [
        "",
        "IMPORTANT",
        "  This diagnostic does not declare a source authoritative merely by filename.",
        "  The next gate must select by exact semantic schema/content.",
        "  No cleanup authorization is produced here.",
        "",
        "SAFETY",
        "  No deletion.",
        "  No move.",
        "  No rename.",
        "  No source modification.",
        "  No Git operation.",
    ]
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print()
    print("=" * 88)
    print("SOURCE DISCOVERY FORENSIC: COMPLETE")
    print("=" * 88)
    print("No source was selected for authorization.")
    print(f"Reports: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
