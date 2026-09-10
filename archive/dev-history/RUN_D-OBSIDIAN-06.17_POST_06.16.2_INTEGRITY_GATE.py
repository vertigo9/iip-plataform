from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from datetime import datetime

EXPECTED_BRANCH = "v2.1"
CORRECTIVE_COMMIT = "b177732"
CORRECTIVE_SUBJECT = "fix(iip): version critical intelligence architecture"
CRITICAL_FILES = [
    "src/iip/intelligence/metric_identity.py",
    "src/iip/intelligence/metric_persistence.py",
    "src/iip/intelligence/metric_persistence_adapter.py",
]
REPORT_DIR = Path("reports") / "D-OBSIDIAN-06.17"
REPORT = REPORT_DIR / "D-OBSIDIAN-06.17_POST_06.16.2_INTEGRITY_GATE.txt"


def run(*args: str) -> tuple[int, str, str]:
    p = subprocess.run(args, text=True, capture_output=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def git(*args: str) -> tuple[int, str, str]:
    return run("git", *args)


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    failures = 0

    def check(label: str, ok: bool, detail: str = ""):
        nonlocal failures
        tag = "PASS" if ok else "FAIL"
        print(f"  [{tag}] {label}" + (f" — {detail}" if detail else ""))
        lines.append(f"[{tag}] {label}" + (f" — {detail}" if detail else ""))
        if not ok:
            failures += 1

    print("=" * 100)
    print("D-OBSIDIAN-06.17 — POST-06.16.2 INTEGRITY / REGRESSION GATE")
    print("=" * 100)

    rc, branch, err = git("branch", "--show-current")
    check("BRANCH_V2_1", rc == 0 and branch == EXPECTED_BRANCH, branch or err)

    rc, head, err = git("rev-parse", "HEAD")
    check("HEAD_IS_06_16_2_OR_LATER", rc == 0 and head.startswith(CORRECTIVE_COMMIT), head or err)

    rc, subject, err = git("log", "-1", "--pretty=%s")
    check("HEAD_SUBJECT", rc == 0 and subject == CORRECTIVE_SUBJECT, subject or err)

    rc, tracked, err = git("ls-files", "--error-unmatch", *CRITICAL_FILES)
    check("ALL_CRITICAL_FILES_TRACKED", rc == 0, "all 3 critical intelligence modules tracked")

    for path in CRITICAL_FILES:
        p = Path(path)
        check(f"PRESENT:{path}", p.is_file(), str(p))

    rc, staged, err = git("diff", "--cached", "--name-only")
    check("NO_STAGED_CHANGES", rc == 0 and not staged, staged or "clean index")

    rc, diff, err = git("diff", "--name-only")
    check("NO_WORKTREE_MODIFICATION_TO_CRITICAL", rc == 0 and not any(x in diff.splitlines() for x in CRITICAL_FILES),
          "critical files unchanged" if rc == 0 else err)

    rc, files, err = git("show", "--format=", "--name-only", CORRECTIVE_COMMIT)
    changed = [x for x in files.splitlines() if x]
    check("06_16_2_COMMIT_SCOPE_EXACT", rc == 0 and sorted(changed) == sorted(CRITICAL_FILES),
          ", ".join(changed))

    print("\nRUNNING FULL REGRESSION...")
    rc, pytest_out, pytest_err = run(sys.executable, "-m", "pytest", "-q")
    check("PYTEST_EXIT_0", rc == 0, f"returncode={rc}")
    print(pytest_out)
    if pytest_err:
        print(pytest_err)

    # Parse the final pytest summary without relying on locale-specific wording.
    summary = ""
    for line in reversed(pytest_out.splitlines()):
        if "passed" in line and "in " in line:
            summary = line
            break
    check("PYTEST_EXPECTED_872_PLUS", "872 passed" in summary,
          summary or "pytest summary not detected")

    now = datetime.now().isoformat(timespec="seconds")
    report_lines = [
        "D-OBSIDIAN-06.17 — POST-06.16.2 INTEGRITY / REGRESSION GATE",
        f"Timestamp: {now}",
        f"Branch: {branch}",
        f"HEAD: {head}",
        f"06.16.2 corrective commit: {CORRECTIVE_COMMIT}",
        "",
        *lines,
        "",
        "PYTEST OUTPUT",
        pytest_out,
        "",
        f"FINAL GATE: {'PASS' if failures == 0 else 'FAIL'}",
    ]
    REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"\nReport: {REPORT.resolve()}")
    if failures:
        print(f"\nD-OBSIDIAN-06.17: FAIL ({failures} checks)")
        return 2

    print("\nD-OBSIDIAN-06.17: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
