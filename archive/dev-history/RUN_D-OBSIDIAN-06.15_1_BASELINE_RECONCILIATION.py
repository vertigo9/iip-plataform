from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "reports" / "D-OBSIDIAN-06.15.1"
OUT.mkdir(parents=True, exist_ok=True)
REPORT = OUT / "D-OBSIDIAN-06.15.1_BASELINE_RECONCILIATION.txt"

PROTECTED_PREFIXES = (
    "src/iip/intelligence/metric_identity.py",
    "src/iip/intelligence/metric_persistence.py",
    "src/iip/intelligence/metric_persistence_adapter.py",
    "tests/integration",
    "tests/intelligence",
    "vault",
    "data",
    "archive",
)

REVIEW_BLOCKED_MARKERS = (
    "REVIEW-BLOCKED",
    "PRESERVE-PENDING-AUTHORIZATION",
    "PRESERVE",
    "REMOVE-CANDIDATE",
    "REVIEW-DUPLICATE",
)

def run(args):
    p = subprocess.run(args, cwd=ROOT, capture_output=True)
    return p.returncode, p.stdout.decode("utf-8", errors="replace"), p.stderr.decode("utf-8", errors="replace")

def status_z():
    p = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z"],
        cwd=ROOT, capture_output=True
    )
    raw = p.stdout.decode("utf-8", errors="surrogateescape")
    return [x for x in raw.split("\0") if x]

def status_path(entry):
    # Porcelain v1: XY + space + path. Rename/copy records may contain a second path.
    return entry[3:] if len(entry) >= 4 else entry

def norm(s):
    s = s.replace("\\", "/").strip().strip('"')
    while s.startswith("./"):
        s = s[2:]
    return s.lower()

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def is_protected(path):
    p = norm(path)
    return any(p == x.lower() or p.startswith(x.lower().rstrip("/") + "/")
               for x in PROTECTED_PREFIXES)

def classify_untracked(path):
    p = norm(path)
    if p.startswith("reports/d-obsidian-06.15.1/"):
        return "CURRENT_PROCEDURAL_EVIDENCE"
    if re.match(r"run_d-obsidian-06\.", p):
        return "PROCEDURAL_SCRIPT"
    if p.startswith(".logs/") or p in {".coverage", "coverage-current.json"}:
        return "RUNTIME"
    if p.startswith("reports/"):
        return "REPORT_OR_EVIDENCE"
    if p.startswith("tests/"):
        return "TEST"
    if p.startswith("src/"):
        return "SOURCE"
    if p.startswith("vault/"):
        return "VAULT_DATA"
    if p.startswith("data/"):
        return "DATA"
    if p.startswith("archive/"):
        return "ARCHIVE"
    if p.startswith("scripts/"):
        return "SCRIPT"
    return "OTHER"

def discover_prior_evidence():
    roots = [
        ROOT / "reports",
        ROOT / "archive" / "reports",
        ROOT / "archive",
    ]
    found = []
    for base in roots:
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            n = p.name.upper()
            parent = str(p.parent).upper()
            if any(tag in n or tag in parent for tag in (
                "D-OBSIDIAN-06.8", "D-OBSIDIAN-06.9", "D-OBSIDIAN-06.10",
                "D-OBSIDIAN-06.11", "D-OBSIDIAN-06.12", "D-OBSIDIAN-06.13"
            )):
                found.append(p)
    return sorted(set(found))

def extract_path_tokens(text):
    # Conservative extraction only; this does not authorize anything.
    patterns = [
        r'(?:"|^|[\s,;])((?:src|tests|vault|data|archive|reports|scripts|patria_harvester_patch)[\\/][^"\r\n,;]+)',
        r'(?:"|^|[\s,;])([A-Za-z0-9_.-]+\.(?:py|ps1|md|txt|json|csv|yaml|yml|toml|ini|bat|psm1|sh))',
    ]
    out = set()
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.I | re.M):
            token = m.group(1).strip().strip('"').rstrip(").]")
            out.add(norm(token))
    return out

