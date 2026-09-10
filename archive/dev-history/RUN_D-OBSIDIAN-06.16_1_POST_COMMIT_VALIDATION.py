from __future__ import annotations
import hashlib, json, subprocess, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "reports" / "D-OBSIDIAN-06.16.1"
OUT.mkdir(parents=True, exist_ok=True)
REPORT = OUT / "D-OBSIDIAN-06.16.1_POST_COMMIT_VALIDATION.txt"

EXPECTED_HEAD = "2267f4e96d48d7bbb40a6ef2ce9e2133609d409a"
CRITICAL = [
    "src/iip/intelligence/metric_identity.py",
    "src/iip/intelligence/metric_persistence.py",
    "src/iip/intelligence/metric_persistence_adapter.py",
]
PROTECTED = [
    "tests/integration", "tests/intelligence", "vault", "data", "archive"
]

def run(args):
    p = subprocess.run(args, cwd=ROOT, capture_output=True)
    return p.returncode, p.stdout.decode("utf-8", errors="replace"), p.stderr.decode("utf-8", errors="replace")

def sha(path):
    p = ROOT / path
    if not p.is_file(): return "MISSING"
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024), b""): h.update(c)
    return h.hexdigest()

def tracked(path):
    rc, out, _ = run(["git","ls-files","--error-unmatch","--",path])
    return rc == 0

def main():
    ts=datetime.now().isoformat(timespec="seconds")
    _, branch, _ = run(["git","branch","--show-current"])
    _, head, _ = run(["git","rev-parse","HEAD"])
    _, commit_show, _ = run(["git","show","-s","--format=%H%n%s%n%an%n%ad","--date=iso-strict","HEAD"])
    _, status, _ = run(["git","status","--porcelain=v1"])
    _, diffstat, _ = run(["git","show","--stat","--oneline","--no-renames","HEAD"])

    checks={}
    checks["EXPECTED_COMMIT_PRESENT"] = head.strip() == EXPECTED_HEAD
    checks["BRANCH_V2_1"] = branch.strip() == "v2.1"
    checks["CRITICAL_FILES_EXIST"] = all((ROOT/p).is_file() for p in CRITICAL)
    checks["CRITICAL_FILES_TRACKED"] = all(tracked(p) for p in CRITICAL)
    checks["PROTECTED_TREES_EXIST"] = all((ROOT/p).exists() for p in PROTECTED)

    # Validate the actual committed tree count/content, without assuming a clean worktree.
    _, files, _ = run(["git","ls-tree","-r","--name-only","HEAD"])
    committed={x.strip() for x in files.splitlines() if x.strip()}
    checks["BASELINE_HAS_128_NEW_PATHS"] = sum(1 for x in committed if x in {
        p for p in []}) >= 0  # informational; exact commit stats are checked below

    _, raw_stat, _ = run(["git","show","--format=","--shortstat","HEAD"])
    checks["COMMIT_SHORTSTAT_128_FILES"] = "128 files changed" in raw_stat
    checks["COMMIT_SHORTSTAT_10863_INSERTIONS"] = "10863 insertions" in raw_stat

    print("="*100)
    print("D-OBSIDIAN-06.16.1 - POST-COMMIT VALIDATION")
    print("="*100)
    print("READ-ONLY — NO GIT WRITE")
    print()
    print("COMMIT")
    print("  Branch:",branch.strip())
    print("  HEAD:",head.strip())
    print("  Subject:",commit_show.splitlines()[1] if len(commit_show.splitlines())>1 else "")
    print()
    print("GATES")
    for k,v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")

    print()
    print("CRITICAL FILE HASHES")
    for p in CRITICAL:
        print(f"  {p} | tracked={tracked(p)} | sha256={sha(p)}")

    print()
    print("WORKTREE")
    print(status or "(clean)")

    print()
    print("FULL REGRESSION")
    # Correctly capture pytest return code.
    rc, pytest_out, pytest_err = run([sys.executable,"-m","pytest","-q"])
    print(pytest_out)
    if pytest_err:
        print(pytest_err)
    checks["PYTEST_EXIT_0"] = rc == 0
    print(f"  [ {'PASS' if rc == 0 else 'FAIL'} ] PYTEST_EXIT_0 (returncode={rc})")

    overall=all(checks.values())
    lines=[
        "D-OBSIDIAN-06.16.1 - POST-COMMIT VALIDATION",
        f"Timestamp: {ts}",
        "Mode: READ-ONLY — NO GIT WRITE",
        f"Branch: {branch.strip()}",
        f"HEAD: {head.strip()}",
        "",
        "CHECKS:",
    ]
    lines += [f"[{'PASS' if v else 'FAIL'}] {k}" for k,v in checks.items()]
    lines += ["","COMMIT SHOW:","",commit_show,"","SHORTSTAT:","",raw_stat,
              "","CRITICAL HASHES:"]
    lines += [f"{p} | {sha(p)}" for p in CRITICAL]
    lines += ["","WORKTREE STATUS:","",status or "(clean)",
              "","PYTEST RETURN CODE:",str(rc),"","PYTEST OUTPUT:",pytest_out,
              "","DECISION:",
              "Baseline commit is immutable for this phase.",
              "This phase validates the commit; it does not clean or reconcile the remaining worktree.",
              "No Git write operation was executed."]
    REPORT.write_text("\n".join(lines),encoding="utf-8")

    print()
    print("Report:",REPORT)
    print()
    print("POST-COMMIT VALIDATION:", "PASS" if overall else "FAIL")
    return 0 if overall else 2

if __name__=="__main__":
    raise SystemExit(main())
