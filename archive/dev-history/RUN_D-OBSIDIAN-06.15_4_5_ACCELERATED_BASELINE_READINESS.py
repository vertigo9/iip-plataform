from __future__ import annotations

import hashlib
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "reports" / "D-OBSIDIAN-06.15.4-5"
OUT.mkdir(parents=True, exist_ok=True)
REPORT = OUT / "D-OBSIDIAN-06.15.4-5_ACCELERATED_BASELINE_READINESS.txt"
MANIFEST = OUT / "D-OBSIDIAN-06.15.4_EXPLICIT_BASELINE_MANIFEST.txt"

PROTECTED = (
    "src/iip/intelligence/metric_identity.py",
    "src/iip/intelligence/metric_persistence.py",
    "src/iip/intelligence/metric_persistence_adapter.py",
    "tests/integration",
    "tests/intelligence",
    "vault",
    "data",
    "archive",
)

def run(args):
    p = subprocess.run(args, cwd=ROOT, capture_output=True)
    return p.returncode, p.stdout.decode("utf-8", errors="replace"), p.stderr.decode("utf-8", errors="replace")

def status_z():
    p = subprocess.run(["git", "status", "--porcelain=v1", "-z"], cwd=ROOT, capture_output=True)
    raw = p.stdout.decode("utf-8", errors="surrogateescape")
    return [x for x in raw.split("\0") if x]

def path_of(e):
    return e[3:] if len(e) >= 4 else e

def norm(p):
    p = p.replace("\\", "/").strip().strip('"')
    while p.startswith("./"):
        p = p[2:]
    return p.lower()

def digest(p):
    if not p.is_file():
        return "MISSING"
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1024 * 1024), b""):
            h.update(c)
    return h.hexdigest()

def category(p):
    n = norm(p)
    if n.startswith("src/"): return "SOURCE"
    if n.startswith("tests/"): return "TEST"
    if n.startswith("vault/"): return "VAULT"
    if n.startswith("data/"): return "DATA"
    if n.startswith("archive/"): return "ARCHIVE"
    if n.startswith("reports/"): return "REPORT"
    if n.startswith("scripts/"): return "SCRIPT"
    if n.startswith("run_d-obsidian-06."): return "PROCEDURAL"
    if n.startswith(".logs/") or n in {".coverage", "coverage-current.json"}: return "RUNTIME"
    return "OTHER"

def protected(p):
    n = norm(p)
    return any(n == x.lower() or n.startswith(x.lower().rstrip("/") + "/") for x in PROTECTED)

def discover_historical_text():
    roots = [ROOT / "reports", ROOT / "archive"]
    tags = ("D-OBSIDIAN-06.8", "D-OBSIDIAN-06.9", "D-OBSIDIAN-06.10",
            "D-OBSIDIAN-06.11", "D-OBSIDIAN-06.12", "D-OBSIDIAN-06.13")
    files = []
    for base in roots:
        if base.exists():
            for p in base.rglob("*"):
                if p.is_file() and any(t in str(p).upper() for t in tags):
                    files.append(p)
    return sorted(set(files))

def historical_refs():
    refs = set()
    for p in discover_historical_text():
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for line in text.splitlines():
            s = line.strip().strip('"')
            for prefix in ("src/", "tests/", "vault/", "data/", "archive/"):
                low = s.lower()
                pos = low.find(prefix)
                if pos >= 0:
                    token = s[pos:].split("|")[0].split("  ")[0].strip().strip('"')
                    token = token.rstrip("),;:")
                    if "." in token:
                        refs.add(norm(token))
    return refs

print("=" * 100)
print("D-OBSIDIAN-06.15.4 + 06.15.5 - ACCELERATED BASELINE READINESS")
print("=" * 100)
print("READ-ONLY — NO GIT WRITE")
print()

_, branch, _ = run(["git", "branch", "--show-current"])
_, head, _ = run(["git", "rev-parse", "HEAD"])
_, tracked_out, _ = run(["git", "ls-files"])
tracked = {norm(x) for x in tracked_out.splitlines() if x.strip()}
status = status_z()

modified, deleted, untracked = [], [], []
for e in status:
    xy, p = e[:2], path_of(e)
    if xy == "??":
        untracked.append(p)
    elif "D" in xy:
        deleted.append((xy, p))
    elif xy.strip():
        modified.append((xy, p))

refs = historical_refs()
rows = []

for xy, p in modified:
    rows.append((p, "REVIEW-BLOCKED", "TRACKED-MODIFIED", f"tracked status={xy}"))

for xy, p in deleted:
    rows.append((p, "REVIEW-BLOCKED", "TRACKED-DELETION", f"tracked deletion={xy}"))

for p in untracked:
    n, cat = norm(p), category(p)
    if n.startswith("reports/d-obsidian-06.15.4-5/"):
        dec, reason = "OUTSIDE-BASELINE", "current procedural evidence"
    elif n.startswith("run_d-obsidian-06."):
        dec, reason = "OUTSIDE-BASELINE", "procedural diagnostic"
    elif cat == "RUNTIME":
        dec, reason = "OUTSIDE-BASELINE", "runtime/generated"
    elif protected(p):
        dec, reason = "PROTECTED-REVIEW", "protected tree"
    elif any(x in n for x in ("backup", "legacy", "old", "copy", "duplicate", "(1)", "(2)")):
        dec, reason = "REVIEW-BLOCKED", "possible historical/duplicate"
    elif n in refs:
        dec, reason = "REVIEW-BLOCKED", "historical evidence reference"
    elif cat in {"SOURCE", "TEST", "VAULT", "DATA", "ARCHIVE"}:
        dec, reason = "CANDIDATE", "structural content; explicit approval still required"
    else:
        dec, reason = "REVIEW-BLOCKED", "unclassified/other"
    rows.append((p, dec, cat, reason))

