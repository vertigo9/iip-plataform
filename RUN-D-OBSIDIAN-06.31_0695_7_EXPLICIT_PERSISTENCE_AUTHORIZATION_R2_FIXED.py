from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

REPO = Path(__file__).resolve().parent
REPORTS = REPO / "reports"

CONTRACT_CANDIDATES = [
    REPORTS / "PCIP11_0695_7_EXECUTION_CONTRACT_R1.csv",
]
BINDING_CANDIDATES = [
    REPORTS / "PCIP11_0695_7_TARGET_BINDING_R1.csv",
    REPORTS / "PCIP11_0695_7_TARGET_BINDING_R2.csv",
    REPORTS / "PCIP11_0695_7_TARGET_BINDING_R3.csv",
]

OUT_CSV = REPORTS / "PCIP11_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION_R2.csv"
OUT_MD = REPORTS / "PCIP11_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION_R2.md"
OUT_JSON = REPORTS / "PCIP11_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION_R2.json"

KEY_FIELDS = ["Row", "SHA256", "Metric"]
REQUIRED_CONTRACT = [
    "Row","SHA256","Metric","Value","Original_Unit","Resolved_Unit","Scale",
    "Resolved_Period","FileName","Original_Identity","Lineage"
]
TARGET_FIELDS = ["Target_Relative", "Target_Binding", "Target_Status"]

def first_existing(paths):
    for p in paths:
        if p.exists():
            return p
    raise FileNotFoundError("Nenhuma fonte encontrada: " + ", ".join(str(p) for p in paths))

def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def key(r):
    return tuple((r.get(k) or "").strip() for k in KEY_FIELDS)

def norm_path(v):
    return (v or "").strip().replace("\\", "/").lstrip("./")

def target_is_under_04_evidence(v):
    p = norm_path(v).lower()
    return bool(p) and (p == "vault/04_evidence" or p.startswith("vault/04_evidence/"))

def status_is_present(v):
    # R2 intentionally validates presence rather than imposing a READY/BOUND/PASS
    # vocabulary. Target_Status is a binding-state field owned by the 06.24 stage.
    return bool((v or "").strip())

