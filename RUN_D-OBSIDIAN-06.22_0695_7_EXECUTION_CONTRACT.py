from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

INPUT = REPORTS / "PCIP11_0695_7_EXECUTION_AUTHORIZATION_GATE_R1.csv"
OUT_CSV = REPORTS / "PCIP11_0695_7_EXECUTION_CONTRACT_R1.csv"
OUT_MD = REPORTS / "PCIP11_0695_7_EXECUTION_CONTRACT_R1.md"
OUT_JSON = REPORTS / "PCIP11_0695_7_EXECUTION_CONTRACT_R1.json"

EXPECTED_ROWS = 31
REQUIRED_INPUT_STATUS = "BLOCKED"

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
    print("D-OBSIDIAN-06.22 — 0695.7 EXECUTION CONTRACT R1 / READ-ONLY")
    print("=" * 100)

    checks = []
    def check(name, ok, detail=""):
        checks.append(bool(ok))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    check("AUTH_GATE_INPUT_EXISTS", INPUT.exists(), str(INPUT))
    if not INPUT.exists():
        print("\nD-OBSIDIAN-06.22: FAIL")
        return 2

    rows = read_csv(INPUT)
    check("INPUT_ROWS_31", len(rows) == EXPECTED_ROWS, f"rows={len(rows)}")
    required = (
        "Row", "SHA256", "FileName", "Original_Identity", "Lineage",
        "Metric", "Value", "Original_Unit", "Resolved_Unit", "Scale",
        "Resolved_Period", "Design_Status", "Execution_Eligibility",
        "Execution_Block_Reason", "Metric_Persistence_Authorization",
        "KnowledgeBridge_Write_Authorization", "Vault_Write_Authorization",
        "Execution_Status",
    )
    check("INPUT_SCHEMA_COMPLETE",
          bool(rows) and all(k in rows[0] for k in required),
          "required schema present")

    blocked = [r for r in rows if v(r, "Execution_Eligibility") == REQUIRED_INPUT_STATUS]
    check("ALL_31_STRUCTURALLY_BLOCKED", len(blocked) == EXPECTED_ROWS,
          f"blocked={len(blocked)}")

    keys = [(v(r, "Row"), v(r, "SHA256").upper(), v(r, "Metric")) for r in rows]
    duplicates = {k for k, n in Counter(keys).items() if n > 1}
    check("IDENTITY_UNIQUE", not duplicates, f"duplicates={len(duplicates)}")

    auth_locked = all(
        v(r, "Metric_Persistence_Authorization") == "NOT_GRANTED"
        and v(r, "KnowledgeBridge_Write_Authorization") == "NOT_GRANTED"
        and v(r, "Vault_Write_Authorization") == "NOT_GRANTED"
        and v(r, "Execution_Status") == "NOT_AUTHORIZED"
        for r in rows
    )
    check("AUTHORIZATION_LOCKED", auth_locked,
          "all 31 remain NOT_GRANTED / NOT_AUTHORIZED")

    # Contract design. These are specifications, not executed operations.
    contract = {
        "contract_id": "PCIP11_0695_7_EXECUTION_CONTRACT_R1",
        "version": "R1",
        "scope": "31 records from 0695.7 Release Readiness / Design Review",
        "execution_mode": "CONTROLLED_SINGLE_RECORD_ATOMIC",
        "target_binding": "EXPLICIT_REQUIRED_BEFORE_AUTHORIZATION",
        "identity_key": ["Row", "SHA256", "Metric"],
        "source_identity": ["FileName", "Original_Identity", "Lineage"],
        "metric_identity": ["Metric", "Value", "Original_Unit", "Resolved_Unit", "Scale", "Resolved_Period"],
        "idempotency": {
            "key": ["SHA256", "Metric"],
            "existing_identical": "NO_OP_AND_AUDIT_AS_ALREADY_PRESENT",
            "existing_conflicting": "BLOCK_NO_OVERWRITE",
        },
        "collision_policy": "BLOCK_AND_ESCALATE",
        "overwrite_policy": "DENY_BY_DEFAULT",
        "atomicity": "ONE_RECORD_AT_A_TIME",
        "partial_failure": "STOP_NEW_WRITES_AND_PRESERVE_AUDIT_TRAIL",
        "rollback": "NO_DESTRUCTIVE_ROLLBACK; COMPENSATING_ACTION_REQUIRES_SEPARATE_AUTHORIZATION",
        "audit": {
            "required": True,
            "per_record": True,
            "fields": [
                "timestamp",
                "contract_id",
                "Row",
                "SHA256",
                "Metric",
                "target",
                "action",
                "result",
                "preexisting_state",
                "post_state",
            ],
        },
        "scope_lock": {
            "source": str(INPUT),
            "input_sha256": sha256_file(INPUT),
            "records": EXPECTED_ROWS,
            "membership_rule": "EXACT_IDENTITY_SET_FROM_INPUT",
        },
        "authorization": {
            "current": "NOT_GRANTED",
            "required_next_state": "EXPLICITLY_GRANTED",
            "grant_must_reference_contract": True,
        },
        "vault": {
            "current_operation": "NONE",
            "write_allowed_in_06_22": False,
        },
        "status": "CONTRACT_DEFINED_NOT_AUTHORIZED",
    }

    now = datetime.now(timezone.utc).isoformat()
    contract["timestamp_utc"] = now

    output = []
    for r in rows:
        output.append({
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
            "Contract_Status": "BOUND_TO_CONTRACT_NOT_AUTHORIZED",
            "Target_Status": "NOT_BOUND",
            "Idempotency": "ENFORCED_BY_CONTRACT",
            "Collision_Policy": "BLOCK_AND_ESCALATE",
            "Overwrite_Policy": "DENY_BY_DEFAULT",
            "Atomicity": "ONE_RECORD_AT_A_TIME",
            "Execution_Status": "NOT_AUTHORIZED",
        })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(output[0].keys()))
        writer.writeheader()
        writer.writerows(output)

    OUT_JSON.write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    md = f"""# PCIP11 — 0695.7 Execution Contract R1

- Status: **{'PASS' if all(checks) else 'FAIL'}**
- Timestamp UTC: {now}
- Scope: **31 records**
- Input SHA-256: `{contract['scope_lock']['input_sha256']}`
- Contract status: **CONTRACT_DEFINED_NOT_AUTHORIZED**

## Execution Contract

### Target
Persistence target must be explicitly bound before authorization. No target is
implicitly inferred by this contract.

### Identity
Primary scope identity:

`Row + SHA256 + Metric`

Source identity:

`FileName + Original_Identity + Lineage`

Metric identity:

`Metric + Value + Original_Unit + Resolved_Unit + Scale + Resolved_Period`

### Idempotency
- Existing identical record: **NO-OP + audit as already present**
- Existing conflicting record: **BLOCK + no overwrite**

### Collision
**BLOCK_AND_ESCALATE**

### Overwrite
**DENY_BY_DEFAULT**

### Atomicity
**ONE_RECORD_AT_A_TIME**

### Partial failure
Stop new writes and preserve the audit trail. Do not silently continue.

### Rollback
No destructive rollback is permitted by this contract. Any compensating
action requires a separate authorization.

### Audit
Every record requires a timestamped audit entry containing contract ID,
identity, target, action, result, pre-existing state and post-state.

## Authorization

Current state:

- Metric persistence: **NOT_GRANTED**
- KnowledgeBridge: **NOT_GRANTED**
- Vault write: **NOT_GRANTED**
- Execution: **NOT_AUTHORIZED**

A future authorization must explicitly reference this contract ID/version.

## Scope Lock

The execution population is exactly the 31 records from:

`PCIP11_0695_7_EXECUTION_AUTHORIZATION_GATE_R1.csv`

Input SHA-256 is frozen in the JSON manifest.

## Safety

This 06.22 gate only defines the contract. It performs:

- no metric persistence;
- no KnowledgeBridge write;
- no Vault write;
- no Git operation.
"""
    OUT_MD.write_text(md, encoding="utf-8")

    print(f"\nContract CSV: {OUT_CSV}")
    print(f"Contract MD : {OUT_MD}")
    print(f"Contract JSON: {OUT_JSON}")
    print("\nContract boundary:")
    print("  Target binding     : EXPLICIT REQUIRED")
    print("  Idempotency        : ENFORCED")
    print("  Collision policy   : BLOCK_AND_ESCALATE")
    print("  Overwrite          : DENY_BY_DEFAULT")
    print("  Atomicity          : ONE_RECORD_AT_A_TIME")
    print("  Authorization      : NOT GRANTED")
    print("  Execution          : NOT AUTHORIZED")
    print("  Vault write        : NOT GRANTED")

    final = all(checks)
    print(f"\nD-OBSIDIAN-06.22: {'PASS' if final else 'FAIL'}")
    return 0 if final else 2

if __name__ == "__main__":
    raise SystemExit(main())
