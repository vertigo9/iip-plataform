#!/usr/bin/env python3
"""
D-OBSIDIAN-06.14 R4.1 — POST-CHANGE FORENSIC

READ-ONLY. Does not modify .gitignore or any project file.

Purpose:
  Diagnose the single unexpected git-status delta reported by R4.

It compares:
  - R4 STATUS_BEFORE
  - current git status
and separately classifies:
  - intended .gitignore modification
  - R4 backup/report artifacts
  - any truly unexpected status entry.

It also verifies the two approved ignore rules and protected paths.
"""

from pathlib import Path
import subprocess
import csv
from datetime import datetime


PROTECTED = [
    "src/iip/intelligence/metric_identity.py",
    "src/iip/intelligence/metric_persistence.py",
    "src/iip/intelligence/metric_persistence_adapter.py",
    "tests/integration",
    "tests/intelligence",
    "vault",
    "data",
    "archive",
    "reports",
]

RUNTIME = [".logs/", "coverage-current.json"]

def git(*args):
    r = subprocess.run(
        ["git", *args],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return r.stdout.strip()

def ignored(path):
    r = subprocess.run(
        ["git", "check-ignore", "-q", "--", path],
        cwd=Path.cwd(),
        capture_output=True,
        check=False,
    )
    return r.returncode == 0

def main():
    repo = Path.cwd().resolve()
    r4 = repo / "reports" / "D-OBSIDIAN-06.14-R4"
    out = repo / "reports" / "D-OBSIDIAN-06.14-R4.1"
    out.mkdir(parents=True, exist_ok=True)

    before_files = sorted(r4.glob("D-OBSIDIAN-06.14_R4_STATUS_BEFORE_*.txt"))
    before_path = before_files[-1] if before_files else None
    before = before_path.read_text(encoding="utf-8", errors="replace").splitlines() if before_path else []

    current_raw = git("status", "--porcelain=v1")
    current = current_raw.splitlines() if current_raw else []

    before_set = set(before)
    current_set = set(current)
    added = sorted(current_set - before_set)
    removed = sorted(before_set - current_set)

    rows = []
    for entry in added:
        # Exact status path extraction after the two-character XY prefix.
        path = entry[3:] if len(entry) >= 4 else entry
        path_clean = path.strip('"')

        if path_clean == ".gitignore":
            classification = "INTENDED_GITIGNORE_CHANGE"
        elif path_clean.startswith("reports/D-OBSIDIAN-06.14-R4"):
            classification = "EXPECTED_R4_EVIDENCE"
        elif path_clean.startswith("reports/D-OBSIDIAN-06.14-R4.1"):
            classification = "EXPECTED_R4_1_EVIDENCE"
        else:
            classification = "UNEXPECTED"

        rows.append({
            "StatusEntry": entry,
            "Path": path_clean,
            "Classification": classification,
        })

    protected_rows = []
    for path in PROTECTED:
        exists = (repo / path).exists()
        protected_rows.append({
            "Path": path,
            "Exists": str(exists),
            "Ignored": str(ignored(path)) if exists else "N/A",
            "Status": "PASS" if (not exists or not ignored(path)) else "FAIL",
        })

    runtime_rows = [
        {
            "Path": p,
            "Exists": str((repo / p.rstrip("/")).exists()),
            "Ignored": str(ignored(p)),
            "Status": "PASS" if ignored(p) else "FAIL",
        }
        for p in RUNTIME
    ]

    checks = [
        ("R4_BEFORE_STATUS_FOUND", 1, int(before_path is not None)),
        ("INTENDED_GITIGNORE_DELTA", 1, int(sum(x["Classification"] == "INTENDED_GITIGNORE_CHANGE" for x in rows) == 1)),
        ("UNEXPECTED_STATUS_DELTAS", 0, sum(x["Classification"] == "UNEXPECTED" for x in rows)),
        ("REMOVED_PREEXISTING_STATUS_ENTRIES", 0, len(removed)),
        ("PROTECTED_PATH_CHECKS", 0, sum(x["Status"] == "FAIL" for x in protected_rows)),
        ("RUNTIME_IGNORE_CHECKS", 0, sum(x["Status"] == "FAIL" for x in runtime_rows)),
    ]

    check_rows = []
    for n,e,a in checks:
        check_rows.append({
            "Check": n, "Expected": str(e), "Actual": str(a),
            "Status": "PASS" if e == a else "FAIL"
        })

    gate = all(x["Status"] == "PASS" for x in check_rows)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def write(path, rows):
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            if not rows:
                return
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)

    write(out / f"R4_1_STATUS_DELTA_{stamp}.csv", rows)
    write(out / f"R4_1_PROTECTED_{stamp}.csv", protected_rows)
    write(out / f"R4_1_RUNTIME_{stamp}.csv", runtime_rows)
    write(out / f"R4_1_CHECKS_{stamp}.csv", check_rows)

    summary = [
        "D-OBSIDIAN-06.14 R4.1 — POST-CHANGE FORENSIC",
        "",
        "READ-ONLY",
        f"R4 before status source: {before_path}",
        "",
        "ADDED STATUS ENTRIES",
    ]
    summary += [f"  {x['StatusEntry']} -> {x['Classification']}" for x in rows] or ["  None"]
    summary += [
        "",
        "REMOVED STATUS ENTRIES",
        *([f"  {x}" for x in removed] or ["  None"]),
        "",
        "CHECKS",
        *[
            f"[{x['Status']}] {x['Check']} Expected={x['Expected']} Actual={x['Actual']}"
            for x in check_rows
        ],
        "",
        "POLICY",
        "No file was modified by R4.1.",
        "This diagnostic does not alter .gitignore.",
        "",
        "POST-CHANGE FORENSIC GATE: " + ("PASS" if gate else "FAIL"),
    ]
    (out / f"R4_1_SUMMARY_{stamp}.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")

    print("=" * 88)
    print("D-OBSIDIAN-06.14 R4.1 - POST-CHANGE FORENSIC")
    print("=" * 88)
    print("READ-ONLY")
    print()
    print(f"R4 before source: {before_path}")
    print()
    print("ADDED STATUS ENTRIES")
    for x in rows:
        print(f"  {x['StatusEntry']} -> {x['Classification']}")
    if not rows:
        print("  None")
    print()
    print("REMOVED STATUS ENTRIES")
    for x in removed:
        print(f"  {x}")
    if not removed:
        print("  None")
    print()
    for x in check_rows:
        print(f"[{x['Status']}] {x['Check']} Expected={x['Expected']} Actual={x['Actual']}")
    print()
    print("=" * 88)
    print("POST-CHANGE FORENSIC GATE: " + ("PASS" if gate else "FAIL"))
    print("=" * 88)
    print()
    print(f"Reports: {out}")
    return 0 if gate else 1

if __name__ == "__main__":
    raise SystemExit(main())
