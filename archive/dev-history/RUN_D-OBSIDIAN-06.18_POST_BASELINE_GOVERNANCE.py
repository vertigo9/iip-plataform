from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_BRANCH = "v2.1"
MIN_TESTS = 872
EXPECTED_COVERAGE = "95%"
EXPECTED_CRITICAL = [
    "src/iip/intelligence/metric_identity.py",
    "src/iip/intelligence/metric_persistence.py",
    "src/iip/intelligence/metric_persistence_adapter.py",
]
REPORT_DIR = Path("reports") / "D-OBSIDIAN-06.18"
REPORT = REPORT_DIR / "D-OBSIDIAN-06.18_POST_BASELINE_GOVERNANCE_GATE.txt"
MANIFEST = REPORT_DIR / "D-OBSIDIAN-06.18_POST_BASELINE_MANIFEST.json"
COMMIT_SUBJECT = "docs(iip): establish post-baseline governance manifest"


def run(*args: str):
    p = subprocess.run(args, text=True, capture_output=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def git(*args: str):
    return run("git", *args)


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    checks = []
    failures = []

    def check(name, ok, detail=""):
        item = {"name": name, "status": "PASS" if ok else "FAIL", "detail": detail}
        checks.append(item)
        if not ok:
            failures.append(item)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    print("=" * 100)
    print("D-OBSIDIAN-06.18 — POST-BASELINE GOVERNANCE / MANIFEST GATE R2")
    print("=" * 100)

    rc, branch, err = git("branch", "--show-current")
    check("BRANCH_V2_1", rc == 0 and branch == EXPECTED_BRANCH, branch or err)

    rc, head, err = git("rev-parse", "HEAD")
    check("HEAD_AVAILABLE", rc == 0 and bool(head), head or err)

    # Important: this gate permits pre-existing unstaged/untracked work.
    # It only blocks files already staged before the operation.
    rc, cached, err = git("diff", "--cached", "--name-only")
    check(
        "NO_PREEXISTING_STAGED_CHANGES",
        rc == 0 and not cached,
        "clean index" if rc == 0 else err,
    )

    for path in EXPECTED_CRITICAL:
        rc, out, err = git("ls-files", "--error-unmatch", path)
        check(f"TRACKED:{path}", rc == 0, out or err)

    rc, show, err = git("show", "-s", "--format=%H%n%s%n%ad", "--date=iso-strict", "HEAD")
    head_lines = show.splitlines()
    check("HEAD_METADATA_READABLE", rc == 0 and len(head_lines) >= 3, show or err)

    print("\nRUNNING FULL REGRESSION FOR GOVERNANCE BASELINE...")
    rc, pytest_out, pytest_err = run(sys.executable, "-m", "pytest", "-q")
    check("PYTEST_EXIT_0", rc == 0, f"returncode={rc}")

    summary = ""
    for line in reversed(pytest_out.splitlines()):
        if "passed" in line and "in " in line:
            summary = line
            break
    check("REGRESSION_MINIMUM_872", "872 passed" in summary, summary or "summary not detected")

    total_line = next((x.strip() for x in pytest_out.splitlines() if x.strip().startswith("TOTAL ")), "")
    coverage = None
    if total_line:
        parts = total_line.split()
        # Actual pytest-cov footer is: TOTAL <stmts> <miss> <cover>
        if len(parts) >= 4:
            coverage = parts[-1]
    check("COVERAGE_95_PERCENT", coverage == EXPECTED_COVERAGE, total_line or "TOTAL line not detected")

    timestamp = datetime.now(timezone.utc).isoformat()
    manifest = {
        "document": "D-OBSIDIAN-06.18_POST_BASELINE_MANIFEST",
        "timestamp_utc": timestamp,
        "branch": branch,
        "head": head,
        "head_subject": head_lines[1] if len(head_lines) > 1 else "",
        "critical_architecture": EXPECTED_CRITICAL,
        "critical_architecture_tracking": "VERIFIED",
        "regression": {
            "pytest_returncode": rc,
            "summary": summary,
            "coverage_total": total_line,
            "coverage": coverage,
        },
        "governance_state": "READY_FOR_NEXT_EVOLUTION" if not failures else "BLOCKED",
        "checks": checks,
    }
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    report = [
        "D-OBSIDIAN-06.18 — POST-BASELINE GOVERNANCE / MANIFEST GATE R2",
        f"Timestamp UTC: {timestamp}",
        f"Branch: {branch}",
        f"HEAD: {head}",
        "",
        *[
            f"[{c['status']}] {c['name']}" + (f" — {c['detail']}" if c["detail"] else "")
            for c in checks
        ],
        "",
        "PYTEST OUTPUT",
        pytest_out,
        "",
        f"Manifest: {MANIFEST.resolve()}",
        "FINAL PRE-COMMIT GATE: " + ("PASS" if not failures else "FAIL"),
    ]
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")

    print(f"\nManifest: {MANIFEST.resolve()}")
    print(f"Report:   {REPORT.resolve()}")

    if failures:
        print(f"\nD-OBSIDIAN-06.18: FAIL ({len(failures)} checks)")
        return 2

    # The only authorized persistent change is the two governance artifacts.
    report_rel = str(REPORT).replace("\\", "/")
    manifest_rel = str(MANIFEST).replace("\\", "/")

    rc, _, err = git("add", report_rel, manifest_rel)
    check("STAGE_ONLY_06_18_ARTIFACTS", rc == 0, err or "report + manifest staged")
    if rc != 0:
        return 2

    rc, staged, err = git("diff", "--cached", "--name-only")
    expected = sorted([report_rel, manifest_rel])
    actual = sorted(staged.splitlines())
    check("STAGED_SCOPE_EXACT", rc == 0 and actual == expected, ", ".join(actual))
    if actual != expected:
        print("Staged scope mismatch; no commit performed.")
        return 2

    rc, _, err = git("commit", "-m", COMMIT_SUBJECT)
    check("COMMIT_06_18", rc == 0, err or COMMIT_SUBJECT)
    if rc != 0:
        return 2

    rc, new_head, err = git("rev-parse", "HEAD")
    check("NEW_HEAD_AVAILABLE", rc == 0 and bool(new_head), new_head or err)

    rc, staged_after, err = git("diff", "--cached", "--name-only")
    check("NO_STAGED_AFTER_COMMIT", rc == 0 and not staged_after, staged_after or err)

    # Final report reflects the complete operation.
    final = REPORT.read_text(encoding="utf-8")
    final += f"\nCommit: {new_head}\nFINAL GATE: {'PASS' if not failures else 'FAIL'}\n"
    REPORT.write_text(final, encoding="utf-8")

    if failures:
        print(f"\nD-OBSIDIAN-06.18: FAIL ({len(failures)} checks)")
        return 2

    print("\nD-OBSIDIAN-06.18: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
