from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

CONTRACT = REPORTS / "PCIP11_0695_7_EXECUTION_CONTRACT_R1.csv"
AUTH_GATE = REPORTS / "PCIP11_0695_7_EXECUTION_AUTHORIZATION_GATE_R1.csv"

OUT_CSV = REPORTS / "PCIP11_0695_7_EXPLICIT_EXECUTION_AUTHORIZATION_R1.csv"
OUT_MD = REPORTS / "PCIP11_0695_7_EXPLICIT_EXECUTION_AUTHORIZATION_R1.md"
OUT_JSON = REPORTS / "PCIP11_0695_7_EXPLICIT_EXECUTION_AUTHORIZATION_R1.json"

EXPECTED_ROWS = 31
CONTRACT_STATUS = "BOUND_TO_CONTRACT_NOT_AUTHORIZED"

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
    print("D-OBSIDIAN-06.23 — 0695.7 EXPLICIT EXECUTION AUTHORIZATION / READ-ONLY")
    print("=" * 100)

    checks = []

    def check(name, ok, detail=""):
        checks.append(bool(ok))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    check("CONTRACT_EXISTS", CONTRACT.exists(), str(CONTRACT))
    check("AUTH_GATE_EXISTS", AUTH_GATE.exists(), str(AUTH_GATE))

    if not CONTRACT.exists() or not AUTH_GATE.exists():
        print("\nD-OBSIDIAN-06.23: FAIL")
        return 2

    contract_rows = read_csv(CONTRACT)
    auth_rows = read_csv(AUTH_GATE)

    check("CONTRACT_ROWS_31", len(contract_rows) == EXPECTED_ROWS,
          f"rows={len(contract_rows)}")
    check("AUTH_GATE_ROWS_31", len(auth_rows) == EXPECTED_ROWS,
          f"rows={len(auth_rows)}")

    contract_hash = sha256_file(CONTRACT)
    auth_hash = sha256_file(AUTH_GATE)

    contract_keys = [
        (v(r, "Row"), v(r, "SHA256").upper(), v(r, "Metric"))
        for r in contract_rows
    ]
    auth_keys = [
        (v(r, "Row"), v(r, "SHA256").upper(), v(r, "Metric"))
        for r in auth_rows
    ]

    check("CONTRACT_IDENTITY_UNIQUE",
          len(contract_keys) == len(set(contract_keys)),
          f"duplicates={len(contract_keys) - len(set(contract_keys))}")
    check("AUTH_GATE_IDENTITY_UNIQUE",
          len(auth_keys) == len(set(auth_keys)),
          f"duplicates={len(auth_keys) - len(set(auth_keys))}")

    check("SCOPE_EXACT_MATCH",
          sorted(contract_keys) == sorted(auth_keys),
          "contract scope equals authorization-gate scope")

    contract_status_ok = all(v(r, "Contract_Status") == CONTRACT_STATUS for r in contract_rows)
    check("CONTRACT_STATUS_LOCKED", contract_status_ok,
          "all records bound to contract, not authorized")

    auth_lock_ok = all(
        v(r, "Metric_Persistence_Authorization") == "NOT_GRANTED"
        and v(r, "KnowledgeBridge_Write_Authorization") == "NOT_GRANTED"
        and v(r, "Vault_Write_Authorization") == "NOT_GRANTED"
        and v(r, "Execution_Status") == "NOT_AUTHORIZED"
        for r in auth_rows
    )
    check("CURRENT_AUTHORIZATION_LOCKED", auth_lock_ok,
          "all current authorization states remain locked")

    # Explicit authorization artifact is a REQUEST/DECISION PACKAGE, not a grant.
    # It freezes exactly what a future human/system authorization would have
    # to approve. No actual authorization token or write permission is emitted.
    authorization = []
    for r in contract_rows:
        authorization.append({
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
            "Contract_Status": "BOUND_TO_CONTRACT",
            "Authorization_Scope": "EXACT_31_RECORDS",
            "Authorization_Decision": "PENDING_EXPLICIT_GRANT",
            "Metric_Persistence_Authorization": "NOT_GRANTED",
            "KnowledgeBridge_Write_Authorization": "NOT_GRANTED",
            "Vault_Write_Authorization": "NOT_GRANTED",
            "Execution_Status": "NOT_AUTHORIZED",
            "Target_Binding": "PENDING_EXPLICIT_BINDING",
        })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(authorization[0].keys()))
        writer.writeheader()
        writer.writerows(authorization)

    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        "document": "PCIP11_0695_7_EXPLICIT_EXECUTION_AUTHORIZATION_R1",
        "timestamp_utc": now,
        "contract_sha256": contract_hash,
        "authorization_gate_sha256": auth_hash,
        "scope_records": EXPECTED_ROWS,
        "scope_identity_rule": "Row + SHA256 + Metric",
        "scope_exact_match": True,
        "decision": "PENDING_EXPLICIT_GRANT",
        "authorization": "NOT_GRANTED",
        "execution": "NOT_AUTHORIZED",
        "target_binding": "PENDING_EXPLICIT_BINDING",
        "vault_write": "NOT_GRANTED",
        "status": "PASS" if all(checks) else "FAIL",
        "safety": {
            "persistence_executed": False,
            "knowledgebridge_written": False,
            "vault_modified": False,
            "git_executed": False,
        },
    }
    OUT_JSON.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    md = f"""# PCIP11 — 0695.7 Explicit Execution Authorization R1

- Gate status: **{'PASS' if all(checks) else 'FAIL'}**
- Timestamp UTC: {now}
- Scope: **exactly 31 records**
- Contract SHA-256: `{contract_hash}`
- Authorization Gate SHA-256: `{auth_hash}`

## Decision state

**PENDING_EXPLICIT_GRANT**

This artifact freezes the exact authorization scope. It does **not** grant
execution permission.

## Scope

Identity key:

`Row + SHA256 + Metric`

The 31 identities must exactly match both the Execution Contract and the
Execution Authorization Gate.

## Authorization

- Metric persistence: **NOT_GRANTED**
- KnowledgeBridge write: **NOT_GRANTED**
- Vault write: **NOT_GRANTED**
- Execution: **NOT_AUTHORIZED**
- Target binding: **PENDING_EXPLICIT_BINDING**

## Safety

- Persistence executed: NO
- KnowledgeBridge written: NO
- Vault modified: NO
- Git executed: NO

## Required future authorization

A real authorization must explicitly reference:

1. Contract ID/version;
2. contract SHA-256;
3. authorization-gate SHA-256;
4. exact 31-record identity set;
5. exact persistence target;
6. execution mode;
7. expiration/revocation state;
8. approving authority/state.

Until those fields are explicitly granted, this artifact remains a
**pre-authorization package**.
"""
    OUT_MD.write_text(md, encoding="utf-8")

    print(f"\nAuthorization CSV: {OUT_CSV}")
    print(f"Authorization MD : {OUT_MD}")
    print(f"Authorization JSON: {OUT_JSON}")
    print("\nCurrent state:")
    print("  Decision          : PENDING_EXPLICIT_GRANT")
    print("  Authorization     : NOT GRANTED")
    print("  Execution         : NOT AUTHORIZED")
    print("  Target binding    : PENDING_EXPLICIT_BINDING")
    print("  Vault write       : NOT GRANTED")
    print("\nThis gate freezes the scope; it does NOT grant execution permission.")

    final = all(checks)
    print(f"\nD-OBSIDIAN-06.23: {'PASS' if final else 'FAIL'}")
    return 0 if final else 2

if __name__ == "__main__":
    raise SystemExit(main())
