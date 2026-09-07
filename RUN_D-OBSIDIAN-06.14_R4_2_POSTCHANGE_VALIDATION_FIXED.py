#!/usr/bin/env python3
"""
D-OBSIDIAN-06.14 R4.2 — POST-CHANGE VALIDATION (FIXED)

READ-ONLY.

Validates the R4 .gitignore change using path/state semantics rather than
set-difference of raw porcelain lines.

Expected:
  - .gitignore is modified by the approved R4 change.
  - .logs/ and coverage-current.json may disappear from status because
    they became ignored.
  - pre-existing modifications remain modifications.
  - R4/R4.1 generated evidence is not treated as a project-content change.
  - the newly generated R4.1 script is an expected diagnostic artifact.
  - protected representatives remain non-ignored.
"""

from __future__ import annotations

import csv
import re
import subprocess
from datetime import datetime
from pathlib import Path


APPROVED = [".logs/", "coverage-current.json"]

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

EXPECTED_NEW = [
    "RUN_D-OBSIDIAN-06.14_R4_1_POSTCHANGE_FORENSIC.py",
]

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

def parse_porcelain(lines):
    out = {}
    for line in lines:
        if not line:
            continue
        xy = line[:2]
        raw = line[3:] if len(line) >= 4 else ""
        path = raw.strip('"')
        out[path] = xy
    return out

