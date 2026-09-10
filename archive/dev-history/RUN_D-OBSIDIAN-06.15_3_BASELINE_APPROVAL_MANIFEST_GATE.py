from __future__ import annotations

import hashlib
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "reports" / "D-OBSIDIAN-06.15.3"
OUT.mkdir(parents=True, exist_ok=True)
REPORT = OUT / "D-OBSIDIAN-06.15.3_BASELINE_APPROVAL_MANIFEST_GATE.txt"

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
    p = subprocess.run(["git", "status", "--porcelain=v1", "-z"],
                       cwd=ROOT, capture_output=True)
    raw = p.stdout.decode("utf-8", errors="surrogateescape")
    return [x for x in raw.split("\0") if x]

def path_of(e):
    return e[3:] if len(e) >= 4 else e

def norm(p):
    p = p.replace("\\", "/").strip().strip('"')
    while p.startswith("./"):
        p = p[2:]
    return p.lower()

def is_protected(p):
    n = norm(p)
    return any(n == x.lower() or n.startswith(x.lower().rstrip("/") + "/")
               for x in PROTECTED)

def sha256(p):
    if not p.is_file():
        return "DIRECTORY" if p.exists() else "MISSING"
    h = hashlib.sha256()
    try:
        with p.open("rb") as f:
            for c in iter(lambda: f.read(1024 * 1024), b""):
                h.update(c)
        return h.hexdigest()
    except OSError:
        return "UNREADABLE"

# Reconstruct the exact conservative rules used by 06.15.2.
def category(p):
    n = norm(p)
    if n.startswith("reports/"): return "REPORT"
    if n.startswith("tests/"): return "TEST"
    if n.startswith("src/"): return "SOURCE"
    if n.startswith("vault/"): return "VAULT"
    if n.startswith("data/"): return "DATA"
    if n.startswith("archive/"): return "ARCHIVE"
    if n.startswith("scripts/"): return "SCRIPT"
    if n.startswith("run_d-obsidian-06."): return "PROCEDURAL"
    if n.startswith(".logs/") or n in {".coverage", "coverage-current.json"}: return "RUNTIME"
    return "OTHER"

def historical_reference_files():
    roots = [ROOT / "reports", ROOT / "archive"]
    tags = ("D-OBSIDIAN-06.8", "D-OBSIDIAN-06.9", "D-OBSIDIAN-06.10",
            "D-OBSIDIAN-06.11", "D-OBSIDIAN-06.12", "D-OBSIDIAN-06.13")
    out = []
    for base in roots:
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file() and any(t in str(p).upper() for t in tags):
                out.append(p)
    return sorted(set(out))

def evidence_references():
    # Deliberately conservative: exact normalized path strings only.
    refs = set()
    for p in historical_reference_files():
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for line in text.splitlines():
            s = line.strip().strip('"')
            for prefix in ("src/", "tests/", "vault/", "data/", "archive/", "reports/", "scripts/"):
                pos = s.lower().find(prefix)
                if pos >= 0:
                    token = s[pos:].split("|")[0].split("  ")[0].strip().strip('"').rstrip("),;")
                    if "." in token:
                        refs.add(norm(token))
    return refs

print("=" * 100)
print("D-OBSIDIAN-06.15.3 - BASELINE APPROVAL MANIFEST GATE")
print("=" * 100)
print("READ-ONLY — NO GIT WRITE")
print()

_, branch, _ = run(["git", "branch", "--show-current"])
_, head, _ = run(["git", "rev-parse", "HEAD"])
_, tracked_out, _ = run(["git", "ls-files"])
tracked = {norm(x) for x in tracked_out.splitlines() if x.strip()}
status = status_z()

modified = []
deleted = []
untracked = []

for e in status:
    xy = e[:2]
    p = path_of(e)
    if xy == "??":
        untracked.append(p)
    elif "D" in xy:
        deleted.append((xy, p))
    elif xy.strip():
        modified.append((xy, p))

refs = evidence_references()

# Explicit approval matrix. This gate does NOT stage anything.
rows = []

for xy, p in modified:
    rows.append((p, "REVIEW-BLOCKED", "TRACKED-MODIFIED",
                 f"tracked status {xy}; explicit baseline decision required"))

for xy, p in deleted:
    rows.append((p, "REVIEW-BLOCKED", "TRACKED-DELETION",
                 f"tracked deletion {xy}; no deletion authorization"))

for p in untracked:
    n = norm(p)
    cat = category(p)

    if n.startswith("reports/d-obsidian-06.15.3/"):
        decision = "OUTSIDE-BASELINE"
        reason = "current gate evidence"
    elif n.startswith("run_d-obsidian-06."):
        decision = "OUTSIDE-BASELINE"
        reason = "procedural diagnostic"
    elif cat == "RUNTIME":
        decision = "OUTSIDE-BASELINE"
        reason = "runtime/generated artifact"
    elif n in refs:
        decision = "REVIEW-BLOCKED"
        reason = "historical evidence reference"
    elif any(x in n for x in ("backup", "legacy", "old", "copy", "duplicate", "(1)", "(2)")):
        decision = "REVIEW-BLOCKED"
        reason = "possible historical/duplicate artifact"
    elif is_protected(p):
        decision = "PROTECTED-REVIEW"
        reason = "protected tree requires explicit reconciliation"
    elif cat in {"SOURCE", "TEST", "VAULT", "DATA", "ARCHIVE"}:
        decision = "CANDIDATE-REQUIRES-EXPLICIT-APPROVAL"
        reason = "structural content; not yet authorized"
    else:
        decision = "REVIEW-BLOCKED"
        reason = "unclassified/other"

    rows.append((p, decision, cat, reason))

