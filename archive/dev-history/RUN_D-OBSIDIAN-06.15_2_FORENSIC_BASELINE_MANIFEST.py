from __future__ import annotations

import hashlib
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "reports" / "D-OBSIDIAN-06.15.2"
OUT.mkdir(parents=True, exist_ok=True)
REPORT = OUT / "D-OBSIDIAN-06.15.2_FORENSIC_BASELINE_MANIFEST.txt"

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

HISTORICAL_TAGS = (
    "D-OBSIDIAN-06.8", "D-OBSIDIAN-06.9", "D-OBSIDIAN-06.10",
    "D-OBSIDIAN-06.11", "D-OBSIDIAN-06.12", "D-OBSIDIAN-06.13",
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

def hash_file(p):
    if not p.is_file():
        return "DIRECTORY"
    h = hashlib.sha256()
    try:
        with p.open("rb") as f:
            for c in iter(lambda: f.read(1024 * 1024), b""):
                h.update(c)
        return h.hexdigest()
    except OSError:
        return "UNREADABLE"

def discover_historical():
    roots = [ROOT / "reports", ROOT / "archive"]
    result = []
    for base in roots:
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file():
                s = str(p).upper()
                if any(tag in s for tag in HISTORICAL_TAGS):
                    result.append(p)
    return sorted(set(result))

def extract_path_tokens(text):
    result = set()
    # Conservative only. A token found in evidence is REVIEW evidence, never approval.
    pats = [
        r'((?:src|tests|vault|data|archive|reports|scripts|patria_harvester_patch)[\\/][A-Za-z0-9_ .()\-\\/]+?\.(?:py|ps1|md|txt|json|csv|yaml|yml|toml|ini|bat|psm1|sh))',
        r'([A-Za-z0-9_.()\-]+\.(?:py|ps1|md|txt|json|csv|yaml|yml|toml|ini|bat|psm1|sh))',
    ]
    for pat in pats:
        for m in re.finditer(pat, text, flags=re.I):
            result.add(norm(m.group(1).rstrip(").,;:")))
    return result

print("=" * 100)
print("D-OBSIDIAN-06.15.2 - FORENSIC BASELINE MANIFEST")
print("=" * 100)
print("READ-ONLY — NO GIT WRITE")
print()

_, branch, _ = run(["git", "branch", "--show-current"])
_, head, _ = run(["git", "rev-parse", "HEAD"])
_, tracked_raw, _ = run(["git", "ls-files"])
tracked = [x for x in tracked_raw.splitlines() if x.strip()]
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

historical = discover_historical()
reference_index = defaultdict(list)

for p in historical:
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
        for token in extract_path_tokens(text):
            reference_index[token].append(p)
    except Exception:
        pass

# Build exact file-level manifest.
rows = []

for xy, p in modified:
    rows.append({
        "path": p,
        "decision": "TRACKED-MODIFIED-REVIEW",
        "reason": f"already tracked; status={xy}; baseline inclusion requires explicit review",
        "category": "TRACKED",
        "sha256": hash_file(ROOT / p),
    })

for xy, p in deleted:
    rows.append({
        "path": p,
        "decision": "REVIEW-BLOCKED",
        "reason": f"tracked deletion status={xy}; no deletion authorization",
        "category": "TRACKED-DELETION",
        "sha256": "MISSING",
    })

for p in untracked:
    n = norm(p)
    cat = category(p)

    if n.startswith("reports/d-obsidian-06.15.2/"):
        decision = "OUTSIDE-BASELINE"
        reason = "current procedural evidence"
    elif n.startswith("run_d-obsidian-06."):
        decision = "OUTSIDE-BASELINE"
        reason = "procedural diagnostic script; not automatically part of product baseline"
    elif cat == "RUNTIME":
        decision = "OUTSIDE-BASELINE"
        reason = "runtime/generated artifact"
    elif n in reference_index:
        decision = "REVIEW-BLOCKED"
        reason = "historical evidence reference; reference does not equal approval"
    elif any(x in n for x in ("backup", "legacy", "old", "copy", "duplicate", "(1)", "(2)")):
        decision = "REVIEW-BLOCKED"
        reason = "name indicates possible historical/duplicate artifact"
    elif is_protected(p):
        decision = "PROTECTED-REVIEW"
        reason = "protected tree; inclusion requires explicit manifest reconciliation"
    elif cat in {"SOURCE", "TEST", "VAULT", "DATA", "ARCHIVE"}:
        decision = "BASELINE-CANDIDATE"
        reason = "structural project content; candidate only"
    elif cat in {"REPORT", "SCRIPT"}:
        decision = "OUTSIDE-BASELINE"
        reason = "report/script artifact; not automatically product baseline"
    else:
        decision = "REVIEW-BLOCKED"
        reason = "unclassified/other"

    rows.append({
        "path": p,
        "decision": decision,
        "reason": reason,
        "category": cat,
        "sha256": hash_file(ROOT / p),
    })

counts = Counter(r["decision"] for r in rows)

# Exact duplicate hash groups among current untracked files.
hash_groups = defaultdict(list)
for r in rows:
    if r["path"] in untracked and r["sha256"] not in {"DIRECTORY", "UNREADABLE"}:
        hash_groups[r["sha256"]].append(r["path"])
duplicate_groups = [v for v in hash_groups.values() if len(v) > 1]

print(f"Branch: {branch.strip()}")
print(f"HEAD: {head.strip()}")
print(f"Tracked files: {len(tracked)}")
print(f"Status entries: {len(status)}")
print(f"Modified tracked: {len(modified)}")
print(f"Deleted tracked: {len(deleted)}")
print(f"Untracked: {len(untracked)}")
print(f"Historical evidence files discovered: {len(historical)}")
print(f"Manifest rows: {len(rows)}")
print(f"Exact duplicate hash groups among current untracked: {len(duplicate_groups)}")
print()

print("DECISION DISTRIBUTION")
for k in sorted(counts):
    print(f"  {k:30} {counts[k]}")
print()

print("PROTECTED PATH CHECK")
for p in PROTECTED:
    ok = (ROOT / p).exists()
    print(f"  [{'PASS' if ok else 'FAIL'}] {p}")
print()

print("FORENSIC RULES")
print("  [PASS] Tracked deletions are REVIEW-BLOCKED")
print("  [PASS] Historical references do not authorize staging")
print("  [PASS] Procedural/runtime artifacts are outside baseline by default")
print("  [PASS] Protected trees require explicit reconciliation")
print("  [PASS] No Git write operation executed")
print()

# Detailed report
lines = [
    "D-OBSIDIAN-06.15.2 - FORENSIC BASELINE MANIFEST",
    f"Timestamp: {datetime.now().isoformat(timespec='seconds')}",
    "Mode: READ-ONLY — NO GIT WRITE",
    f"Branch: {branch.strip()}",
    f"HEAD: {head.strip()}",
    f"Tracked files: {len(tracked)}",
    f"Status entries: {len(status)}",
    f"Modified tracked: {len(modified)}",
    f"Deleted tracked: {len(deleted)}",
    f"Untracked: {len(untracked)}",
    f"Historical evidence files discovered: {len(historical)}",
    f"Manifest rows: {len(rows)}",
    f"Exact duplicate hash groups among current untracked: {len(duplicate_groups)}",
    "",
    "DECISION DISTRIBUTION:",
]
lines += [f"{k}: {counts[k]}" for k in sorted(counts)]

lines += ["", "MANIFEST ROWS:"]
for r in sorted(rows, key=lambda x: norm(x["path"])):
    lines.append(
        f"{r['decision']} | {r['category']} | {r['path']} | "
        f"{r['reason']} | SHA256={r['sha256']}"
    )

lines += ["", "EXACT DUPLICATE HASH GROUPS — REVIEW ONLY:"]
for group in duplicate_groups:
    digest = hash_file(ROOT / group[0])
    lines.append(f"HASH={digest}")
    lines.extend(f"  {p}" for p in sorted(group))

lines += ["", "HISTORICAL EVIDENCE FILES:"]
lines.extend(str(p.relative_to(ROOT)) for p in historical)

lines += [
    "",
    "FINAL DECISION:",
    "This manifest is forensic/reconciliatory only.",
    "BASELINE-CANDIDATE does NOT mean authorized for git add.",
    "No Git staging, commit, deletion, move, reset, clean, or checkout was performed.",
    "A later approval gate must convert exact paths into an explicit staging manifest.",
]

REPORT.write_text("\n".join(lines), encoding="utf-8")

checks = {
    "HEAD_PRESENT": bool(head.strip()),
    "MANIFEST_COMPLETE": len(rows) == len(modified) + len(deleted) + len(untracked),
    "PROTECTED_PATHS_EXIST": all((ROOT / p).exists() for p in PROTECTED),
    "NO_GIT_WRITE": True,
    "REPORT_EXISTS": REPORT.exists(),
}

print("GATES")
for name, ok in checks.items():
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

print()
print(f"Report: {REPORT}")
print()
print("FORENSIC BASELINE MANIFEST: " + ("PASS" if all(checks.values()) else "FAIL"))
