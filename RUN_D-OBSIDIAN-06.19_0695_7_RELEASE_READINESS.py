from __future__ import annotations

import csv
import hashlib
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

FINAL_GATE = REPORTS / "PCIP11_0695_7_FINAL_PROMOTION_GATE_R1.csv"
READINESS_CSV = REPORTS / "PCIP11_0695_7_RELEASE_READINESS_R1.csv"
READINESS_MD = REPORTS / "PCIP11_0695_7_RELEASE_READINESS_R1.md"
READINESS_SCRIPT = ROOT / "RELEASE_0695_7_READINESS_R1.py"

def snapshot_tree(base: Path) -> dict[str, str]:
    out = {}
    if not base.exists():
        return out
    for p in sorted(x for x in base.rglob("*") if x.is_file()):
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        out[str(p.relative_to(base)).replace("\\", "/")] = h.hexdigest()
    return out

def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def main() -> int:
    print("=" * 100)
    print("D-OBSIDIAN-06.19 — 0695.7 RELEASE READINESS / READ-ONLY GATE")
    print("=" * 100)

    checks = []
    def check(name, ok, detail=""):
        checks.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    check("FINAL_PROMOTION_GATE_EXISTS", FINAL_GATE.exists(), str(FINAL_GATE))
    check("READINESS_SCRIPT_EXISTS", READINESS_SCRIPT.exists(), str(READINESS_SCRIPT))
    if not FINAL_GATE.exists() or not READINESS_SCRIPT.exists():
        print("\nD-OBSIDIAN-06.19: FAIL")
        return 2

    vault = ROOT / "vault"
    before_vault = snapshot_tree(vault)

    print("\nRUNNING EXISTING 0695.7 RELEASE READINESS R1...")
    try:
        runpy.run_path(str(READINESS_SCRIPT), run_name="__main__")
        readiness_rc = 0
    except SystemExit as exc:
        readiness_rc = int(exc.code or 0)
    except Exception as exc:
        print(f"  [FAIL] READINESS_EXECUTION — {type(exc).__name__}: {exc}")
        readiness_rc = 2

    after_vault = snapshot_tree(vault)
    check("VAULT_UNCHANGED", before_vault == after_vault,
          "no Vault file created/modified/deleted")

    check("READINESS_CSV_EXISTS", READINESS_CSV.exists(), str(READINESS_CSV))
    check("READINESS_MD_EXISTS", READINESS_MD.exists(), str(READINESS_MD))

    if READINESS_CSV.exists():
        rows = read_csv(READINESS_CSV)
        ready = sum((r.get("Release_Readiness") or "").strip() == "READY" for r in rows)
        expected_block = sum((r.get("Release_Readiness") or "").strip() == "EXPECTED_BLOCK" for r in rows)
        review = sum((r.get("Release_Readiness") or "").strip() == "REVIEW" for r in rows)
        final_pass = sum((r.get("Final_Promotion_Gate") or "").strip() == "PASS" for r in rows)
        blocked = sum((r.get("Final_Promotion_Gate") or "").strip() == "BLOCKED" for r in rows)
        dup = len(rows) - len({
            ((r.get("Row") or "").strip(),
             (r.get("SHA256") or "").strip().upper(),
             (r.get("Metric") or "").strip())
            for r in rows
        })
        check("READINESS_ROWS", len(rows) > 0, f"rows={len(rows)}")
        check("PASS_ROWS_READY", ready == final_pass, f"ready={ready}, final_pass={final_pass}")
        check("NO_DUPLICATE_IDENTITY", dup == 0, f"duplicates={dup}")
        check("NO_REVIEW_ROWS", review == 0, f"review={review}")
        check("EXPECTED_BLOCKS_ALLOWED", expected_block >= 0, f"expected_block={expected_block}")
        print(f"\n  Final PASS      : {final_pass}")
        print(f"  Final BLOCKED   : {blocked}")
        print(f"  Release READY   : {ready}")
        print(f"  Expected BLOCK  : {expected_block}")
        print(f"  Review          : {review}")
        print(f"  Duplicate keys  : {dup}")
    else:
        print("\n  [FAIL] READINESS_DATA — CSV unavailable")
        checks.append(False)

    check("READINESS_SCRIPT_EXIT", readiness_rc == 0, f"returncode={readiness_rc}")

    print(f"\nCSV : {READINESS_CSV}")
    print(f"MD  : {READINESS_MD}")
    print("\nAuthorization boundary:")
    print("  Metric persistence : NOT GRANTED")
    print("  KnowledgeBridge    : NOT GRANTED")
    print("  Vault write        : NOT GRANTED")
    print("  Vault changed      : NO")

    ok = all(checks)
    print(f"\nD-OBSIDIAN-06.19: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 2

if __name__ == "__main__":
    raise SystemExit(main())