print("=" * 96)
print("D-OBSIDIAN-06.15.1 - BASELINE RECONCILIATION")
print("=" * 96)
print("READ-ONLY — NO GIT WRITE")
print()

_, branch, _ = run(["git", "branch", "--show-current"])
_, head, _ = run(["git", "rev-parse", "HEAD"])
tracked_rc, tracked_out, _ = run(["git", "ls-files"])
tracked = [x for x in tracked_out.splitlines() if x.strip()]
status = status_z()

modified = []
deleted = []
untracked = []
for e in status:
    xy = e[:2]
    p = status_path(e)
    if xy == "??":
        untracked.append(p)
    elif "D" in xy:
        deleted.append((xy, p))
    elif xy.strip():
        modified.append((xy, p))

# Current state inventory
buckets = defaultdict(list)
for p in untracked:
    buckets[classify_untracked(p)].append(p)

# Locate historical evidence and build a conservative reference index.
evidence_files = discover_prior_evidence()
reference_tokens = set()
for p in evidence_files:
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
        reference_tokens.update(extract_path_tokens(text))
    except Exception:
        pass

# Also inspect filenames themselves as weak evidence.
reference_names = {norm(p.name) for p in evidence_files}

baseline_candidates = []
outside_baseline = []
review_blocked = []
protected_untracked = []

for p in untracked:
    n = norm(p)

    # Current report/procedural files are not automatically baseline candidates.
    if classify_untracked(p) == "CURRENT_PROCEDURAL_EVIDENCE":
        outside_baseline.append((p, "CURRENT_06.15.1_EVIDENCE"))
        continue

    if is_protected(p):
        protected_untracked.append(p)

    # Strong conservative blocks.
    if any(marker.lower() in n for marker in (
        "backup", "legacy", "old", "copy", "duplicate", "(1)", "(2)"
    )):
        review_blocked.append((p, "NAME_REVIEW_REQUIRED"))
        continue

    if n in reference_tokens:
        # Presence in historical evidence is evidence of relevance, not approval.
        review_blocked.append((p, "HISTORICAL_EVIDENCE_REFERENCE_REQUIRES_RECONCILIATION"))
        continue

    # Current project source/tests/vault/data are candidates for manual baseline
    # consideration, but this audit deliberately does not authorize staging.
    if classify_untracked(p) in {"SOURCE", "TEST", "VAULT_DATA", "DATA", "ARCHIVE"}:
        baseline_candidates.append((p, "STRUCTURAL_BASELINE_CANDIDATE"))
    elif classify_untracked(p) in {"REPORT_OR_EVIDENCE", "SCRIPT"}:
        outside_baseline.append((p, "PROCEDURAL_OR_EVIDENCE_REVIEW"))
    elif classify_untracked(p) in {"PROCEDURAL_SCRIPT", "RUNTIME"}:
        outside_baseline.append((p, "PROCEDURAL_OR_RUNTIME"))
    else:
        review_blocked.append((p, "UNCLASSIFIED_REVIEW"))

# Every tracked deletion is conservatively review-required.
for xy, p in deleted:
    review_blocked.append((p, f"TRACKED_DELETION_{xy}"))

# Every modified tracked file is recorded as baseline candidate only if already tracked;
# this is not a staging decision.
modified_tracked = [(p, xy) for xy, p in modified]

# Hash a sample-independent full inventory for audit reproducibility.
inventory_hash = hashlib.sha256()
for p in sorted(untracked):
    fp = ROOT / p
    if fp.is_file():
        try:
            digest = sha256(fp)
        except OSError:
            digest = "UNREADABLE"
    else:
        digest = "DIRECTORY"
    inventory_hash.update(f"{norm(p)}|{digest}\n".encode("utf-8", errors="replace"))

