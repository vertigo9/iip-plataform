from __future__ import annotations
import hashlib, json, subprocess, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "reports" / "D-OBSIDIAN-06.16.2"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
REPORT = REPORT_DIR / "D-OBSIDIAN-06.16.2_CRITICAL_ARCHITECTURE_TRACKING_RECONCILIATION.txt"
MANIFEST = REPORT_DIR / "D-OBSIDIAN-06.16.2_CRITICAL_ARCHITECTURE_TRACKING_MANIFEST.json"

BASELINE = "2267f4e96d48d7bbb40a6ef2ce9e2133609d409a"
CRITICAL = [
    "src/iip/intelligence/metric_identity.py",
    "src/iip/intelligence/metric_persistence.py",
    "src/iip/intelligence/metric_persistence_adapter.py",
]
INTELLIGENCE_DIR = "src/iip/intelligence"
TEST_DIRS = ["tests/intelligence", "tests/integration"]
PROTECTED = ["vault", "archive", "data"]

# This phase intentionally has two modes:
# audit = read-only forensic reconciliation
# apply = ONLY stage the already-authorized critical architecture files and create
#         one corrective commit. No delete/reset/clean/move operations are used.
# validate = read-only post-commit verification.
# all = audit -> apply -> validate.
FORBIDDEN = {"clean", "reset", "checkout", "restore", "rm", "mv", "rebase"}

def run(args):
    p = subprocess.run(args, cwd=ROOT, capture_output=True)
    return p.returncode, p.stdout.decode("utf-8", errors="replace"), p.stderr.decode("utf-8", errors="replace")

def sha(path):
    p = ROOT / path
    if not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def exists(path):
    return (ROOT / path).is_file()

def git_tracked(path):
    rc, _, _ = run(["git", "ls-files", "--error-unmatch", "--", path])
    return rc == 0

def worktree_state(path):
    rc, out, _ = run(["git", "status", "--porcelain=v1", "--", path])
    return out.strip()

def committed_in_baseline(path):
    rc, out, _ = run(["git", "cat-file", "-e", f"{BASELINE}:{path}"])
    return rc == 0

def assert_safe_args(args):
    low = {str(x).lower() for x in args}
    if low & FORBIDDEN:
        raise RuntimeError(f"Forbidden Git operation detected: {low & FORBIDDEN}")

def audit():
    _, branch, _ = run(["git", "branch", "--show-current"])
    _, head, _ = run(["git", "rev-parse", "HEAD"])
    _, subject, _ = run(["git", "show", "-s", "--format=%s", "HEAD"])
    _, status, _ = run(["git", "status", "--porcelain=v1"])
    _, tracked_intel, _ = run(["git", "ls-files", INTELLIGENCE_DIR])
    _, baseline_intel, _ = run(["git", "ls-tree", "-r", "--name-only", BASELINE, INTELLIGENCE_DIR])

    rows = []
    for p in CRITICAL:
        rows.append({
            "path": p,
            "exists": exists(p),
            "tracked_now": git_tracked(p),
            "present_in_baseline": committed_in_baseline(p),
            "worktree_status": worktree_state(p),
            "sha256": sha(p),
        })

    intel_files = sorted([x for x in tracked_intel.splitlines() if x.strip()])
    baseline_files = sorted([x for x in baseline_intel.splitlines() if x.strip()])
    untracked_candidates = []
    for p in CRITICAL:
        if exists(p) and not git_tracked(p):
            untracked_candidates.append(p)

    result = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "branch": branch.strip(),
        "head": head.strip(),
        "head_subject": subject.strip(),
        "baseline": BASELINE,
        "critical": rows,
        "intelligence_tracked_count": len(intel_files),
        "intelligence_baseline_count": len(baseline_files),
        "critical_authorized_candidates": untracked_candidates,
        "protected_trees_exist": {p: (ROOT/p).exists() for p in PROTECTED},
        "test_trees_exist": {p: (ROOT/p).exists() for p in TEST_DIRS},
        "status_count": len(status.splitlines()),
        "status": status,
    }
    MANIFEST.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result

def apply():
    data = audit()
    if data["branch"] != "v2.1":
        raise RuntimeError("Wrong branch.")
    if data["head"] != BASELINE:
        raise RuntimeError("Baseline HEAD changed; refusing corrective staging.")
    candidates = data["critical_authorized_candidates"]
    if len(candidates) != len(CRITICAL):
        raise RuntimeError(f"Expected exactly 3 critical untracked candidates, found {len(candidates)}: {candidates}")

    # Only the three architecture files are staged.
    args = ["git", "add", "--"] + candidates
    assert_safe_args(args)
    rc, out, err = run(args)
    if rc != 0:
        raise RuntimeError(f"git add failed:\n{out}\n{err}")

    _, cached, _ = run(["git", "diff", "--cached", "--name-status"])
    expected = {p.replace("/", "\\") for p in candidates}
    staged = {line.split("\t",1)[-1].strip().replace("/", "\\") for line in cached.splitlines() if line.strip()}
    if staged != expected:
        raise RuntimeError(f"Staged set mismatch. Expected={expected} Actual={staged}")

    message = "fix(iip): version critical intelligence architecture"
    args = ["git", "commit", "-m", message]
    assert_safe_args(args)
    rc, out, err = run(args)
    if rc != 0:
        raise RuntimeError(f"git commit failed:\n{out}\n{err}")
    return out

