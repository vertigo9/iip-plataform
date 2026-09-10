from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE_REPORT = ROOT / "reports" / "D-OBSIDIAN-06.15.4-5" / "D-OBSIDIAN-06.15.4_EXPLICIT_BASELINE_MANIFEST.txt"
OUT = ROOT / "reports" / "D-OBSIDIAN-06.15.4-DIAG"
OUT.mkdir(parents=True, exist_ok=True)
REPORT = OUT / "D-OBSIDIAN-06.15.4-DIAG_32_CANDIDATES.txt"

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

def sha256(p):
    if not p.exists():
        return "MISSING"
    if not p.is_file():
        return "DIRECTORY"
    h = hashlib.sha256()
    try:
        with p.open("rb") as f:
            for c in iter(lambda: f.read(1024 * 1024), b""):
                h.update(c)
        return h.hexdigest()
    except OSError as e:
        return f"UNREADABLE:{e}"

def is_protected(p):
    n = norm(p)
    return any(n == x.lower() or n.startswith(x.lower().rstrip("/") + "/") for x in PROTECTED)

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

def load_candidate_paths():
    if not SOURCE_REPORT.exists():
        return []
    out = []
    for line in SOURCE_REPORT.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("PENDING-APPROVAL | "):
            path = line.split(" | ", 1)[1].split(" | SHA256=", 1)[0]
            out.append(path)
    return out

_, branch, _ = run(["git", "branch", "--show-current"])
_, head, _ = run(["git", "rev-parse", "HEAD"])
_, tracked_out, _ = run(["git", "ls-files"])
tracked = {norm(x) for x in tracked_out.splitlines() if x.strip()}
status = status_z()
status_map = {norm(path_of(e)): e[:2] for e in status}

candidates = load_candidate_paths()

print("=" * 100)
print("D-OBSIDIAN-06.15.4-DIAG - DIAGNOSTIC OF 32 BASELINE CANDIDATES")
print("=" * 100)
print("READ-ONLY — NO GIT WRITE")
print()

print(f"Candidate paths loaded from 06.15.4 manifest: {len(candidates)}")
print()

rows = []
for p in sorted(candidates, key=norm):
    n = norm(p)
    fp = ROOT / p
    exists = fp.exists()
    is_file = fp.is_file()
    h = sha256(fp)
    tracked_now = n in tracked
    status_now = status_map.get(n, "-")
    prot = is_protected(p)
    cat = category(p)
    procedural = cat == "PROCEDURAL"
    runtime = cat == "RUNTIME"

    reasons = []
    if not exists:
        reasons.append("MISSING")
    if exists and not is_file:
        reasons.append("DIRECTORY_NOT_FILE")
    if h in {"MISSING", "DIRECTORY"} or h.startswith("UNREADABLE:"):
        reasons.append("HASH_INVALID")
    if tracked_now:
        reasons.append("ALREADY_TRACKED")
    if procedural:
        reasons.append("PROCEDURAL")
    if runtime:
        reasons.append("RUNTIME")
    if prot:
        reasons.append("PROTECTED")
    if status_now != "??":
        reasons.append(f"STATUS_NOT_UNTRACKED:{status_now}")

    ok = (
        exists and is_file and
        h not in {"MISSING", "DIRECTORY"} and not h.startswith("UNREADABLE:") and
        not tracked_now and not procedural and not runtime
    )

    rows.append({
        "path": p,
        "category": cat,
        "exists": exists,
        "is_file": is_file,
        "hash": h,
        "tracked": tracked_now,
        "status": status_now,
        "protected": prot,
        "procedural": procedural,
        "runtime": runtime,
        "eligible": ok,
        "reasons": reasons,
    })

for i, r in enumerate(rows, 1):
    print(f"[{i:02}] {r['path']}")
    print(f"     category={r['category']} exists={r['exists']} file={r['is_file']} tracked={r['tracked']} status={r['status']}")
    print(f"     protected={r['protected']} procedural={r['procedural']} runtime={r['runtime']}")
    print(f"     sha256={r['hash']}")
    print(f"     eligible={r['eligible']} reason={','.join(r['reasons']) or 'NONE'}")

eligible = [r for r in rows if r["eligible"]]
blocked = [r for r in rows if not r["eligible"]]

print()
print("SUMMARY")
print(f"  Total candidates: {len(rows)}")
print(f"  Eligible under 06.15.4/5 safety rule: {len(eligible)}")
print(f"  Blocked: {len(blocked)}")

reason_counts = {}
for r in blocked:
    for reason in r["reasons"]:
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

print("  Block reasons:")
for reason, count in sorted(reason_counts.items()):
    print(f"    {reason}: {count}")

print()
print("NO GIT WRITE: PASS")
print("NO STAGING: PASS")
print("NO DELETE/MOVE/CLEAN/RESET: PASS")

lines = [
    "D-OBSIDIAN-06.15.4-DIAG - DIAGNOSTIC OF BASELINE CANDIDATES",
    f"Timestamp: {datetime.now().isoformat(timespec='seconds')}",
    "Mode: READ-ONLY — NO GIT WRITE",
    f"Branch: {branch.strip()}",
    f"HEAD: {head.strip()}",
    f"Candidates loaded: {len(rows)}",
    "",
    "FILE-LEVEL DIAGNOSTIC:",
]
for i, r in enumerate(rows, 1):
    lines += [
        f"[{i:02}] {r['path']}",
        f"  category={r['category']}",
        f"  exists={r['exists']} file={r['is_file']} tracked={r['tracked']} status={r['status']}",
        f"  protected={r['protected']} procedural={r['procedural']} runtime={r['runtime']}",
        f"  sha256={r['hash']}",
        f"  eligible={r['eligible']}",
        f"  reasons={','.join(r['reasons']) or 'NONE'}",
    ]

lines += [
    "",
    "SUMMARY:",
    f"Total candidates: {len(rows)}",
    f"Eligible: {len(eligible)}",
    f"Blocked: {len(blocked)}",
    "",
    "BLOCK REASONS:",
]
lines += [f"{k}: {v}" for k, v in sorted(reason_counts.items())]
lines += [
    "",
    "DECISION:",
    "This diagnostic identifies why candidates were blocked.",
    "It does not authorize staging and performs no Git write operation.",
]

REPORT.write_text("\n".join(lines), encoding="utf-8")

checks = {
    "SOURCE_MANIFEST_EXISTS": SOURCE_REPORT.exists(),
    "CANDIDATES_LOADED": len(candidates) == 32,
    "NO_GIT_WRITE": True,
    "REPORT_EXISTS": REPORT.exists(),
}

print()
print("GATES")
for k, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
print()
print(f"Report: {REPORT}")
print()
print("CANDIDATE DIAGNOSTIC: " + ("PASS" if all(checks.values()) else "FAIL"))