counts = Counter(r[1] for r in rows)
candidates = [r for r in rows if r[1] == "CANDIDATE"]

# Candidate safety checks
candidate_checks = []
for p, dec, cat, reason in candidates:
    fp = ROOT / p
    d = digest(fp)
    ok_exists = fp.exists()
    ok_hash = d not in {"MISSING", "DIRECTORY"}
    ok_tracked = norm(p) not in tracked
    ok_no_runtime = cat != "RUNTIME"
    ok_no_proc = cat != "PROCEDURAL"
    candidate_checks.append((p, ok_exists and ok_hash and ok_tracked and ok_no_runtime and ok_no_proc, d))

# Duplicate groups among candidates
hash_groups = defaultdict(list)
for p, ok, d in candidate_checks:
    if ok:
        hash_groups[d].append(p)
dup_groups = [v for v in hash_groups.values() if len(v) > 1]

# Explicit approval remains zero: this script only prepares the manifest.
approved = []
eligible = [x for x in candidate_checks if x[1]]
blocked_candidates = [x for x in candidate_checks if not x[1]]

print(f"Branch: {branch.strip()}")
print(f"HEAD: {head.strip()}")
print(f"Status: {len(status)}")
print(f"Modified: {len(modified)}")
print(f"Deleted: {len(deleted)}")
print(f"Untracked: {len(untracked)}")
print()
print("DECISION DISTRIBUTION")
for k in sorted(counts):
    print(f"  {k:30} {counts[k]}")
print()
print(f"Candidate paths: {len(candidates)}")
print(f"Candidate safety-eligible: {len(eligible)}")
print(f"Candidate safety-blocked: {len(blocked_candidates)}")
print(f"Candidate duplicate groups: {len(dup_groups)}")
print(f"Explicitly approved paths: {len(approved)}")
print()

print("PRE-STAGING SAFETY")
checks = {
    "HEAD_PRESENT": bool(head.strip()),
    "STATUS_READ": len(status) >= 0,
    "PROTECTED_PATHS_EXIST": all((ROOT / p).exists() for p in PROTECTED),
    "NO_CANDIDATE_DUPLICATE_GROUPS": len(dup_groups) == 0,
    "NO_CANDIDATE_SAFETY_BLOCKS": len(blocked_candidates) == 0,
    "NO_AUTO_APPROVAL": len(approved) == 0,
    "NO_GIT_WRITE": True,
}
for k, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")

# Explicit manifest: candidates are listed as PENDING_APPROVAL, never approved.
lines = [
    "D-OBSIDIAN-06.15.4 - EXPLICIT BASELINE MANIFEST",
    f"Timestamp: {datetime.now().isoformat(timespec='seconds')}",
    "Mode: READ-ONLY",
    "IMPORTANT: No path is approved for git staging by this file.",
    "",
    "PENDING_APPROVAL PATHS:",
]
for p, ok, d in sorted(candidate_checks, key=lambda x: norm(x[0])):
    lines.append(f"{'PENDING-APPROVAL' if ok else 'BLOCKED'} | {p} | SHA256={d}")

lines += [
    "",
    "RULE:",
    "Only a later explicit authorization step may change PENDING-APPROVAL to APPROVED-BASELINE.",
    "No Git staging or commit was performed.",
]
MANIFEST.write_text("\n".join(lines), encoding="utf-8")

report = [
    "D-OBSIDIAN-06.15.4 + 06.15.5 - ACCELERATED BASELINE READINESS",
    f"Timestamp: {datetime.now().isoformat(timespec='seconds')}",
    "Mode: READ-ONLY — NO GIT WRITE",
    f"Branch: {branch.strip()}",
    f"HEAD: {head.strip()}",
    f"Status: {len(status)}",
    f"Modified: {len(modified)}",
    f"Deleted: {len(deleted)}",
    f"Untracked: {len(untracked)}",
    "",
    "DECISION DISTRIBUTION:",
]
report += [f"{k}: {counts[k]}" for k in sorted(counts)]
report += [
    "",
    f"Candidate paths: {len(candidates)}",
    f"Candidate safety-eligible: {len(eligible)}",
    f"Candidate safety-blocked: {len(blocked_candidates)}",
    f"Candidate duplicate groups: {len(dup_groups)}",
    "Explicitly approved paths: 0",
    "",
    "PRE-STAGING CHECKS:",
]
report += [f"[{'PASS' if v else 'FAIL'}] {k}" for k, v in checks.items()]
report += [
    "",
    "PENDING-APPROVAL PATHS:",
]
report += [f"{p} | SHA256={d}" for p, ok, d in sorted(candidate_checks, key=lambda x: norm(x[0]))]
report += [
    "",
    "DECISION:",
    "No Git staging authorization was created.",
    "If all gates pass, the next step may create a separate explicit authorization manifest.",
]
REPORT.write_text("\n".join(report), encoding="utf-8")

print()
print(f"Manifest: {MANIFEST}")
print(f"Report:   {REPORT}")
print()
print("ACCELERATED BASELINE READINESS: " + ("PASS" if all(checks.values()) else "FAIL"))
print("No Git staging authorization was created.")
