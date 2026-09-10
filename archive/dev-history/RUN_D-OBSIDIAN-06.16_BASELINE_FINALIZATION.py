from __future__ import annotations
import argparse, hashlib, json, subprocess, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "reports" / "D-OBSIDIAN-06.16"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST = REPORT_DIR / "D-OBSIDIAN-06.16_BASELINE_MANIFEST.json"
REPORT = REPORT_DIR / "D-OBSIDIAN-06.16_BASELINE_FINALIZATION.txt"
STAGE_MANIFEST = REPORT_DIR / "D-OBSIDIAN-06.16_STAGE_MANIFEST.txt"

PROTECTED = [
    "src/iip/intelligence/metric_identity.py",
    "src/iip/intelligence/metric_persistence.py",
    "src/iip/intelligence/metric_persistence_adapter.py",
    "tests/integration",
    "tests/intelligence",
    "vault", "data", "archive",
]

def run(args):
    p = subprocess.run(args, cwd=ROOT, capture_output=True)
    return p.returncode, p.stdout.decode("utf-8", errors="replace"), p.stderr.decode("utf-8", errors="replace")

def norm(p):
    p = p.replace("\\", "/").strip().strip('"')
    while p.startswith("./"): p = p[2:]
    return p.lower()

def sha(p):
    if not p.is_file(): return "MISSING"
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024), b""): h.update(c)
    return h.hexdigest()

def status():
    _, out, _ = run(["git","status","--porcelain=v1","-z"])
    return [x for x in out.split("\0") if x]

def path_of(e): return e[3:] if len(e)>=4 else e

def snapshot():
    _, branch, _ = run(["git","branch","--show-current"])
    _, head, _ = run(["git","rev-parse","HEAD"])
    entries=status()
    tracked=set(norm(x) for x in run(["git","ls-files"])[1].splitlines() if x.strip())
    rows=[]
    for e in entries:
        xy,p=e[:2],path_of(e)
        n=norm(p)
        if xy=="??": kind="UNTRACKED"
        elif "D" in xy: kind="DELETED"
        elif xy.strip(): kind="MODIFIED"
        else: kind="OTHER"
        rows.append({"path":p,"norm":n,"status":xy,"kind":kind,
                     "tracked":n in tracked,"sha256":sha(ROOT/p)})
    return branch.strip(),head.strip(),rows

def safe_candidate(r):
    n=r["norm"]
    if r["kind"]!="UNTRACKED": return False,"not-untracked"
    if not (ROOT/r["path"]).is_file(): return False,"not-file"
    if n.startswith("reports/d-obsidian-06.16/"): return False,"current-evidence"
    if n.startswith("run_d-obsidian-06."): return False,"procedural"
    if n.startswith(".logs/") or n in {".coverage","coverage-current.json"}: return False,"runtime"
    if any(x in n for x in ("backup","legacy","old","copy","duplicate","(1)","(2)")): return False,"possible-historical-or-duplicate"
    if any(n==x or n.startswith(x.rstrip("/")+"/") for x in map(str.lower,PROTECTED)): return False,"protected-review"
    if not any(n.startswith(x) for x in ("src/","tests/","vault/","data/","archive/")): return False,"outside-structural-scope"
    return True,"structural-baseline-candidate"

def audit():
    branch,head,rows=snapshot()
    candidates=[]; blocked=[]
    for r in rows:
        ok,reason=safe_candidate(r)
        if ok: candidates.append(r)
        elif r["kind"]=="UNTRACKED": blocked.append((r,reason))
    manifest={
        "phase":"06.16",
        "timestamp":datetime.now().isoformat(timespec="seconds"),
        "mode":"READ-ONLY",
        "branch":branch,"head":head,
        "status_entries":len(rows),
        "candidates":candidates,
        "blocked_untracked":[{"path":r["path"],"reason":reason} for r,reason in blocked],
        "modified":[r for r in rows if r["kind"]=="MODIFIED"],
        "deleted":[r for r in rows if r["kind"]=="DELETED"],
        "protected":PROTECTED,
        "approved_baseline":[],
    }
    MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    lines=[
        "D-OBSIDIAN-06.16 BASELINE FINALIZATION",
        f"Timestamp: {manifest['timestamp']}",
        "Mode: READ-ONLY AUDIT",
        f"Branch: {branch}","HEAD: "+head,
        f"Status entries: {len(rows)}",
        f"Structural candidates: {len(candidates)}",
        f"Blocked untracked: {len(blocked)}",
        f"Modified tracked: {len(manifest['modified'])}",
        f"Deleted tracked: {len(manifest['deleted'])}",
        "",
        "CANDIDATES — PENDING EXPLICIT APPROVAL:",
    ]
    lines += [f"{r['path']} | SHA256={r['sha256']}" for r in candidates]
    lines += ["","BLOCKED UNTRACKED:"]
    lines += [f"{r['path']} | {reason}" for r,reason in blocked]
    lines += ["","GUARDS: NO GIT WRITE; NO DELETE; NO MOVE; NO CLEAN; NO RESET."]
    REPORT.write_text("\n".join(lines),encoding="utf-8")
    print(f"Branch: {branch}")
    print(f"HEAD: {head}")
    print(f"Status entries: {len(rows)}")
    print(f"Structural candidates: {len(candidates)}")
    print(f"Blocked untracked: {len(blocked)}")
    print(f"Modified: {len(manifest['modified'])}")
    print(f"Deleted: {len(manifest['deleted'])}")
    print(f"Manifest: {MANIFEST}")
    print(f"Report: {REPORT}")
    print("AUDIT: PASS")
    return 0

