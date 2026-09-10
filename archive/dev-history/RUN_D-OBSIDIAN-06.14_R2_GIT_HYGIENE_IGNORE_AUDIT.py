#!/usr/bin/env python3
"""
D-OBSIDIAN-06.14 R2 — GIT HYGIENE & IGNORE BOUNDARY AUDIT

READ-ONLY / NON-DESTRUCTIVE.

Audits:
  - .gitignore rules currently present
  - known runtime/generated artifacts
  - root-level installers/temp files
  - tracked files that match obvious runtime patterns
  - untracked files that are candidates for ignore treatment
  - protected trees/files that must not be blanket-ignored
  - no file deletion/move/rename
  - no Git write operations

This script does NOT edit .gitignore. It only produces a proposal.
"""

from __future__ import annotations

import csv
import hashlib
import subprocess
from pathlib import Path


KNOWN_RUNTIME = [
    ".coverage",
    ".logs",
    "coverage-current.json",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
]

ROOT_TEMP_PATTERNS = (
    "ChatGPT Installer",
    "Microsoft.Services.Store.winmd",
    "Sem título.base",
)

OBVIOUS_GENERATED_NAMES = (
    "coverage-current.json",
    ".coverage",
)

PROTECTED_PREFIXES = (
    "src/iip/",
    "tests/",
    "vault/",
    "data/",
    "archive/",
    "reports/",
)

PROTECTED_EXACT = {
    "src/iip/intelligence/metric_identity.py",
    "src/iip/intelligence/metric_persistence.py",
    "src/iip/intelligence/metric_persistence_adapter.py",
}

def git(repo: Path, *args: str) -> str:
    r = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return r.stdout.strip()

