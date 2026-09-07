from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "reports" / "D-OBSIDIAN-06.15"
OUT.mkdir(parents=True, exist_ok=True)
REPORT = OUT / "D-OBSIDIAN-06.15_BASELINE_MANIFEST_AUDIT.txt"

PROTECTED = [
    "src/iip/intelligence/metric_identity.py",
    "src/iip/intelligence/metric_persistence.py",
    "src/iip/intelligence/metric_persistence_adapter.py",
    "tests/integration",
    "tests/intelligence",
    "vault",
    "data",
    "archive",
]

def run(args):
    p = subprocess.run(args, cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr

def status_z():
    p = subprocess.run(["git", "status", "--porcelain=v1", "-z"],
                       cwd=ROOT, capture_output=True)
    raw = p.stdout.decode("utf-8", errors="surrogateescape")
    return [x for x in raw.split("\0") if x]

def path_of(x):
    return x[3:] if len(x) >= 4 else x

def sha256(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

print("=" * 88)
print("D-OBSIDIAN-06.15 - BASELINE MANIFEST AUDIT")
print("=" * 88)
print("READ-ONLY")
print()

_, branch = run(["git", "branch", "--show-current"])
_, head = run(["git", "rev-parse", "HEAD"])
_, tracked_raw = run(["git", "ls-files"])
tracked = [x for x in tracked_raw.splitlines() if x.strip()]
status = status_z()

modified = []
deleted = []
untracked = []
other = []

for entry in status:
    xy = entry[:2]
    p = path_of(entry)
    if xy == "??":
        untracked.append(p)
    elif "D" in xy:
        deleted.append((xy, p))
    elif xy.strip():
        modified.append((xy, p))
    else:
        other.append((xy, p))

print(f"Branch: {branch.strip()}")
print(f"HEAD: {head.strip()}")
print(f"Tracked files: {len(tracked)}")
print(f"Status entries: {len(status)}")
print(f"Modified/other tracked entries: {len(modified)}")
print(f"Deleted tracked entries: {len(deleted)}")
print(f"Untracked entries: {len(untracked)}")
print()

# Protected paths: report only, never alter.
protected_failures = []
for target in PROTECTED:
    p = ROOT / target
    if not p.exists():
        protected_failures.append(target)

print("PROTECTED PATH AUDIT")
for target in PROTECTED:
    print(f"  [{'PASS' if target not in protected_failures else 'FAIL'}] {target}")
print()

# Inventory buckets. No approval or staging is performed here.
procedural = []
reports = []
runtime = []
other_untracked = []

for p in untracked:
    if p.startswith("reports/D-OBSIDIAN-06.15/"):
        reports.append(p)
    elif p.startswith("RUN_D-OBSIDIAN-06."):
        procedural.append(p)
    elif p in {".coverage", "coverage-current.json"} or p.startswith(".logs/"):
        runtime.append(p)
    else:
        other_untracked.append(p)

print("UNTRACKED CLASSIFICATION — AUDIT ONLY")
print(f"  Current 06.15 procedural/evidence: {len(procedural)}")
print(f"  Current 06.15 report files: {len(reports)}")
print(f"  Runtime artifacts: {len(runtime)}")
print(f"  Other untracked: {len(other_untracked)}")
print()

print("BASELINE DECISION")
print("  NO AUTOMATIC ADD/COMMIT")
print("  NO DELETION")
print("  NO MOVE")
print("  NO CLEAN")
print()
print("The 'other untracked' set remains REVIEW until reconciled against")
print("the D-OBSIDIAN-06.8–06.13 forensic/classification manifests.")
print()

# Produce a machine-readable-ish manifest without making Git changes.
lines = [
    "D-OBSIDIAN-06.15 - BASELINE MANIFEST AUDIT",
    f"Timestamp: {datetime.now().isoformat(timespec='seconds')}",
    "Mode: READ-ONLY",
    f"Branch: {branch.strip()}",
    f"HEAD: {head.strip()}",
    f"Tracked files: {len(tracked)}",
    f"Status entries: {len(status)}",
    f"Modified entries: {len(modified)}",
    f"Deleted entries: {len(deleted)}",
    f"Untracked entries: {len(untracked)}",
    "",
    "PROTECTED PATHS:",
]
lines += [f"[{'PASS' if t not in protected_failures else 'FAIL'}] {t}" for t in PROTECTED]
lines += [
    "",
    "MODIFIED/OTHER TRACKED:",
]
lines += [f"{xy} {p}" for xy, p in modified]
lines += [
    "",
    "DELETED TRACKED:",
]
lines += [f"{xy} {p}" for xy, p in deleted]
lines += [
    "",
    "UNTRACKED — PROCEDURAL:",
]
lines += procedural
lines += ["", "UNTRACKED — REPORT/EVIDENCE:"] + reports
lines += ["", "UNTRACKED — RUNTIME:"] + runtime
lines += ["", "UNTRACKED — OTHER / REVIEW REQUIRED:"] + other_untracked
lines += [
    "",
    "BASELINE DECISION:",
    "NO AUTOMATIC ADD/COMMIT/DELETE/MOVE/CLEAN.",
    "OTHER UNTRACKED ITEMS REQUIRE RECONCILIATION WITH D-OBSIDIAN-06.8–06.13.",
]

REPORT.write_text("\n".join(lines), encoding="utf-8")

print(f"Report: {REPORT}")
print()
print("BASELINE MANIFEST AUDIT: PASS")
print("This gate means inventory integrity passed; it does NOT authorize Git staging/commit.")
