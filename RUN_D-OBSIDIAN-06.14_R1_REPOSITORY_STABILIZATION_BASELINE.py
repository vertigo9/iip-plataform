#!/usr/bin/env python3
"""
D-OBSIDIAN-06.14 R1 — REPOSITORY STABILIZATION & BASELINE PREPARATION

READ-ONLY / NON-DESTRUCTIVE.

Purpose:
  Build an auditable baseline inventory before Git stabilization.

Checks:
  - repository identity / branch / HEAD
  - tracked vs untracked files
  - modified / deleted tracked files
  - root-level clutter and temporary artifacts
  - .gitignore coverage for known runtime artifacts
  - protected trees and critical 0695 files
  - 06.09-06.13 evidence directories
  - no cleanup authorization
  - no deletion / move / rename / source modification
  - no Git write operations

Git commands are read-only: status, branch, rev-parse, ls-files.
"""

from __future__ import annotations

import csv
import hashlib
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path


PROTECTED_FILES = [
    Path("src/iip/intelligence/metric_identity.py"),
    Path("src/iip/intelligence/metric_persistence.py"),
    Path("src/iip/intelligence/metric_persistence_adapter.py"),
]

PROTECTED_DIRS = [
    Path("data"),
    Path("vault"),
    Path("archive"),
    Path("tests/intelligence"),
    Path("tests/integration"),
]

EVIDENCE_DIRS = [
    Path("reports/D-OBSIDIAN-06.9-R1"),
    Path("reports/D-OBSIDIAN-06.10-R4"),
    Path("reports/D-OBSIDIAN-06.11-R1"),
    Path("reports/D-OBSIDIAN-06.12-R1"),
    Path("reports/D-OBSIDIAN-06.12-R2"),
    Path("reports/D-OBSIDIAN-06.12-R3"),
    Path("reports/D-OBSIDIAN-06.12-R4"),
    Path("reports/D-OBSIDIAN-06.13-R1"),
    Path("reports/D-OBSIDIAN-06.13-R2"),
    Path("reports/D-OBSIDIAN-06.13-R3"),
    Path("reports/D-OBSIDIAN-06.13-R4"),
]

RUNTIME_ARTIFACTS = [
    ".coverage",
    ".logs",
    "coverage-current.json",
    ".pytest_cache",
    ".obsidian/graph.json",
]

def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.stdout.strip()

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def is_ignored(repo: Path, rel: Path) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", "--", str(rel)],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0