counts = Counter(r[1] for r in rows)

# Candidate set is explicitly NOT an approval set.
candidates = [r for r in rows if r[1] == "CANDIDATE-REQUIRES-EXPLICIT-APPROVAL"]

print(f"Branch: {branch.strip()}")
print(f"HEAD: {head.strip()}")
print(f"Tracked: {len(tracked)}")
print(f"Status entries: {len(status)}")
print(f"Modified: {len(modified)}")
print(f"Deleted: {len(deleted)}")
print(f"Untracked: {len(untracked)}")
print(f"Historical evidence files: {len(historical_reference_files())}")
print(f"Historical exact-path references found: {len(refs)}")
print()
print("APPROVAL MATRIX")
for k in sorted(counts):
    print(f"  {k:42} {counts[k]}")
print()
print(f"Explicit approval candidates: {len(candidates)}")
print("Explicitly approved baseline paths: 0")
print()

print("PROTECTED PATHS")
for p in PROTECTED:
    print(f"  [{'PASS' if (ROOT / p).exists() else 'FAIL'}] {p}")
print()

# Duplicate hash groups among candidate files are highlighted as blockers.
hashes = defaultdict(list)
for p, decision, cat, reason in candidates:
    digest = sha256(ROOT / p)
    if digest not in {"MISSING", "UNREADABLE", "DIRECTORY"}:
        hashes[digest].append(p)
candidate_duplicate_groups = [v for v in hashes.values() if len(v) > 1]

print(f"Candidate duplicate hash groups: {len(candidate_duplicate_groups)}")
print()
print("GATE RULES")
print("  [PASS] Zero files are auto-approved")
print("  [PASS] Protected trees are not auto-approved")
print("  [PASS] Historical references are not auto-approved")
print("  [PASS] Tracked deletions remain blocked")
print("  [PASS] No Git write operation")
print()

lines = [
    "D-OBSIDIAN-06.15.3 - BASELINE APPROVAL MANIFEST GATE",
    f"Timestamp: {datetime.now().isoformat(timespec='seconds')}",
    "Mode: READ-ONLY — NO GIT WRITE",
    f"Branch: {branch.strip()}",
    f"HEAD: {head.strip()}",
    f"Tracked: {len(tracked)}",
    f"Status entries: {len(status)}",
    f"Modified: {len(modified)}",
    f"Deleted: {len(deleted)}",
    f"Untracked: {len(untracked)}",
    f"Historical exact-path references: {len(refs)}",
    "",
    "DECISION DISTRIBUTION:",
]
lines += [f"{k}: {counts[k]}" for k in sorted(counts)]
lines += [
    "",
    "EXPLICIT APPROVAL STATUS:",
    "APPROVED-BASELINE: 0",
    "CANDIDATE-REQUIRES-EXPLICIT-APPROVAL: " + str(len(candidates)),
    "",
    "MANIFEST:",
]
for p, decision, cat, reason in sorted(rows, key=lambda x: norm(x[0])):
    lines.append(f"{decision} | {cat} | {p} | {reason} | SHA256={sha256(ROOT / p)}")

lines += ["", "CANDIDATE FILES — REQUIRE EXPLICIT APPROVAL:"]
for p, decision, cat, reason in sorted(candidates, key=lambda x: norm(x[0])):
    lines.append(f"{p} | {cat} | SHA256={sha256(ROOT / p)}")

lines += ["", "CANDIDATE DUPLICATE HASH GROUPS — BLOCKED FROM AUTOMATIC APPROVAL:"]
for group in candidate_duplicate_groups:
    lines.append(f"HASH={sha256(ROOT / group[0])}")
    lines.extend(f"  {p}" for p in sorted(group))

lines += [
    "",
    "FINAL DECISION:",
    "NO FILE IS APPROVED FOR GIT STAGING BY THIS GATE.",
    "An explicit path-level approval manifest must be produced before staging.",
    "No Git add/commit/reset/clean/checkout/move/delete was executed.",
]

REPORT.write_text("\n".join(lines), encoding="utf-8")

checks = {
    "MANIFEST_ROWS_COMPLETE": len(rows) == len(status),
    "PROTECTED_PATHS_EXIST": all((ROOT / p).exists() for p in PROTECTED),
    "ZERO_AUTO_APPROVAL": counts.get("APPROVED-BASELINE", 0) == 0,
    "NO_GIT_WRITE": True,
    "REPORT_EXISTS": REPORT.exists(),
}

print("GATES")
for name, ok in checks.items():
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

print()
print(f"Report: {REPORT}")
print()
print("BASELINE APPROVAL MANIFEST GATE: " + ("PASS" if all(checks.values()) else "FAIL"))
print("No staging authorization was created.")