def main():
    repo = Path.cwd().resolve()
    r4 = repo / "reports" / "D-OBSIDIAN-06.14-R4"
    out = repo / "reports" / "D-OBSIDIAN-06.14-R4.2"
    out.mkdir(parents=True, exist_ok=True)

    before_files = sorted(r4.glob("D-OBSIDIAN-06.14_R4_STATUS_BEFORE_*.txt"))
    after_files = sorted(r4.glob("D-OBSIDIAN-06.14_R4_STATUS_AFTER_*.txt"))
    before_path = before_files[-1] if before_files else None
    after_path = after_files[-1] if after_files else None

    before_lines = (
        before_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if before_path else []
    )
    r4_after_lines = (
        after_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if after_path else []
    )
    current_lines = git("status", "--porcelain=v1").splitlines()

    before = parse_porcelain(before_lines)
    r4_after = parse_porcelain(r4_after_lines)
    current = parse_porcelain(current_lines)

    rows = []

    # State-aware analysis of pre-existing entries.
    all_paths = sorted(set(before) | set(current))
    for path in all_paths:
        b = before.get(path)
        c = current.get(path)

        if b == c and b is not None:
            cls = "UNCHANGED_PREEXISTING_STATUS"
        elif path == ".gitignore" and c is not None:
            cls = "INTENDED_GITIGNORE_CHANGE"
        elif path in (".logs", "coverage-current.json") and b == "??" and c is None:
            cls = "EXPECTED_NOW_IGNORED"
        elif b is not None and c is None:
            cls = "UNEXPECTED_REMOVAL_FROM_STATUS"
        elif b is None and c is not None:
            if path in EXPECTED_NEW:
                cls = "EXPECTED_NEW_DIAGNOSTIC"
            elif path.startswith("reports/D-OBSIDIAN-06.14-R4"):
                cls = "EXPECTED_R4_EVIDENCE"
            elif path.startswith("reports/D-OBSIDIAN-06.14-R4.2"):
                cls = "EXPECTED_R4_2_EVIDENCE"
            else:
                cls = "NEW_UNEXPECTED_STATUS"
        else:
            cls = "STATUS_TRANSITION"

        rows.append({
            "Path": path,
            "BeforeXY": b or "",
            "CurrentXY": c or "",
            "Classification": cls,
        })

    protected_rows = []
    for path in PROTECTED:
        exists = (repo / path).exists()
        ig = ignored(path) if exists else False
        protected_rows.append({
            "Path": path,
            "Exists": str(exists),
            "Ignored": str(ig) if exists else "N/A",
            "Status": "PASS" if (not exists or not ig) else "FAIL",
        })

    runtime_rows = []
    for path in APPROVED:
        ig = ignored(path)
        runtime_rows.append({
            "Path": path,
            "Ignored": str(ig),
            "Status": "PASS" if ig else "FAIL",
        })

    checks = [
        ("R4_BEFORE_STATUS_SOURCE", 1, int(before_path is not None)),
        ("INTENDED_GITIGNORE_CHANGE", 1,
         sum(x["Classification"] == "INTENDED_GITIGNORE_CHANGE" for x in rows)),
        ("EXPECTED_IGNORED_TRANSITIONS", 2,
         sum(x["Classification"] == "EXPECTED_NOW_IGNORED" for x in rows)),
        ("UNEXPECTED_STATUS_REMOVALS", 0,
         sum(x["Classification"] == "UNEXPECTED_REMOVAL_FROM_STATUS" for x in rows)),
        ("NEW_UNEXPECTED_STATUS", 0,
         sum(x["Classification"] == "NEW_UNEXPECTED_STATUS" for x in rows)),
        ("PROTECTED_PATH_FAILURES", 0,
         sum(x["Status"] == "FAIL" for x in protected_rows)),
        ("RUNTIME_IGNORE_FAILURES", 0,
         sum(x["Status"] == "FAIL" for x in runtime_rows)),
    ]

    check_rows = []
    for n,e,a in checks:
        check_rows.append({
            "Check": n,
            "Expected": str(e),
            "Actual": str(a),
            "Status": "PASS" if e == a else "FAIL",
        })

    gate = all(x["Status"] == "PASS" for x in check_rows)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def write_csv(path, data):
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            if not data:
                return
            w = csv.DictWriter(f, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)

    write_csv(out / f"R4_2_STATUS_STATE_ANALYSIS_{stamp}.csv", rows)
    write_csv(out / f"R4_2_PROTECTED_{stamp}.csv", protected_rows)
    write_csv(out / f"R4_2_RUNTIME_{stamp}.csv", runtime_rows)
    write_csv(out / f"R4_2_CHECKS_{stamp}.csv", check_rows)

    summary = [
        "D-OBSIDIAN-06.14 R4.2 — POST-CHANGE VALIDATION (FIXED)",
        "",
        "READ-ONLY",
        f"R4 before: {before_path}",
        f"R4 after : {after_path}",
        "",
        "STATE ANALYSIS",
    ]
    summary += [
        f"  {x['Path']}: {x['BeforeXY'] or '-'} -> {x['CurrentXY'] or '-'} | {x['Classification']}"
        for x in rows
    ]
    summary += [
        "",
        "CHECKS",
        *[
            f"[{x['Status']}] {x['Check']} Expected={x['Expected']} Actual={x['Actual']}"
            for x in check_rows
        ],
        "",
        "POLICY",
        "R4.2 is read-only.",
        "The .gitignore change from R4 is not reverted.",
        "No project content is deleted, moved, renamed, or modified.",
        "",
        "POST-CHANGE VALIDATION GATE: " + ("PASS" if gate else "FAIL"),
    ]
    (out / f"R4_2_SUMMARY_{stamp}.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")

    print("=" * 88)
    print("D-OBSIDIAN-06.14 R4.2 - POST-CHANGE VALIDATION (FIXED)")
    print("=" * 88)
    print("READ-ONLY")
    print()
    print("STATE ANALYSIS")
    for x in rows:
        print(
            f"  {x['Path']}: {x['BeforeXY'] or '-'} -> "
            f"{x['CurrentXY'] or '-'} | {x['Classification']}"
        )
    print()
    for x in check_rows:
        print(f"[{x['Status']}] {x['Check']} Expected={x['Expected']} Actual={x['Actual']}")
    print()
    print("=" * 88)
    print("POST-CHANGE VALIDATION GATE: " + ("PASS" if gate else "FAIL"))
    print("=" * 88)
    print()
    print(f"Reports: {out}")
    return 0 if gate else 1

if __name__ == "__main__":
    raise SystemExit(main())
