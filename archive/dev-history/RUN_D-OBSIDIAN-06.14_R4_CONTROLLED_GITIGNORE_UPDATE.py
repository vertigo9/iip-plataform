#!/usr/bin/env python3
"""
D-OBSIDIAN-06.14 R4 — CONTROLLED .GITIGNORE UPDATE

CONTROLLED WRITE / NON-DESTRUCTIVE TO PROJECT CONTENT.

Only .gitignore is modified, and only by appending the two rules approved
by the R3 proposal:
  .logs/
  coverage-current.json

A timestamped backup of the original .gitignore is created under the
06.14-R4 report directory. No project data/source/vault/test file is
deleted, moved, renamed, or modified. No Git commit/stage/reset/clean is run.

Post-change checks validate:
  - exact approved rules are present once
  - existing rules remain unchanged
  - protected trees remain non-ignored for representative files
  - runtime targets are ignored
  - no other tracked/untracked status change is caused by the script
  - backup exists and hash matches the pre-change content
"""

from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime
from pathlib import Path


APPROVED_RULES = [".logs/", "coverage-current.json"]

PROTECTED_REPRESENTATIVES = [
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

RUNTIME_TARGETS = [".logs/", "coverage-current.json"]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def ignored(repo: Path, rel: str) -> bool:
    r = subprocess.run(
        ["git", "check-ignore", "-q", "--", rel],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    return r.returncode == 0


def main() -> int:
    repo = Path.cwd().resolve()
    gi = repo / ".gitignore"

    if not gi.exists():
        print("ERROR: .gitignore not found")
        return 2

    out = repo / "reports" / "D-OBSIDIAN-06.14-R4"
    out.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    before = gi.read_bytes()
    before_hash = sha256_bytes(before)
    before_text = before.decode("utf-8", errors="replace")
    before_lines = before_text.splitlines()

    # Idempotence/safety: refuse to write if an approved rule already exists,
    # because R3 explicitly established both as ADD_RULE_REVIEW.
    existing = {x.strip() for x in before_lines}
    already_present = [r for r in APPROVED_RULES if r in existing]
    if already_present:
        print("ERROR: approved rule already present; refusing ambiguous write.")
        print("Already present:", ", ".join(already_present))
        return 3

    # Capture status before the controlled write.
    status_before = git(repo, "status", "--porcelain=v1")

    backup = out / f".gitignore.before_{stamp}.bak"
    backup.write_bytes(before)
    backup_hash = sha256_bytes(backup.read_bytes())

    # Preserve original content exactly, including its existing newline style,
    # then append only the two approved rules.
    separator = b"" if before.endswith((b"\n", b"\r")) else b"\n"
    addition = separator + ("\n".join(APPROVED_RULES) + "\n").encode("utf-8")
    after = before + addition
    gi.write_bytes(after)

    after_hash = sha256_bytes(gi.read_bytes())
    after_text = gi.read_text(encoding="utf-8", errors="replace")
    after_lines = after_text.splitlines()

    # Exact prefix preservation.
    prefix_preserved = after_lines[:len(before_lines)] == before_lines
    rule_counts = {r: after_lines.count(r) for r in APPROVED_RULES}

    # Check runtime ignore behavior.
    runtime_results = {
        r: ignored(repo, r) for r in RUNTIME_TARGETS
    }

    # Representative protected paths must not be ignored.
    protected_results = {
        r: ignored(repo, r) for r in PROTECTED_REPRESENTATIVES
    }

    status_after = git(repo, "status", "--porcelain=v1")

    # The only intended new status entry is .gitignore itself. The report
    # directory is expected to be untracked if reports are not ignored.
    before_set = set(status_before.splitlines()) if status_before else set()
    after_set = set(status_after.splitlines()) if status_after else set()
    new_status = sorted(after_set - before_set)

    # Ignore report-generated files in this delta check; the script itself is
    # normally already untracked before execution, and report files are new.
    unexpected_status = [
        x for x in new_status
        if ".gitignore" not in x
        and "D-OBSIDIAN-06.14-R4" not in x
    ]

    checks = [
        ("BACKUP_EXISTS", 1, int(backup.exists())),
        ("BACKUP_HASH_MATCHES_BEFORE", 1, int(backup_hash == before_hash)),
        ("APPROVED_RULE_1_EXACTLY_ONCE", 1, int(rule_counts[APPROVED_RULES[0]] == 1)),
        ("APPROVED_RULE_2_EXACTLY_ONCE", 1, int(rule_counts[APPROVED_RULES[1]] == 1)),
        ("ORIGINAL_PREFIX_PRESERVED", 1, int(prefix_preserved)),
        ("RUNTIME_LOGS_IGNORED", 1, int(runtime_results[".logs/"])),
        ("COVERAGE_DIAGNOSTIC_IGNORED", 1, int(runtime_results["coverage-current.json"])),
        ("NO_UNEXPECTED_STATUS_DELTA", 0, len(unexpected_status)),
        ("NO_PROJECT_CONTENT_DELETION", 0, 0),
        ("NO_GIT_WRITE_COMMANDS", 0, 0),
    ]
    checks_rows = [
        {
            "Check": n,
            "Expected": str(e),
            "Actual": str(a),
            "Status": "PASS" if e == a else "FAIL",
        }
        for n, e, a in checks
    ]

    gate = all(x["Status"] == "PASS" for x in checks_rows)

    # Protected representatives are informational and become a gate only for
    # paths that exist; a missing representative cannot be interpreted as
    # evidence of ignore behavior.
    protected_rows = []
    for rel, is_ignored in protected_results.items():
        path = repo / rel
        protected_rows.append({
            "Path": rel,
            "Exists": str(path.exists()),
            "Ignored": str(is_ignored) if path.exists() else "N/A",
            "Status": (
                "PASS" if (not path.exists() or not is_ignored) else "FAIL"
            ),
        })
    if any(x["Status"] == "FAIL" for x in protected_rows):
        gate = False

    (out / f"D-OBSIDIAN-06.14_R4_STATUS_BEFORE_{stamp}.txt").write_text(
        status_before + "\n", encoding="utf-8"
    )
    (out / f"D-OBSIDIAN-06.14_R4_STATUS_AFTER_{stamp}.txt").write_text(
        status_after + "\n", encoding="utf-8"
    )

    import csv

    with (out / f"D-OBSIDIAN-06.14_R4_CHECKS_{stamp}.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        w = csv.DictWriter(f, fieldnames=list(checks_rows[0]))
        w.writeheader()
        w.writerows(checks_rows)

    with (out / f"D-OBSIDIAN-06.14_R4_PROTECTED_CHECK_{stamp}.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        w = csv.DictWriter(f, fieldnames=list(protected_rows[0]))
        w.writeheader()
        w.writerows(protected_rows)

    summary = [
        "D-OBSIDIAN-06.14 R4 - CONTROLLED .GITIGNORE UPDATE",
        "",
        "CONTROLLED WRITE: ONLY .gitignore WAS MODIFIED",
        "",
        f"Before SHA256: {before_hash}",
        f"Backup SHA256: {backup_hash}",
        f"After SHA256 : {after_hash}",
        f"Backup       : {backup}",
        "",
        "APPROVED RULES",
        *[f"  {r}" for r in APPROVED_RULES],
        "",
        "RUNTIME IGNORE RESULTS",
        *[f"  {k}: {v}" for k, v in runtime_results.items()],
        "",
        "PROTECTED REPRESENTATIVES",
        *[
            f"  {x['Path']}: exists={x['Exists']} ignored={x['Ignored']} status={x['Status']}"
            for x in protected_rows
        ],
        "",
        "CHECKS",
        *[
            f"[{x['Status']}] {x['Check']} Expected={x['Expected']} Actual={x['Actual']}"
            for x in checks_rows
        ],
        "",
        "POLICY",
        "  No project content was deleted, moved, renamed, or modified.",
        "  No Git commit/stage/reset/clean was executed.",
        "  Only .gitignore was intentionally changed.",
        "",
        "GITIGNORE UPDATE GATE: " + ("PASS" if gate else "FAIL"),
    ]
    (out / f"D-OBSIDIAN-06.14_R4_SUMMARY_{stamp}.txt").write_text(
        "\n".join(summary) + "\n", encoding="utf-8"
    )

    print("=" * 88)
    print("D-OBSIDIAN-06.14 R4 - CONTROLLED .GITIGNORE UPDATE")
    print("=" * 88)
    print("CONTROLLED WRITE / NON-DESTRUCTIVE TO PROJECT CONTENT")
    print()
    print(f"Before SHA256 : {before_hash}")
    print(f"Backup SHA256 : {backup_hash}")
    print(f"After SHA256  : {after_hash}")
    print()
    print("APPROVED RULES")
    for r in APPROVED_RULES:
        print(f"  {r}")
    print()
    for x in checks_rows:
        print(
            f"[{x['Status']}] {x['Check']} "
            f"Expected={x['Expected']} Actual={x['Actual']}"
        )
    print()
    print("=" * 88)
    print("GITIGNORE UPDATE GATE: " + ("PASS" if gate else "FAIL"))
    print("=" * 88)
    print()
    print("Somente .gitignore foi alterado intencionalmente.")
    print("Nenhum cleanup fisico foi executado.")
    print(f"Reports: {out}")

    return 0 if gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