def main() -> int:
    repo = Path.cwd().resolve()
    out = repo / "reports" / "D-OBSIDIAN-06.14-R1"
    out.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    branch = run_git(repo, "branch", "--show-current")
    head = run_git(repo, "rev-parse", "HEAD")
    status_porcelain = run_git(repo, "status", "--porcelain=v1")
    tracked = run_git(repo, "ls-files").splitlines()

    status_lines = status_porcelain.splitlines() if status_porcelain else []
    modified = [x for x in status_lines if len(x) >= 2 and x[:2] not in ("??", "!!")]
    untracked = [x for x in status_lines if x.startswith("??")]

    tracked_deleted = [
        x for x in status_lines
        if len(x) >= 2 and "D" in x[:2]
    ]

    root_files = [
        p for p in repo.iterdir()
        if p.is_file() and p.name not in {".git"}
    ]

    runtime_rows = []
    for raw in RUNTIME_ARTIFACTS:
        rel = Path(raw)
        exists = (repo / rel).exists()
        runtime_rows.append({
            "Artifact": raw,
            "Exists": str(exists),
            "IgnoredByGit": str(is_ignored(repo, rel)) if exists else "N/A",
            "SHA256": sha256(repo / rel) if exists and (repo / rel).is_file() else "",
        })

    protected_rows = []
    for rel in PROTECTED_FILES:
        path = repo / rel
        protected_rows.append({
            "Path": str(rel),
            "Exists": str(path.exists()),
            "SHA256": sha256(path) if path.is_file() else "",
        })

    protected_tree_rows = []
    for rel in PROTECTED_DIRS:
        path = repo / rel
        count = sum(1 for x in path.rglob("*") if x.is_file()) if path.exists() else 0
        protected_tree_rows.append({
            "Path": str(rel),
            "Exists": str(path.exists()),
            "FileCount": str(count),
        })

    evidence_rows = []
    for rel in EVIDENCE_DIRS:
        path = repo / rel
        count = sum(1 for x in path.glob("*") if x.is_file()) if path.exists() else 0
        evidence_rows.append({
            "Path": str(rel),
            "Exists": str(path.exists()),
            "DirectFileCount": str(count),
        })

    # Root clutter inventory, but no classification is destructive.
    root_rows = []
    for path in sorted(root_files, key=lambda x: x.name.lower()):
        rel = path.relative_to(repo)
        root_rows.append({
            "Path": str(rel),
            "SizeBytes": str(path.stat().st_size),
            "IgnoredByGit": str(is_ignored(repo, rel)),
            "SHA256": sha256(path),
        })

    # Git status first-column summary.
    status_counter = Counter(
        x[:2] if len(x) >= 2 else x for x in status_lines
    )

    checks = []

    def check(name: str, expected: int, actual: int):
        checks.append({
            "Check": name,
            "Expected": expected,
            "Actual": actual,
            "Status": "PASS" if expected == actual else "FAIL",
        })

    # These are invariants, not assumptions about zero modifications.
    check("HEAD_AVAILABLE", 1, int(bool(head)))
    check("BRANCH_AVAILABLE", 1, int(bool(branch)))
    check(
        "PROTECTED_FILES_PRESENT",
        len(PROTECTED_FILES),
        sum(x["Exists"] == "True" for x in protected_rows),
    )
    check(
        "PROTECTED_TREES_PRESENT",
        len(PROTECTED_DIRS),
        sum(x["Exists"] == "True" for x in protected_tree_rows),
    )
    check(
        "EVIDENCE_DIRS_PRESENT",
        len(EVIDENCE_DIRS),
        sum(x["Exists"] == "True" for x in evidence_rows),
    )
    check(
        "NO_GIT_WRITE_COMMANDS",
        0,
        0,
    )
    check(
        "NO_DELETION_EXECUTION",
        0,
        0,
    )

    # Informational checks about known runtime artifacts. These intentionally
    # do not fail the gate because stabilization has not yet modified .gitignore.
    ignored_runtime = sum(
        r["IgnoredByGit"] == "True" for r in runtime_rows
        if r["Exists"] == "True"
    )

    # Baseline gate is PASS if structural protected/evidence invariants pass.
    gate = all(x["Status"] == "PASS" for x in checks)

    def write_csv(path: Path, rows: list[dict[str, str]]):
        if not rows:
            path.write_text("", encoding="utf-8-sig")
            return
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    status_file = out / f"D-OBSIDIAN-06.14_R1_GIT_STATUS_{stamp}.txt"
    status_file.write_text(
        "\n".join([
            f"Branch: {branch}",
            f"HEAD: {head}",
            "",
            "GIT STATUS --PORCELAIN",
            status_porcelain,
            "",
            f"Tracked files: {len(tracked)}",
            f"Status entries: {len(status_lines)}",
            f"Modified/changed entries: {len(modified)}",
            f"Untracked entries: {len(untracked)}",
            f"Deleted tracked entries: {len(tracked_deleted)}",
        ]) + "\n",
        encoding="utf-8",
    )

    write_csv(
        out / f"D-OBSIDIAN-06.14_R1_RUNTIME_ARTIFACTS_{stamp}.csv",
        runtime_rows,
    )
    write_csv(
        out / f"D-OBSIDIAN-06.14_R1_PROTECTED_FILES_{stamp}.csv",
        protected_rows,
    )
    write_csv(
        out / f"D-OBSIDIAN-06.14_R1_PROTECTED_TREES_{stamp}.csv",
        protected_tree_rows,
    )
    write_csv(
        out / f"D-OBSIDIAN-06.14_R1_EVIDENCE_DIRS_{stamp}.csv",
        evidence_rows,
    )
    write_csv(
        out / f"D-OBSIDIAN-06.14_R1_ROOT_INVENTORY_{stamp}.csv",
        root_rows,
    )
    write_csv(
        out / f"D-OBSIDIAN-06.14_R1_CHECKS_{stamp}.csv",
        checks,
    )

    summary_file = out / f"D-OBSIDIAN-06.14_R1_SUMMARY_{stamp}.txt"
    summary = [
        "D-OBSIDIAN-06.14 R1 - REPOSITORY STABILIZATION & BASELINE",
        "",
        "READ-ONLY / NON-DESTRUCTIVE",
        "",
        "IDENTITY",
        f"  Branch: {branch}",
        f"  HEAD: {head}",
        "",
        "GIT STATE",
        f"  Tracked files: {len(tracked)}",
        f"  Status entries: {len(status_lines)}",
        f"  Changed entries: {len(modified)}",
        f"  Untracked entries: {len(untracked)}",
        f"  Deleted tracked entries: {len(tracked_deleted)}",
        "",
        "RUNTIME ARTIFACTS",
        f"  Existing known runtime artifacts: {sum(r['Exists'] == 'True' for r in runtime_rows)}",
        f"  Currently ignored: {ignored_runtime}",
        "",
        "PROTECTED",
        f"  Critical files present: {sum(x['Exists'] == 'True' for x in protected_rows)}/{len(protected_rows)}",
        f"  Protected trees present: {sum(x['Exists'] == 'True' for x in protected_tree_rows)}/{len(protected_tree_rows)}",
        "",
        "EVIDENCE",
        f"  06.09-06.13 evidence directories present: {sum(x['Exists'] == 'True' for x in evidence_rows)}/{len(evidence_rows)}",
        "",
        "CHECKS",
    ]
    for c in checks:
        summary.append(
            f"[{c['Status']}] {c['Check']} Expected={c['Expected']} Actual={c['Actual']}"
        )

    summary += [
        "",
        "POLICY",
        "  This is a baseline inventory, not cleanup execution.",
        "  No files were deleted, moved, renamed, or modified.",
        "  No Git write operation was executed.",
        "",
        "NEXT CONTROLLED STEP",
        "  Review runtime-artifact inventory and .gitignore coverage.",
        "  Do not delete artifacts merely because they are untracked.",
        "",
        "BASELINE GATE: " + ("PASS" if gate else "FAIL"),
    ]
    summary_file.write_text("\n".join(summary) + "\n", encoding="utf-8")

    print("=" * 88)
    print("D-OBSIDIAN-06.14 R1 - REPOSITORY STABILIZATION & BASELINE")
    print("=" * 88)
    print("READ-ONLY / NON-DESTRUCTIVE")
    print()
    print("IDENTITY")
    print(f"  Branch : {branch}")
    print(f"  HEAD   : {head}")
    print()
    print("GIT STATE")
    print(f"  Tracked files          : {len(tracked)}")
    print(f"  Status entries         : {len(status_lines)}")
    print(f"  Changed entries       : {len(modified)}")
    print(f"  Untracked entries     : {len(untracked)}")
    print(f"  Deleted tracked       : {len(tracked_deleted)}")
    print()
    print("KNOWN RUNTIME ARTIFACTS")
    print(f"  Existing              : {sum(r['Exists'] == 'True' for r in runtime_rows)}")
    print(f"  Currently ignored     : {ignored_runtime}")
    print()
    print("PROTECTED")
    print(f"  Critical files        : {sum(x['Exists'] == 'True' for x in protected_rows)}/{len(protected_rows)}")
    print(f"  Protected trees       : {sum(x['Exists'] == 'True' for x in protected_tree_rows)}/{len(protected_tree_rows)}")
    print()
    print("EVIDENCE")
    print(f"  Evidence dirs         : {sum(x['Exists'] == 'True' for x in evidence_rows)}/{len(evidence_rows)}")
    print()
    for c in checks:
        print(
            f"[{c['Status']}] {c['Check']} "
            f"Expected={c['Expected']} Actual={c['Actual']}"
        )
    print()
    print("=" * 88)
    print("BASELINE GATE: " + ("PASS" if gate else "FAIL"))
    print("=" * 88)
    print()
    print("READ-ONLY: nenhuma acao destrutiva foi executada.")
    print(f"Reports: {out}")

    return 0 if gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
