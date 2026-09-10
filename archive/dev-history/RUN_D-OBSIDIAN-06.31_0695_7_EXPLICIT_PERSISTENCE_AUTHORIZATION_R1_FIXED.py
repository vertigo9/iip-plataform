#!/usr/bin/env python3
"""
D-OBSIDIAN-06.31 — 0695.7 EXPLICIT PERSISTENCE AUTHORIZATION R1

Controlled authorization artifact.

This script DOES NOT write the Vault, KnowledgeBridge, metric store, or source data.
It creates an auditable authorization manifest only after validating the exact
06.22 contract + 06.24 target-binding chain for the 31 release-ready records.

User approval in the current execution flow is treated as the explicit grant.
The grant is scoped, fingerprinted, fail-closed, and overwrite-denying.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_ROWS = 31
CONTRACT_GLOB = "reports/**/PCIP11_0695_7_EXECUTION_CONTRACT_R1.csv"
BINDING_GLOB = "reports/**/*TARGET_BINDING*.csv"
OUT_DIR = Path("reports/PCIP11_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION_R1")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def latest(glob_pattern: str) -> Path:
    files = [p for p in Path.cwd().glob(glob_pattern) if p.is_file()]
    if not files:
        raise FileNotFoundError(f"Fonte nao encontrada: {glob_pattern}")
    return max(files, key=lambda p: p.stat().st_mtime)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def norm(v: object) -> str:
    return str(v or "").strip()


def main() -> int:
    repo = Path.cwd().resolve()
    contract = latest(CONTRACT_GLOB)
    binding = latest(BINDING_GLOB)

    contract_rows = read_csv(contract)
    binding_rows = read_csv(binding)

    checks: list[tuple[str, bool, str]] = []

    checks.append(("CONTRACT_31_ROWS", len(contract_rows) == EXPECTED_ROWS,
                   f"expected={EXPECTED_ROWS} actual={len(contract_rows)}"))
    checks.append(("TARGET_BINDING_31_ROWS", len(binding_rows) == EXPECTED_ROWS,
                   f"expected={EXPECTED_ROWS} actual={len(binding_rows)}"))

    contract_fields = set(contract_rows[0]) if contract_rows else set()
    binding_fields = set(binding_rows[0]) if binding_rows else set()

    required_contract = {"Row", "SHA256", "Metric"}
    checks.append(("CONTRACT_REQUIRED_FIELDS", required_contract <= contract_fields,
                   f"missing={sorted(required_contract - contract_fields)}"))

    required_binding_any = {"Target_Relative", "Target_Binding"}
    checks.append(("BINDING_TARGET_FIELD_PRESENT",
                   bool(required_binding_any & binding_fields),
                   f"fields={sorted(binding_fields)}"))

    contract_keys = {
        (norm(r.get("Row")), norm(r.get("SHA256")), norm(r.get("Metric")))
        for r in contract_rows
    }
    checks.append(("CONTRACT_IDENTITY_UNIQUE",
                   len(contract_keys) == len(contract_rows),
                   f"unique={len(contract_keys)} rows={len(contract_rows)}"))

    binding_keys = {
        (norm(r.get("Row")), norm(r.get("SHA256")), norm(r.get("Metric")))
        for r in binding_rows
    }
    checks.append(("BINDING_IDENTITY_UNIQUE",
                   len(binding_keys) == len(binding_rows),
                   f"unique={len(binding_keys)} rows={len(binding_rows)}"))

    checks.append(("SCOPE_EXACT_MATCH",
                   contract_keys == binding_keys,
                   f"contract_keys={len(contract_keys)} binding_keys={len(binding_keys)}"))

    target_values = []
    for r in binding_rows:
        # 06.24 R2 contract: Target_Relative is the canonical repository-relative
        # destination; Target_Binding is the binding decision/status descriptor.
        target = norm(r.get("Target_Relative"))
        target_values.append(target)

    checks.append(("TARGETS_NONEMPTY",
                   all(target_values),
                   f"empty={sum(not x for x in target_values)}"))

    checks.append(("TARGETS_04_EVIDENCE",
                   all(x.replace("\\", "/").lower().startswith("vault/04_evidence/")
                       for x in target_values),
                   "all Target_Relative values must resolve under vault/04_Evidence"))

    if "Target_Status" in binding_fields:
        checks.append(("TARGET_STATUS_READY",
                       all(norm(r.get("Target_Status")).upper() in {"READY", "BOUND", "PASS"}
                           for r in binding_rows),
                       "all Target_Status values must be READY/BOUND/PASS"))
    if "Target_Binding" in binding_fields:
        checks.append(("TARGET_BINDING_PRESENT",
                       all(norm(r.get("Target_Binding")) for r in binding_rows),
                       "all Target_Binding values must be populated"))

    gate = all(ok for _, ok, _ in checks)
    if not gate:
        print("=" * 96)
        print("D-OBSIDIAN-06.31 — 0695.7 EXPLICIT PERSISTENCE AUTHORIZATION R1")
        print("=" * 96)
        for name, ok, detail in checks:
            print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
        print("AUTHORIZATION: NOT GRANTED")
        print("D-OBSIDIAN-06.31: BLOCKED")
        return 1

    timestamp = datetime.now(timezone.utc).isoformat()
    contract_sha = sha256_file(contract)
    binding_sha = sha256_file(binding)

    auth_id = "D-OBSIDIAN-06.31-0695.7"
    rows = []
    for r in contract_rows:
        key = (norm(r.get("Row")), norm(r.get("SHA256")), norm(r.get("Metric")))
        b = next(
            x for x in binding_rows
            if (norm(x.get("Row")), norm(x.get("SHA256")), norm(x.get("Metric"))) == key
        )
        target = norm(b.get("Target_Relative"))
        rows.append({
            "Authorization_ID": auth_id,
            "Authorization_Status": "GRANTED",
            "Authorized_At_UTC": timestamp,
            "Contract_ID": "PCIP11-0695.7-EXECUTION-CONTRACT-R1",
            "Contract_SHA256": contract_sha,
            "Target_Binding_SHA256": binding_sha,
            "Row": key[0],
            "SHA256": key[1],
            "Metric": key[2],
            "Target_Relative": target,
            "Target_Binding": norm(b.get("Target_Binding")),
            "Metric_Persistence_Authorization": "GRANTED",
            "KnowledgeBridge_Write_Authorization": "GRANTED",
            "Vault_Write_Authorization": "GRANTED",
            "Overwrite_Policy": "DENY_BY_DEFAULT",
            "Conflict_Policy": "BLOCK",
            "Collision_Policy": "BLOCK_AND_ESCALATE",
            "Atomicity": "ONE_RECORD_AT_A_TIME",
            "Scope_Lock": "EXACT_31_RECORDS",
        })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / "PCIP11_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION_R1.csv"
    md_path = OUT_DIR / "PCIP11_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION_R1.md"
    json_path = OUT_DIR / "PCIP11_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION_R1.json"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    md = [
        "# PCIP11 — 0695.7 Explicit Persistence Authorization R1",
        "",
        "## Authorization",
        f"- Status: **GRANTED**",
        f"- Authorization ID: `{auth_id}`",
        f"- Authorized at UTC: `{timestamp}`",
        f"- Scope: **exactly 31 records**",
        f"- Contract SHA-256: `{contract_sha}`",
        f"- Target-binding SHA-256: `{binding_sha}`",
        "",
        "## Controls",
        "- Metric persistence: GRANTED",
        "- KnowledgeBridge write: GRANTED",
        "- Vault write: GRANTED",
        "- Overwrite: DENY_BY_DEFAULT",
        "- Conflict: BLOCK",
        "- Collision: BLOCK_AND_ESCALATE",
        "- Atomicity: ONE_RECORD_AT_A_TIME",
        "- Scope lock: EXACT_31_RECORDS",
        "",
        "## Pre-authorization checks",
    ]
    md.extend(f"- [{'PASS' if ok else 'FAIL'}] {name}: {detail}"
              for name, ok, detail in checks)
    md += [
        "",
        "## Safety boundary",
        "- This artifact grants permission for the separately controlled persistence executor.",
        "- This script itself performs no Vault, KnowledgeBridge, metric-store, or source-data write.",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "Authorization_ID": auth_id,
        "Authorization_Status": "GRANTED",
        "Authorized_At_UTC": timestamp,
        "Scope": "EXACT_31_RECORDS",
        "Contract": {
            "ID": "PCIP11-0695.7-EXECUTION-CONTRACT-R1",
            "SHA256": contract_sha,
        },
        "Target_Binding_SHA256": binding_sha,
        "Controls": {
            "Metric_Persistence": "GRANTED",
            "KnowledgeBridge_Write": "GRANTED",
            "Vault_Write": "GRANTED",
            "Overwrite": "DENY_BY_DEFAULT",
            "Conflict": "BLOCK",
            "Collision": "BLOCK_AND_ESCALATE",
            "Atomicity": "ONE_RECORD_AT_A_TIME",
        },
        "Records": rows,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")

    print("=" * 96)
    print("D-OBSIDIAN-06.31 — 0695.7 EXPLICIT PERSISTENCE AUTHORIZATION R1")
    print("=" * 96)
    for name, ok, detail in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    print(f"Authorization: GRANTED")
    print(f"Scope: {len(rows)} records")
    print(f"Contract SHA256: {contract_sha}")
    print(f"Target binding SHA256: {binding_sha}")
    print(f"Reports: {OUT_DIR}")
    print("Vault modified: NO")
    print("D-OBSIDIAN-06.31: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
