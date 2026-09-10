from __future__ import annotations
import subprocess, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "reports" / "D-OBSIDIAN-06.14-R5"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
REPORT = REPORT_DIR / "D-OBSIDIAN-06.14-R5_FULL_REGRESSION_BASELINE_READINESS.txt"

CRITICAL_FILES = [
    ROOT / "src/iip/intelligence/metric_identity.py",
    ROOT / "src/iip/intelligence/metric_persistence.py",
    ROOT / "src/iip/intelligence/metric_persistence_adapter.py",
]
PROTECTED_DIRS = [
    ROOT / "tests/integration", ROOT / "tests/intelligence",
    ROOT / "vault", ROOT / "data", ROOT / "archive",
]

def run(cmd):
    p = subprocess.run(cmd, cwd=ROOT, text=True, encoding="utf-8",
                       errors="replace", capture_output=True)
    return p.returncode, p.stdout + p.stderr

def status():
    p = subprocess.run(["git", "status", "--porcelain=v1", "-z"],
                       cwd=ROOT, capture_output=True)
    raw = p.stdout.decode("utf-8", errors="surrogateescape")
    return [x for x in raw.split("\0") if x]

def path_of(x):
    return x[3:] if len(x) >= 4 else x

def check_gitignore():
    p = ROOT / ".gitignore"
    if not p.exists(): return False, ["missing .gitignore"]
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    bad = [r for r in [".logs/", "coverage-current.json"] if lines.count(r) != 1]
    return not bad, bad

def check_ignored():
    bad = []
    for item in [".logs/", "coverage-current.json"]:
        code, _ = run(["git", "check-ignore", "-q", "--", item])
        if code != 0: bad.append(item)
    return not bad, bad

print("=" * 88)
print("D-OBSIDIAN-06.14 R5 - FULL REGRESSION + BASELINE READINESS")
print("=" * 88)
print("READ-ONLY\n")

started = datetime.now().isoformat(timespec="seconds")
before = status()
_, branch = run(["git", "branch", "--show-current"])
_, head = run(["git", "rev-parse", "HEAD"])
_, tracked = run(["git", "ls-files"])
tracked_count = len([x for x in tracked.splitlines() if x.strip()])

print(f"Branch : {branch.strip()}")
print(f"HEAD   : {head.strip()}")
print(f"Tracked: {tracked_count}")
print(f"Status : {len(before)}\n")

critical_bad = [str(p.relative_to(ROOT)) for p in CRITICAL_FILES if not p.is_file()]
protected_bad = [str(p.relative_to(ROOT)) for p in PROTECTED_DIRS if not p.is_dir()]
gi_ok, gi_bad = check_gitignore()
rt_ok, rt_bad = check_ignored()

print(f"[{'PASS' if not critical_bad else 'FAIL'}] Critical files: {len(CRITICAL_FILES)-len(critical_bad)}/{len(CRITICAL_FILES)}")
print(f"[{'PASS' if not protected_bad else 'FAIL'}] Protected trees: {len(PROTECTED_DIRS)-len(protected_bad)}/{len(PROTECTED_DIRS)}")
print(f"[{'PASS' if gi_ok else 'FAIL'}] .gitignore approved rules")
print(f"[{'PASS' if rt_ok else 'FAIL'}] Runtime ignore checks\n")

print("FULL REGRESSION: pytest -q --disable-warnings --maxfail=0")
print("-" * 88)
pytest_code, pytest_out = run([sys.executable, "-m", "pytest", "-q",
                               "--disable-warnings", "--maxfail=0"])
print(pytest_out)

print("\nCOVERAGE: pytest --cov=src/iip --cov-report=term-missing")
cov_code, cov_out = run([sys.executable, "-m", "pytest", "--cov=src/iip",
                         "--cov-report=term-missing", "-q",
                         "--disable-warnings", "--maxfail=0"])
print(cov_out)

after = status()
before_paths = {path_of(x) for x in before}
new_paths = sorted({path_of(x) for x in after} - before_paths)
self_name = Path(__file__).name
unexpected = [p for p in new_paths
              if p != self_name and not p.startswith("reports/D-OBSIDIAN-06.14-R5/")]

print("\nPOST-REGRESSION STATUS")
print(f"  Status entries: {len(after)}")
print(f"  New paths: {len(new_paths)}")
for p in unexpected[:50]:
    print(f"    UNEXPECTED: {p}")

gates = {
    "FULL_REGRESSION_RETURN_CODE": pytest_code == 0,
    "COVERAGE_RETURN_CODE": cov_code == 0,
    "CRITICAL_FILES": not critical_bad,
    "PROTECTED_TREES": not protected_bad,
    "GITIGNORE": gi_ok,
    "RUNTIME_IGNORES": rt_ok,
    "NO_UNEXPECTED_NEW_STATUS": not unexpected,
}
all_pass = all(gates.values())

print("\nBASELINE READINESS GATE")
print("-" * 88)
for k, v in gates.items():
    print(f"[{'PASS' if v else 'FAIL'}] {k}")
print(f"\nBASELINE READINESS GATE: {'PASS' if all_pass else 'FAIL'}")

report = [
    "D-OBSIDIAN-06.14 R5 - FULL REGRESSION + BASELINE READINESS",
    f"Timestamp: {started}", "Mode: READ-ONLY",
    f"Branch: {branch.strip()}", f"HEAD: {head.strip()}",
    f"Tracked files: {tracked_count}", f"Status before: {len(before)}",
    "",
    "FULL REGRESSION OUTPUT:", pytest_out,
    "",
    "COVERAGE OUTPUT:", cov_out,
    "",
    f"Status after: {len(after)}",
    f"New paths: {new_paths}",
    f"Unexpected new paths: {unexpected}",
    "",
    "BASELINE READINESS GATE:",
]
report += [f"[{'PASS' if v else 'FAIL'}] {k}" for k, v in gates.items()]
report += [f"BASELINE READINESS GATE: {'PASS' if all_pass else 'FAIL'}",
           "", "NO GIT WRITE OPERATIONS PERFORMED."]
REPORT.write_text("\n".join(report), encoding="utf-8")

print(f"\nReport: {REPORT}")
raise SystemExit(0 if all_pass else 1)