def validate():
    _, branch, _ = run(["git", "branch", "--show-current"])
    _, head, _ = run(["git", "rev-parse", "HEAD"])
    _, subject, _ = run(["git", "show", "-s", "--format=%s", "HEAD"])
    _, cached, _ = run(["git", "diff", "--cached", "--name-only"])
    _, commit_files, _ = run(["git", "show", "--format=", "--name-only", "HEAD"])
    commit_set = {x.strip().replace("\\","/") for x in commit_files.splitlines() if x.strip()}

    checks = {
        "BRANCH_V2_1": branch.strip() == "v2.1",
        "HEAD_NOT_BASELINE": head.strip() != BASELINE,
        "CORRECTIVE_COMMIT_SUBJECT": subject.strip() == "fix(iip): version critical intelligence architecture",
        "NO_STAGED_CHANGES": not cached.strip(),
        "CRITICAL_FILES_TRACKED": all(git_tracked(p) for p in CRITICAL),
        "CRITICAL_FILES_PRESENT_IN_HEAD": all(run(["git","cat-file","-e",f"HEAD:{p}"])[0] == 0 for p in CRITICAL),
        "CORRECTIVE_COMMIT_CONTAINS_ONLY_CRITICAL": commit_set == set(CRITICAL),
    }

    rc, pytest_out, pytest_err = run([sys.executable, "-m", "pytest", "-q"])
    checks["PYTEST_EXIT_0"] = rc == 0

    return checks, head.strip(), pytest_out, pytest_err

def write_report(mode, audit_data, apply_out="", validation=None):
    lines = [
        "D-OBSIDIAN-06.16.2 — CRITICAL ARCHITECTURE TRACKING RECONCILIATION",
        f"Timestamp: {datetime.now().isoformat(timespec='seconds')}",
        f"Mode: {mode}",
        "Safety: no clean/reset/checkout/restore/rm/mv/rebase operations.",
        "",
        "BASELINE",
        f"  Expected baseline: {BASELINE}",
        f"  Current branch: {audit_data.get('branch')}",
        f"  Current HEAD: {audit_data.get('head')}",
        f"  Baseline subject: {audit_data.get('head_subject')}",
        "",
        "CRITICAL FILES",
    ]
    for r in audit_data["critical"]:
        lines.append(f"  {r['path']} | exists={r['exists']} | tracked_now={r['tracked_now']} | present_in_baseline={r['present_in_baseline']} | status={r['worktree_status'] or '-'} | sha256={r['sha256']}")
    lines += [
        "",
        f"INTELLIGENCE TRACKED NOW: {audit_data['intelligence_tracked_count']}",
        f"INTELLIGENCE IN BASELINE: {audit_data['intelligence_baseline_count']}",
        f"CRITICAL CANDIDATES: {audit_data['critical_authorized_candidates']}",
        "",
        "APPLY OUTPUT:",
        apply_out or "(not executed)",
    ]
    if validation:
        lines += ["", "VALIDATION CHECKS:"]
        for k,v in validation[0].items():
            lines.append(f"  [{'PASS' if v else 'FAIL'}] {k}")
        lines += ["", f"VALIDATION HEAD: {validation[1]}", "", "PYTEST:", validation[2]]
        if validation[3]:
            lines += ["STDERR:", validation[3]]
    REPORT.write_text("\n".join(lines), encoding="utf-8")

def main():
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "all"
    if mode not in {"audit","apply","validate","all"}:
        print("Usage: audit | apply | validate | all")
        return 2

    audit_data = audit()
    print("="*100)
    print("D-OBSIDIAN-06.16.2 — CRITICAL ARCHITECTURE TRACKING RECONCILIATION")
    print("="*100)
    print("Branch:", audit_data["branch"])
    print("HEAD:", audit_data["head"])
    print("Critical candidates:", audit_data["critical_authorized_candidates"])
    print("Intelligence tracked now:", audit_data["intelligence_tracked_count"])
    print("Intelligence in baseline:", audit_data["intelligence_baseline_count"])

    if mode == "audit":
        write_report(mode, audit_data)
        print("AUDIT ONLY: PASS")
        return 0

    apply_out = ""
    if mode in {"apply","all"}:
        apply_out = apply()
        print()
        print(apply_out)

    validation = None
    if mode in {"validate","all"}:
        # Re-audit after apply/commit.
        audit_data = audit()
        validation = validate()
        checks = validation[0]
        print()
        for k,v in checks.items():
            print(f"  [{'PASS' if v else 'FAIL'}] {k}")
        print()
        print("PYTEST OUTPUT")
        print(validation[2])
        if validation[3]:
            print(validation[3])
        ok = all(checks.values())
        write_report(mode, audit_data, apply_out, validation)
        print("Report:", REPORT)
        print()
        print("D-OBSIDIAN-06.16.2:", "PASS" if ok else "FAIL")
        return 0 if ok else 2

    write_report(mode, audit_data, apply_out)
    print("D-OBSIDIAN-06.16.2 APPLY: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
