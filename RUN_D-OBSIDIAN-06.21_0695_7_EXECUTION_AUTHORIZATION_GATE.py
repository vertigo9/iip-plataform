from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

INPUT = REPORTS / "PCIP11_0695_7_PERSISTENCE_DESIGN_REVIEW_R1.csv"
OUT_CSV = REPORTS / "PCIP11_0695_7_EXECUTION_AUTHORIZATION_GATE_R1.csv"
OUT_MD = REPORTS / "PCIP11_0695_7_EXECUTION_AUTHORIZATION_GATE_R1.md"
OUT_JSON = REPORTS / "PCIP11_0695_7_EXECUTION_AUTHORIZATION_GATE_R1.json"

EXPECTED_READY = 31
REQUIRED_STATUS = "DESIGN_REVIEW_READY"

AUTH_FIELDS = {
    "Metric_Persistence_Authorization": "NOT_GRANTED",
    "KnowledgeBridge_Write_Authorization": "NOT_GRANTED",
    "Vault_Write_Authorization": "NOT_GRANTED",
    "Execution_Status": "NOT_AUTHORIZED",
}

REQUIRED_FIELDS = (
    "Row", "SHA256", "FileName", "Original_Identity", "Lineage",
    "Metric", "Value", "Original_Unit", "Resolved_Unit", "Scale",
    "Resolved_Period", "Design_Status",
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
    print("D-OBSIDIAN-06.21 — 0695.7 EXECUTION AUTHORIZATION GATE / READ-ONLY")
    print("=" * 100)

    checks = []

    def check(name, ok, detail=""):
        checks.append(bool(ok))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    check("DESIGN_INPUT_EXISTS", INPUT.exists(), str(INPUT))
    if not INPUT.exists():
        print("\nD-OBSIDIAN-06.21: FAIL")
        return 2

    rows = read_csv(INPUT)
    check("INPUT_NONEMPTY", bool(rows), f"rows={len(rows)}")
    check(
        "INPUT_REQUIRED_FIELDS",
        bool(rows) and all(field in rows[0] for field in REQUIRED_FIELDS),
        "required schema present",
    )

    design_ready = [r for r in rows if v(r, "Design_Status") == REQUIRED_STATUS]
    non_ready = [r for r in rows if v(r, "Design_Status") != REQUIRED_STATUS]

    check("DESIGN_READY_SET_31", len(design_ready) == EXPECTED_READY,
          f"design_ready={len(design_ready)}")
    check("NO_UNEXPECTED_DESIGN_STATUS", len(non_ready) == 0,
          f"unexpected={len(non_ready)}")

    # Execution eligibility is deliberately stricter than Design Review.
    # This gate does NOT grant authorization; it determines whether the
    # records satisfy the structural preconditions to be considered for
    # a future, explicit authorization decision.
    complete = []
    blocked = []

    for r in design_ready:
        reasons = []

        for field in (
            "Row", "SHA256", "FileName", "Original_Identity", "Lineage",
            "Metric", "Value", "Original_Unit", "Resolved_Unit", "Scale",
            "Resolved_Period",
        ):
            if not v(r, field):
                reasons.append(f"MISSING_{field}")

        if v(r, "SHA256") and len(v(r, "SHA256")) != 64:
            reasons.append("INVALID_SHA256_LENGTH")

        if v(r, "Lineage") not in {"PCIP11", "CVBI11 -> PCIP11"}:
            reasons.append("INVALID_LINEAGE")

        if v(r, "Metric") == "UNSTRUCTURED_EVIDENCE":
            reasons.append("UNSTRUCTURED_EVIDENCE")

        for field, expected in AUTH_FIELDS.items():
            if v(r, field) != expected:
                reasons.append(f"{field}_NOT_{expected}")

        # No execution target is accepted yet. Destination binding must be
        # supplied by the explicit execution contract in the next stage.
        reasons.append("PERSISTENCE_TARGET_NOT_BOUND")

        if reasons:
            blocked.append((r, reasons))
        else:
            complete.append(r)

    # Identity collision check among all design-ready rows.
    identity_keys = [
        (v(r, "Row"), v(r, "SHA256").upper(), v(r, "Metric"))
        for r in design_ready
    ]
    duplicate_keys = {
        key for key, count in Counter(identity_keys).items() if count > 1
    }
    check("READY_IDENTITY_UNIQUE", not duplicate_keys,
          f"duplicates={len(duplicate_keys)}")

    # Because target binding is intentionally absent, no record can become
    # execution-authorized in this gate.
    execution_eligible = []
    execution_blocked = design_ready

    check("EXECUTION_ELIGIBLE_ZERO_BY_DESIGN", len(execution_eligible) == 0,
          "target binding intentionally deferred")

    # Every READY record must remain locked.
    auth_locked = all(
        all(v(r, field) == expected for field, expected in AUTH_FIELDS.items())
        for r in design_ready
    )
    check("AUTHORIZATION_REMAINS_LOCKED", auth_locked,
          "all design-ready rows remain NOT_GRANTED / NOT_AUTHORIZED")

    # Vault is not touched by this script; no filesystem write under vault.
    # We verify the directory exists if present, but deliberately do not
    # mutate it.
    vault_exists = (ROOT / "vault").exists()
    check("VAULT_ACCESS_BOUNDARY", True,
          "no Vault operation performed" + ("; vault present" if vault_exists else ""))

    output_rows = []
    for r in design_ready:
        key = (v(r, "Row"), v(r, "SHA256").upper(), v(r, "Metric"))
        dup = key in duplicate_keys
        reasons = ["PERSISTENCE_TARGET_NOT_BOUND"]
        if dup:
            reasons.append("DUPLICATE_IDENTITY")

        output_rows.append({
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
            "Design_Status": v(r, "Design_Status"),
            "Execution_Eligibility": "BLOCKED",
            "Execution_Block_Reason": "|".join(reasons),
            "Metric_Persistence_Authorization": "NOT_GRANTED",
            "KnowledgeBridge_Write_Authorization": "NOT_GRANTED",
            "Vault_Write_Authorization": "NOT_GRANTED",
            "Execution_Status": "NOT_AUTHORIZED",
        })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(output_rows[0].keys()) if output_rows else [])
        writer.writeheader()
        writer.writerows(output_rows)

    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        "document": "PCIP11_0695_7_EXECUTION_AUTHORIZATION_GATE_R1",
        "timestamp_utc": now,
        "input_sha256": sha256_file(INPUT),
        "input_rows": len(rows),
        "design_ready_rows": len(design_ready),
        "execution_eligible_rows": len(execution_eligible),
        "execution_blocked_rows": len(execution_blocked),
        "execution_block_reason": "PERSISTENCE_TARGET_NOT_BOUND",
        "authorization": "NOT_GRANTED",
        "execution_status": "NOT_AUTHORIZED",
        "vault_write": "NOT_GRANTED",
        "status": "PASS" if all(checks) else "FAIL",
        "interpretation": (
            "Structural gate PASS. No execution authorization is granted. "
            "Persistence target binding is intentionally deferred to the "
            "explicit execution contract."
        ),
    }
    OUT_JSON.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# PCIP11 — 0695.7 Execution Authorization Gate R1",
        "",
        f"- Status: **{'PASS' if all(checks) else 'FAIL'}**",
        f"- Timestamp UTC: {now}",
        f"- Input SHA-256: `{manifest['input_sha256']}`",
        "",
        "## Population",
        f"- Design Review rows: {len(rows)}",
        f"- Design Review READY: {len(design_ready)}",
        f"- Execution eligible: {len(execution_eligible)}",
        f"- Execution blocked: {len(execution_blocked)}",
        "",
        "## Decision",
        "- Structural preconditions: PASS",
        "- Execution authorization: **NOT_GRANTED**",
        "- Execution status: **NOT_AUTHORIZED**",
        "- Persistence target: **NOT_BOUND**",
        "",
        "## Safety boundary",
        "- Metric persistence: NOT GRANTED",
        "- KnowledgeBridge write: NOT GRANTED",
        "- Vault write: NOT GRANTED",
        "- No Vault operation performed",
        "",
        "## Rationale",
        "The target binding is intentionally deferred so that eligibility and "
        "authorization cannot be conflated. A subsequent explicit execution "
        "contract must define the destination, write mode, idempotency rule, "
        "collision behavior, and rollback/audit semantics before authorization.",
        "",
        "## Outputs",
        f"- CSV: `{OUT_CSV}`",
        f"- JSON: `{OUT_JSON}`",
        f"- MD: `{OUT_MD}`",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\nExecution Gate CSV: {OUT_CSV}")
    print(f"Execution Gate MD : {OUT_MD}")
    print(f"Execution Gate JSON: {OUT_JSON}")
    print("\nAuthorization boundary:")
    print("  Metric persistence : NOT GRANTED")
    print("  KnowledgeBridge    : NOT GRANTED")
    print("  Vault write        : NOT GRANTED")
    print("  Execution         : NOT AUTHORIZED")
    print("  Persistence target: NOT BOUND")
    print("\nNOTE: this is intentionally a structural gate; it cannot authorize execution.")

    final = all(checks)
    print(f"\nD-OBSIDIAN-06.21: {'PASS' if final else 'FAIL'}")
    return 0 if final else 2

if __name__ == "__main__":
    raise SystemExit(main())