print(f"Branch: {branch.strip()}")
print(f"HEAD: {head.strip()}")
print(f"Tracked files: {len(tracked)}")
print(f"Status entries: {len(status)}")
print(f"Modified/other tracked: {len(modified)}")
print(f"Deleted tracked: {len(deleted)}")
print(f"Untracked: {len(untracked)}")
print(f"Historical evidence files discovered: {len(evidence_files)}")
print(f"Untracked inventory SHA256: {inventory_hash.hexdigest()}")
print()

print("UNTRACKED BUCKETS")
for k in sorted(buckets):
    print(f"  {k:32} {len(buckets[k])}")
print()

print("RECONCILIATION RESULT — CONSERVATIVE")
print(f"  Structural baseline candidates : {len(baseline_candidates)}")
print(f"  Outside-baseline/procedural    : {len(outside_baseline)}")
print(f"  Review-blocked                 : {len(review_blocked)}")
print(f"  Protected untracked detected   : {len(protected_untracked)}")
print()

print("IMPORTANT:")
print("  Candidate != Git authorization.")
print("  No add, commit, reset, clean, checkout, move, or delete was performed.")
print("  Historical evidence references are treated as REVIEW, never as approval.")
print("  Tracked deletions are REVIEW-BLOCKED.")
print()

# Write detailed report.
lines = [
    "D-OBSIDIAN-06.15.1 - BASELINE RECONCILIATION",
    f"Timestamp: {datetime.now().isoformat(timespec='seconds')}",
    "Mode: READ-ONLY — NO GIT WRITE",
    f"Branch: {branch.strip()}",
    f"HEAD: {head.strip()}",
    f"Tracked files: {len(tracked)}",
    f"Status entries: {len(status)}",
    f"Modified/other tracked: {len(modified)}",
    f"Deleted tracked: {len(deleted)}",
    f"Untracked: {len(untracked)}",
    f"Historical evidence files discovered: {len(evidence_files)}",
    f"Untracked inventory SHA256: {inventory_hash.hexdigest()}",
    "",
    "UNTRACKED BUCKETS:",
]
lines += [f"{k}: {len(buckets[k])}" for k in sorted(buckets)]

lines += ["", "MODIFIED TRACKED:"]
lines += [f"{xy} {p}" for xy, p in modified_tracked]

lines += ["", "TRACKED DELETIONS — REVIEW-BLOCKED:"]
lines += [f"{xy} {p}" for xy, p in deleted]

lines += ["", "STRUCTURAL BASELINE CANDIDATES — NOT AUTHORIZED:"]
lines += [f"{p} | {reason}" for p, reason in baseline_candidates]

lines += ["", "OUTSIDE BASELINE / PROCEDURAL — NOT AUTHORIZED:"]
lines += [f"{p} | {reason}" for p, reason in outside_baseline]

lines += ["", "REVIEW-BLOCKED — NOT AUTHORIZED:"]
lines += [f"{p} | {reason}" for p, reason in review_blocked]

lines += ["", "PROTECTED UNTRACKED:"]
lines += protected_untracked

lines += ["", "HISTORICAL EVIDENCE FILES DISCOVERED:"]
lines += [str(p.relative_to(ROOT)) for p in evidence_files]

lines += [
    "",
    "DECISION:",
    "This is an inventory/reconciliation gate only.",
    "No Git staging or commit is authorized by this report.",
    "A later explicit baseline manifest must enumerate exact approved paths.",
]

REPORT.write_text("\n".join(lines), encoding="utf-8")

# Gate: structural integrity only.
checks = {
    "HEAD_PRESENT": bool(head.strip()),
    "STATUS_READ": len(status) >= 0,
    "PROTECTED_PATHS_EXIST": not [x for x in PROTECTED_PREFIXES if not (ROOT / x).exists()],
    "NO_GIT_WRITE": True,
    "REPORT_CREATED": REPORT.exists(),
}

print("GATES")
for name, ok in checks.items():
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

print()
print(f"Report: {REPORT}")
print()
print("BASELINE RECONCILIATION AUDIT: " + ("PASS" if all(checks.values()) else "FAIL"))
print("Next step: review the generated manifest before any Git staging.")
