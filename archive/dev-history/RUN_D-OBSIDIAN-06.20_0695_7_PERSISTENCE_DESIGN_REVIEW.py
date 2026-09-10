from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
INPUT = REPORTS / "PCIP11_0695_7_RELEASE_READINESS_R1.csv"
OUT_CSV = REPORTS / "PCIP11_0695_7_PERSISTENCE_DESIGN_REVIEW_R1.csv"
OUT_MD = REPORTS / "PCIP11_0695_7_PERSISTENCE_DESIGN_REVIEW_R1.md"
VAULT = ROOT / "vault"

REQUIRED_AUTH = {
    "Metric_Persistence_Authorization": "NOT_GRANTED",
    "KnowledgeBridge_Write_Authorization": "NOT_GRANTED",
    "Vault_Write_Authorization": "NOT_GRANTED",
}

REQUIRED_FIELDS = (
    "Row", "SHA256", "FileName", "Original_Identity", "Lineage",
    "Metric", "Value", "Original_Unit", "Resolved_Unit", "Scale",
    "Resolved_Period", "Final_Promotion_Gate", "Release_Readiness",
)

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def v(row, key):
    return str(row.get(key, "") or "").strip()

def main() -> int:
    print("=" * 100)
    print("D-OBSIDIAN-06.20 — 0695.7 PERSISTENCE DESIGN REVIEW / AUTHORIZATION BOUNDARY")
    print("=" * 100)

    checks = []
    def check(name, ok, detail=""):
        checks.append(bool(ok))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    check("READINESS_INPUT_EXISTS", INPUT.exists(), str(INPUT))
    if not INPUT.exists():
        print("\nD-OBSIDIAN-06.20: FAIL")
        return 2

    before_vault = {
        str(p.relative_to(VAULT)).replace("\\", "/"): sha256_file(p)
        for p in VAULT.rglob("*") if p.is_file()
    } if VAULT.exists() else {}

    rows = read_csv(INPUT)
    check("INPUT_NONEMPTY", bool(rows), f"rows={len(rows)}")
    check("INPUT_REQUIRED_FIELDS",
          bool(rows) and all(field in rows[0] for field in REQUIRED_FIELDS),
          "required schema present")

    ready = [r for r in rows if v(r, "Release_Readiness") == "READY"]
    blocked = [r for r in rows if v(r, "Release_Readiness") == "EXPECTED_BLOCK"]
    review = [r for r in rows if v(r, "Release_Readiness") == "REVIEW"]

    check("READY_SET_31", len(ready) == 31, f"ready={len(ready)}")
    check("NO_REVIEW_ROWS", len(review) == 0, f"review={len(review)}")
    check("EXPECTED_BLOCK_43", len(blocked) == 43, f"expected_block={len(blocked)}")

    auth_ok = all(
        all(v(r, k) == expected for k, expected in REQUIRED_AUTH.items())
        for r in ready
    )
    check("AUTHORIZATION_LOCKED", auth_ok,
          "all READY rows remain NOT_GRANTED")

    ids = [(v(r, "Row"), v(r, "SHA256").upper(), v(r, "Metric")) for r in ready]
    check("READY_IDENTITY_UNIQUE", len(ids) == len(set(ids)),
          f"unique={len(set(ids))}")

    periods = Counter(v(r, "Resolved_Period") for r in ready)
    lineages = Counter(v(r, "Lineage") for r in ready)
    metrics = Counter(v(r, "Metric") for r in ready)

    design_rows = []
    for r in ready:
        design_rows.append({
            "Row": v(r, "Row"),
            "SHA256": v(r, "SHA256"),
            "FileName": v(r, "FileName"),
            "Original_Identity": v(r, "Original_Identity"),
            "Lineage": v(r, "Lineage"),
            "Metric": v(r, "Metric"),
            "Value": v(r, "Value"),
            "Original_Unit": v(r, "Original_Unit"),
            "Resolved_Unit": v(r, "Resolved_Unit"),
            "Scale": v(r, "Scale"),
            "Resolved_Period": v(r, "Resolved_Period"),
            "Design_Status": "DESIGN_REVIEW_READY",
            "Metric_Persistence_Authorization": "NOT_GRANTED",
            "KnowledgeBridge_Write_Authorization": "NOT_GRANTED",
            "Vault_Write_Authorization": "NOT_GRANTED",
            "Execution_Status": "NOT_AUTHORIZED",
        })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(design_rows[0].keys()) if design_rows else [])
        writer.writeheader()
        writer.writerows(design_rows)

    after_vault = {
        str(p.relative_to(VAULT)).replace("\\", "/"): sha256_file(p)
        for p in VAULT.rglob("*") if p.is_file()
    } if VAULT.exists() else {}
    check("VAULT_UNCHANGED", before_vault == after_vault,
          "no Vault file created/modified/deleted")

    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        "document": "D-OBSIDIAN-06.20_PERSISTENCE_DESIGN_REVIEW_R1",
        "timestamp_utc": now,
        "input_sha256": sha256_file(INPUT),
        "input_rows": len(rows),
        "ready_rows": len(ready),
        "expected_block_rows": len(blocked),
        "review_rows": len(review),
        "ready_periods": dict(sorted(periods.items())),
        "lineage_distribution": dict(sorted(lineages.items())),
        "metric_distribution": dict(sorted(metrics.items())),
        "authorization_boundary": "NOT_GRANTED",
        "execution_authorization": "NOT_AUTHORIZED",
        "vault_changed": False,
        "checks": checks,
        "status": "PASS" if all(checks) else "FAIL",
    }
    manifest_path = REPORTS / "PCIP11_0695_7_PERSISTENCE_DESIGN_REVIEW_R1.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# PCIP11 — 0695.7 Persistence Design Review R1",
        "",
        f"- Status: **{'PASS' if all(checks) else 'FAIL'}**",
        f"- Timestamp UTC: {now}",
        f"- Input SHA-256: `{manifest['input_sha256']}`",
        "",
        "## Population",
        f"- Release Readiness rows: {len(rows)}",
        f"- DESIGN_REVIEW_READY: {len(ready)}",
        f"- EXPECTED_BLOCK: {len(blocked)}",
        f"- REVIEW: {len(review)}",
        "",
        "## Authorization boundary",
        "- Metric persistence: **NOT_GRANTED**",
        "- KnowledgeBridge write: **NOT_GRANTED**",
        "- Vault write: **NOT_GRANTED**",
        "- Execution: **NOT_AUTHORIZED**",
        "- Vault modified: **NO**",
        "",
        "## Ready periods",
    ]
    lines.extend(f"- {p}: {n}" for p, n in sorted(periods.items()))
    lines += [
        "",
        "## Lineage distribution",
    ]
    lines.extend(f"- {p or '(blank)'}: {n}" for p, n in sorted(lineages.items()))
    lines += [
        "",
        "## Safety",
        "- This gate creates only review artifacts under `reports/`.",
        "- It does not write metric persistence records.",
        "- It does not write KnowledgeBridge.",
        "- It does not modify the Vault.",
        "- It does not execute Git operations.",
        "",
        "## Interpretation",
        "- READY means eligible to enter persistence design review.",
        "- READY does NOT mean authorized for persistence.",
        "- Execution authorization remains a separate gate.",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\nDesign CSV: {OUT_CSV}")
    print(f"Design MD : {OUT_MD}")
    print(f"Manifest  : {manifest_path}")
    print("\nAuthorization boundary:")
    print("  Metric persistence : NOT GRANTED")
    print("  KnowledgeBridge    : NOT GRANTED")
    print("  Vault write        : NOT GRANTED")
    print("  Execution         : NOT AUTHORIZED")
    print("  Vault changed     : NO")

    final = all(checks)
    print(f"\nD-OBSIDIAN-06.20: {'PASS' if final else 'FAIL'}")
    return 0 if final else 2

if __name__ == "__main__":
    raise SystemExit(main())