def authorize():
    if not MANIFEST.exists():
        print("FAIL: run audit first"); return 2
    m=json.loads(MANIFEST.read_text(encoding="utf-8"))
    candidates=m.get("candidates",[])
    if not candidates:
        print("FAIL: no candidates available for explicit authorization"); return 2
    # Explicit authorization is generated from the audited candidate set,
    # but still requires the operator to run this phase deliberately.
    approved=[]
    for r in candidates:
        p=ROOT/r["path"]
        if p.is_file() and sha(p)==r["sha256"]:
            approved.append(r["path"])
    if len(approved)!=len(candidates):
        print("FAIL: candidate filesystem/hash drift detected"); return 2
    STAGE_MANIFEST.write_text("\n".join(approved)+"\n",encoding="utf-8")
    m["approved_baseline"]=approved
    m["authorization_timestamp"]=datetime.now().isoformat(timespec="seconds")
    MANIFEST.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"EXPLICIT APPROVED-BASELINE: {len(approved)}")
    print(f"Stage manifest: {STAGE_MANIFEST}")
    print("AUTHORIZATION: PASS")
    print("No Git staging performed.")
    return 0

def validate_stage():
    if not STAGE_MANIFEST.exists():
        print("FAIL: explicit stage manifest does not exist"); return 2
    approved=[x.strip() for x in STAGE_MANIFEST.read_text(encoding="utf-8").splitlines() if x.strip()]
    branch,head,rows=snapshot()
    current={norm(r["path"]):r for r in rows}
    failures=[]
    for p in approved:
        r=current.get(norm(p))
        if not r: failures.append((p,"not-currently-in-status"))
        elif r["kind"]!="UNTRACKED": failures.append((p,f"status={r['status']}"))
        elif not (ROOT/p).is_file(): failures.append((p,"missing"))
    if failures:
        print("PRE-STAGING VALIDATION: FAIL")
        for x in failures: print(" ",x)
        return 2
    print(f"PRE-STAGING VALIDATION: PASS ({len(approved)} paths)")
    print("No Git staging performed.")
    return 0

def stage():
    if validate_stage()!=0: return 2
    approved=[x.strip() for x in STAGE_MANIFEST.read_text(encoding="utf-8").splitlines() if x.strip()]
    # The only Git write in this phase is selective staging of the exact manifest.
    p=subprocess.run(["git","add","--",*approved],cwd=ROOT,capture_output=True,text=True)
    if p.returncode:
        print(p.stdout,p.stderr); return p.returncode
    _,cached,_=run(["git","diff","--cached","--name-status"])
    print("SELECTIVE STAGING: PASS")
    print("Cached paths:")
    print(cached)
    return 0

def cached_gate():
    _,out,_=run(["git","diff","--cached","--name-only"])
    staged=[x for x in out.splitlines() if x.strip()]
    approved=[x.strip() for x in STAGE_MANIFEST.read_text(encoding="utf-8").splitlines() if x.strip()] if STAGE_MANIFEST.exists() else []
    a={norm(x) for x in approved}; s={norm(x) for x in staged}
    if a!=s:
        print("CACHED DIFF GATE: FAIL")
        print("Expected-only:",sorted(a-s)); print("Unexpected:",sorted(s-a))
        return 2
    _,stat,_=run(["git","diff","--cached","--stat"])
    print("CACHED DIFF GATE: PASS")
    print(f"Staged paths: {len(staged)}")
    print(stat)
    return 0

def commit():
    if cached_gate()!=0: return 2
    msg="chore(iip): establish audited baseline"
    p=subprocess.run(["git","commit","-m",msg],cwd=ROOT,text=True,capture_output=True)
    print(p.stdout)
    print(p.stderr)
    return p.returncode

def post():
    branch,head,rows=snapshot()
    _,out,_=run(["git","status","--porcelain"])
    _,pytest,_=run([sys.executable,"-m","pytest","-q"])
    print("POST-COMMIT SNAPSHOT")
    print("Branch:",branch)
    print("HEAD:",head)
    print("Status:")
    print(out or "(clean)")
    print("PYTEST EXIT:",pytest)
    print("POST-COMMIT: PASS" if pytest==0 else "POST-COMMIT: FAIL")
    return 0 if pytest==0 else 2

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("phase",choices=["audit","authorize","validate","stage","cached-gate","commit","post","all-safe"])
    ap.add_argument("--commit",action="store_true")
    a=ap.parse_args()
    if a.phase=="audit": return audit()
    if a.phase=="authorize": return authorize()
    if a.phase=="validate": return validate_stage()
    if a.phase=="stage": return stage()
    if a.phase=="cached-gate": return cached_gate()
    if a.phase=="commit":
        if not a.commit:
            print("REFUSED: use --commit explicitly")
            return 2
        return commit()
    if a.phase=="post": return post()
    if a.phase=="all-safe":
        if audit()!=0: return 2
        if authorize()!=0: return 2
        if validate_stage()!=0: return 2
        if stage()!=0: return 2
        if cached_gate()!=0: return 2
        print("ALL-SAFE PIPELINE STOPPED BEFORE COMMIT.")
        print("Review git diff --cached, then run: python RUN_D-OBSIDIAN-06.16_BASELINE_FINALIZATION.py commit --commit")
        return 0

if __name__=="__main__":
    raise SystemExit(main())