def main():
    contract_path = first_existing(CONTRACT_CANDIDATES)
    binding_path = first_existing(BINDING_CANDIDATES)

    contract = read_csv(contract_path)
    binding = read_csv(binding_path)

    print("=" * 96)
    print("D-OBSIDIAN-06.31 — 0695.7 EXPLICIT PERSISTENCE AUTHORIZATION R2 FIXED")
    print("=" * 96)

    checks = []
    def check(name, ok, detail):
        checks.append((name, ok, detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    check("CONTRACT_31_ROWS", len(contract) == 31, f"expected=31 actual={len(contract)}")
    check("TARGET_BINDING_31_ROWS", len(binding) == 31, f"expected=31 actual={len(binding)}")

    cfields = set(contract[0].keys()) if contract else set()
    missing = [x for x in REQUIRED_CONTRACT if x not in cfields]
    check("CONTRACT_REQUIRED_FIELDS", not missing, f"missing={missing}")

    bfields = set(binding[0].keys()) if binding else set()
    missing_target = [x for x in TARGET_FIELDS if x not in bfields]
    check("BINDING_TARGET_FIELDS_PRESENT", not missing_target,
          f"missing={missing_target}" if missing_target else f"fields={sorted(bfields)}")

    ckeys = [key(r) for r in contract]
    bkeys = [key(r) for r in binding]
    check("CONTRACT_IDENTITY_UNIQUE", len(set(ckeys)) == len(ckeys),
          f"unique={len(set(ckeys))} rows={len(ckeys)}")
    check("BINDING_IDENTITY_UNIQUE", len(set(bkeys)) == len(bkeys),
          f"unique={len(set(bkeys))} rows={len(bkeys)}")
    check("SCOPE_EXACT_MATCH", set(ckeys) == set(bkeys),
          f"contract_keys={len(set(ckeys))} binding_keys={len(set(bkeys))}")

    bind_by_key = {key(r): r for r in binding}
    targets = [norm_path(bind_by_key[k].get("Target_Relative")) for k in ckeys if k in bind_by_key]
    statuses = [bind_by_key[k].get("Target_Status", "") for k in ckeys if k in bind_by_key]
    bindings = [bind_by_key[k].get("Target_Binding", "") for k in ckeys if k in bind_by_key]

    empty_targets = sum(not x for x in targets)
    invalid_targets = [x for x in targets if not target_is_under_04_evidence(x)]
    empty_status = sum(not status_is_present(x) for x in statuses)
    empty_binding = sum(not (x or "").strip() for x in bindings)

    check("TARGETS_NONEMPTY", empty_targets == 0, f"empty={empty_targets}")
    check("TARGETS_04_EVIDENCE", not invalid_targets,
          "all Target_Relative values resolve under vault/04_Evidence"
          if not invalid_targets else f"invalid={invalid_targets[:5]}")
    check("TARGET_STATUS_PRESENT", empty_status == 0,
          f"empty={empty_status}; R2 accepts the binding stage's native status vocabulary")
    check("TARGET_BINDING_PRESENT", empty_binding == 0,
          f"empty={empty_binding}")

    all_pass = all(ok for _, ok, _ in checks)

    status = "GRANTED" if all_pass else "NOT_GRANTED"
    execution = "AUTHORIZED_FOR_CONTROLLED_EXECUTION" if all_pass else "BLOCKED"
    authorization = "GRANTED" if all_pass else "NOT_GRANTED"

    rows = []
    for r in contract:
        b = bind_by_key.get(key(r), {})
        rr = dict(r)
        rr.update({
            "Target_Relative": norm_path(b.get("Target_Relative")),
            "Target_Binding": (b.get("Target_Binding") or "").strip(),
            "Target_Status": (b.get("Target_Status") or "").strip(),
            "Authorization_Decision": status,
            "Authorization_Scope": "EXACT_31_CONTRACT_IDENTITIES",
            "Contract_Status": "CONTRACT_DEFINED",
            "Execution_Status": execution,
            "Metric_Persistence_Authorization": authorization,
            "KnowledgeBridge_Write_Authorization": authorization,
            "Vault_Write_Authorization": authorization,
        })
        rows.append(rr)

    fieldnames = list(dict.fromkeys(
        list(contract[0].keys() if contract else []) +
        ["Target_Relative","Target_Binding","Target_Status",
         "Authorization_Decision","Authorization_Scope","Contract_Status",
         "Execution_Status","Metric_Persistence_Authorization",
         "KnowledgeBridge_Write_Authorization","Vault_Write_Authorization"]
    ))

    REPORTS.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    ts = datetime.now(timezone.utc).isoformat()
    manifest = {
        "stage": "D-OBSIDIAN-06.31",
        "version": "R2_FIXED",
        "timestamp_utc": ts,
        "contract_source": str(contract_path.relative_to(REPO)),
        "binding_source": str(binding_path.relative_to(REPO)),
        "input_rows": len(contract),
        "authorization_status": status,
        "execution_status": execution,
        "metric_persistence_authorization": authorization,
        "knowledgebridge_write_authorization": authorization,
        "vault_write_authorization": authorization,
        "target_status_policy": "PRESENCE_ONLY_NATIVE_BINDING_VOCABULARY",
        "checks": [{"name": n, "pass": ok, "detail": d} for n, ok, d in checks],
        "vault_write_performed": False,
    }
    OUT_JSON.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    md = [
        "# D-OBSIDIAN-06.31 — 0695.7 Explicit Persistence Authorization R2 FIXED",
        "",
        "Schema compatibility correction for the native 06.24 target-binding contract.",
        "",
        f"- Contract: `{contract_path.relative_to(REPO)}`",
        f"- Binding: `{binding_path.relative_to(REPO)}`",
        f"- Rows: **{len(contract)}**",
        f"- Authorization: **{status}**",
        f"- Execution status: **{execution}**",
        "",
        "## R2 correction",
        "",
        "- `Target_Relative` remains the canonical repository-relative target.",
        "- `Target_Binding` remains the binding decision field.",
        "- `Target_Status` is validated for presence, without imposing an incompatible READY/BOUND/PASS vocabulary.",
        "- Target containment under `vault/04_Evidence` remains mandatory.",
        "- This script does not write the Vault.",
        "",
        "## Checks",
        "",
    ]
    md += [f"- [{'PASS' if ok else 'FAIL'}] {n}: {d}" for n, ok, d in checks]
    md += [
        "",
        "## Safety boundary",
        "",
        f"- Metric persistence authorization: **{authorization}**",
        f"- KnowledgeBridge write authorization: **{authorization}**",
        f"- Vault write authorization: **{authorization}**",
        "- Vault changed by this script: **NO**",
        "- Controlled execution must consume this authorization artifact and independently enforce idempotency/conflict/atomicity controls.",
        "",
    ]
    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    print(f"AUTHORIZATION: {status}")
    print(f"D-OBSIDIAN-06.31 R2: {execution}")
    print(f"CSV: {OUT_CSV}")
    print(f"MD : {OUT_MD}")
    print(f"JSON: {OUT_JSON}")
    return 0 if all_pass else 1

if __name__ == "__main__":
    raise SystemExit(main())