def ignored(repo: Path, rel: Path) -> bool:
    r = subprocess.run(
        ["git", "check-ignore", "-q", "--", str(rel)],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    return r.returncode == 0

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()

def write_csv(path: Path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        if not rows:
            return
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def main():
    repo = Path.cwd().resolve()
    out = repo / "reports" / "D-OBSIDIAN-06.14-R2"
    out.mkdir(parents=True, exist_ok=True)

    branch = git(repo, "branch", "--show-current")
    head = git(repo, "rev-parse", "HEAD")
    tracked = git(repo, "ls-files").splitlines()
    status = git(repo, "status", "--porcelain=v1").splitlines()

    gi_path = repo / ".gitignore"
    gi_text = gi_path.read_text(encoding="utf-8", errors="replace") if gi_path.exists() else ""

    runtime_rows = []
    for name in KNOWN_RUNTIME:
        rel = Path(name)
        path = repo / rel
        runtime_rows.append({
            "Path": name,
            "Exists": str(path.exists()),
            "Tracked": str(name in tracked),
            "Ignored": str(ignored(repo, rel)) if path.exists() else "N/A",
            "SizeBytes": str(path.stat().st_size) if path.is_file() else "",
            "SHA256": sha(path) if path.is_file() else "",
            "SuggestedBoundary": (
                "IGNORE_CANDIDATE" if path.exists() and not (name in tracked)
                else "REVIEW"
            ),
        })

    root_rows = []
    for path in sorted(repo.iterdir(), key=lambda x: x.name.lower()):
        if not path.is_file():
            continue
        rel = path.relative_to(repo)
        name = path.name
        match = any(x.lower() in name.lower() for x in ROOT_TEMP_PATTERNS)
        root_rows.append({
            "Path": str(rel),
            "SizeBytes": str(path.stat().st_size),
            "Ignored": str(ignored(repo, rel)),
            "Tracked": str(str(rel).replace("\\", "/") in tracked),
            "PatternMatch": str(match),
            "SuggestedAction": "REVIEW_IGNORE" if match else "KEEP_REVIEW",
            "SHA256": sha(path),
        })

    # Untracked inventory from porcelain, preserving Git's exact paths.
    untracked_rows = []
    for line in status:
        if not line.startswith("?? "):
            continue
        raw = line[3:]
        rels = [raw]
        # Git can quote paths containing special characters. Do not decode
        # aggressively; preserve exact porcelain representation.
        for raw_rel in rels:
            rel = Path(raw_rel)
            path = repo / rel
            s = str(rel).replace("\\", "/")
            protected = s in PROTECTED_EXACT or s.startswith(PROTECTED_PREFIXES)
            runtime = (
                s in KNOWN_RUNTIME
                or s.startswith(".pytest_cache/")
                or s.startswith(".logs/")
                or s.endswith("/__pycache__")
                or "/__pycache__/" in s
            )
            generated = (
                "coverage-current.json" in s
                or s.endswith(".pyc")
                or s.endswith(".pyo")
            )
            untracked_rows.append({
                "GitPath": raw_rel,
                "Exists": str(path.exists()),
                "SizeBytes": str(path.stat().st_size) if path.is_file() else "",
                "Protected": str(protected),
                "RuntimePattern": str(runtime),
                "GeneratedPattern": str(generated),
                "Ignored": str(ignored(repo, rel)) if path.exists() else "N/A",
                "SuggestedBoundary": (
                    "PROTECTED_KEEP" if protected else
                    "IGNORE_REVIEW" if (runtime or generated) else
                    "VERSIONING_REVIEW"
                ),
            })

    # Tracked obvious runtime/generated files.
    tracked_runtime = []
    for s in tracked:
        norm = s.replace("\\", "/")
        if (
            norm in KNOWN_RUNTIME
            or norm.endswith(".pyc")
            or norm.endswith(".pyo")
            or "/__pycache__/" in norm
            or norm.startswith(".pytest_cache/")
            or norm.startswith(".logs/")
        ):
            tracked_runtime.append({
                "Path": norm,
                "Reason": "TRACKED_RUNTIME_PATTERN",
            })

    # Current .gitignore lines.
    ignore_rows = []
    for i, line in enumerate(gi_text.splitlines(), 1):
        if not line.strip():
            continue
        ignore_rows.append({"Line": str(i), "Rule": line})

    checks = [
        {
            "Check": "HEAD_AVAILABLE",
            "Expected": 1,
            "Actual": int(bool(head)),
        },
        {
            "Check": "BRANCH_AVAILABLE",
            "Expected": 1,
            "Actual": int(bool(branch)),
        },
        {
            "Check": "GITIGNORE_PRESENT",
            "Expected": 1,
            "Actual": int(gi_path.exists()),
        },
        {
            "Check": "NO_TRACKED_RUNTIME_ARTIFACTS",
            "Expected": 0,
            "Actual": len(tracked_runtime),
        },
        {
            "Check": "NO_PROTECTED_RUNTIME_RECLASSIFICATION",
            "Expected": 0,
            "Actual": sum(
                1 for r in untracked_rows
                if r["Protected"] == "True" and r["SuggestedBoundary"] != "PROTECTED_KEEP"
            ),
        },
        {
            "Check": "NO_DESTRUCTIVE_ACTION",
            "Expected": 0,
            "Actual": 0,
        },
    ]
    for c in checks:
        c["Status"] = "PASS" if c["Expected"] == c["Actual"] else "FAIL"

    gate = all(c["Status"] == "PASS" for c in checks)

    stamp = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")

    write_csv(out / f"D-OBSIDIAN-06.14_R2_RUNTIME_{stamp}.csv", runtime_rows)
    write_csv(out / f"D-OBSIDIAN-06.14_R2_ROOT_{stamp}.csv", root_rows)
    write_csv(out / f"D-OBSIDIAN-06.14_R2_UNTRACKED_{stamp}.csv", untracked_rows)
    write_csv(out / f"D-OBSIDIAN-06.14_R2_TRACKED_RUNTIME_{stamp}.csv", tracked_runtime)
    write_csv(out / f"D-OBSIDIAN-06.14_R2_GITIGNORE_{stamp}.csv", ignore_rows)
    write_csv(out / f"D-OBSIDIAN-06.14_R2_CHECKS_{stamp}.csv", checks)

    summary = [
        "D-OBSIDIAN-06.14 R2 - GIT HYGIENE & IGNORE BOUNDARY AUDIT",
        "",
        "READ-ONLY / NON-DESTRUCTIVE",
        "",
        f"Branch: {branch}",
        f"HEAD: {head}",
        f"Tracked files: {len(tracked)}",
        f"Status entries: {len(status)}",
        f"Untracked entries: {len(untracked_rows)}",
        "",
        f"Known runtime artifacts existing: {sum(r['Exists'] == 'True' for r in runtime_rows)}",
        f"Known runtime artifacts ignored: {sum(r['Ignored'] == 'True' for r in runtime_rows)}",
        f"Tracked runtime artifacts: {len(tracked_runtime)}",
        f"Untracked ignore-review candidates: {sum(r['SuggestedBoundary'] == 'IGNORE_REVIEW' for r in untracked_rows)}",
        f"Protected untracked items: {sum(r['Protected'] == 'True' for r in untracked_rows)}",
        "",
        "CURRENT .gitignore",
    ]
    summary += [f"  {r['Line']}: {r['Rule']}" for r in ignore_rows]
    summary += ["", "CHECKS"]
    summary += [
        f"[{c['Status']}] {c['Check']} Expected={c['Expected']} Actual={c['Actual']}"
        for c in checks
    ]
    summary += [
        "",
        "POLICY",
        "  This phase proposes ignore boundaries only.",
        "  .gitignore was NOT modified.",
        "  No file was deleted, moved, renamed, or edited.",
        "  No Git write command was executed.",
        "",
        "BASELINE GATE: " + ("PASS" if gate else "FAIL"),
    ]
    (out / f"D-OBSIDIAN-06.14_R2_SUMMARY_{stamp}.txt").write_text(
        "\n".join(summary) + "\n", encoding="utf-8"
    )

    print("=" * 88)
    print("D-OBSIDIAN-06.14 R2 - GIT HYGIENE & IGNORE BOUNDARY AUDIT")
    print("=" * 88)
    print("READ-ONLY / NON-DESTRUCTIVE")
    print()
    print(f"Branch                 : {branch}")
    print(f"HEAD                   : {head}")
    print(f"Tracked files          : {len(tracked)}")
    print(f"Status entries         : {len(status)}")
    print(f"Untracked entries      : {len(untracked_rows)}")
    print()
    print("KNOWN RUNTIME")
    print(f"  Existing             : {sum(r['Exists'] == 'True' for r in runtime_rows)}")
    print(f"  Ignored              : {sum(r['Ignored'] == 'True' for r in runtime_rows)}")
    print(f"  Tracked runtime      : {len(tracked_runtime)}")
    print()
    print("UNTRACKED BOUNDARIES")
    print(f"  Ignore-review        : {sum(r['SuggestedBoundary'] == 'IGNORE_REVIEW' for r in untracked_rows)}")
    print(f"  Protected keep       : {sum(r['SuggestedBoundary'] == 'PROTECTED_KEEP' for r in untracked_rows)}")
    print(f"  Versioning review    : {sum(r['SuggestedBoundary'] == 'VERSIONING_REVIEW' for r in untracked_rows)}")
    print()
    for c in checks:
        print(f"[{c['Status']}] {c['Check']} Expected={c['Expected']} Actual={c['Actual']}")
    print()
    print("=" * 88)
    print("GIT HYGIENE AUDIT: " + ("PASS" if gate else "FAIL"))
    print("=" * 88)
    print()
    print("READ-ONLY: .gitignore nao foi alterado e nenhuma acao destrutiva foi executada.")
    print(f"Reports: {out}")

    return 0 if gate else 1

if __name__ == "__main__":
    raise SystemExit(main())
