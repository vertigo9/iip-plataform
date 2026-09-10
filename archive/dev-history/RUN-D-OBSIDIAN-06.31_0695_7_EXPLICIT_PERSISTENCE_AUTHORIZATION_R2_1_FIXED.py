from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent
REPORTS = REPO / "reports"

CONTRACT = REPORTS / "PCIP11_0695_7_EXECUTION_CONTRACT_R1.csv"
BINDING_CANDIDATES = [
    REPORTS / "PCIP11_0695_7_TARGET_BINDING_R3.csv",
    REPORTS / "PCIP11_0695_7_TARGET_BINDING_R2.csv",
    REPORTS / "PCIP11_0695_7_TARGET_BINDING_R1.csv",
]

OUT_CSV = REPORTS / "PCIP11_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION_R2_1.csv"
OUT_MD = REPORTS / "PCIP11_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION_R2_1.md"
OUT_JSON = REPORTS / "PCIP11_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION_R2_1.json"

KEY_FIELDS = ["Row", "SHA256", "Metric"]
TARGET_ALIASES = [
    "Target_Relative",
    "Target_Path",
    "Target",
    "Target_Relative_Path",
]
STATUS_ALIASES = ["Target_Status", "Binding_Status", "Status"]
BINDING_ALIASES = ["Target_Binding", "Binding_Decision", "Target_Decision"]

def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def first_nonempty(row, aliases):
    for name in aliases:
        if name in row and str(row[name]).strip():
            return str(row[name]).strip()
    return ""

def choose_binding():
    available = []
    for p in BINDING_CANDIDATES:
        if p.exists():
            rows = read_csv(p)
            fields = set(rows[0].keys()) if rows else set()
            target = next((x for x in TARGET_ALIASES if x in fields), None)
            available.append((p, rows, fields, target))
            if len(rows) == 31 and target:
                return p, rows, fields
    # fail closed: do not silently select a schema without a target field
    detail = "; ".join(f"{p.name}: target_field={t}" for p,_,_,t in available)
    raise RuntimeError(
        "Nenhum Target Binding compatível encontrado (31 rows + target field). " + detail
    )

def key(row):
    return tuple(str(row.get(k, "")).strip() for k in KEY_FIELDS)

def norm_target(value):
    return str(value or "").strip().replace("\\", "/").lstrip("./")

def under_evidence(value):
    p = norm_target(value).lower()
    return p.startswith("vault/04_evidence/") or p == "vault/04_evidence"

def main():
    contract = read_csv(CONTRACT)
    binding_path, binding, binding_fields = choose_binding()

    print("=" * 96)
    print("D-OBSIDIAN-06.31 — 0695.7 EXPLICIT PERSISTENCE AUTHORIZATION R2.1 FIXED")
    print("=" * 96)

    checks = []
    def chk(name, ok, detail):
        checks.append((name, ok, detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    chk("CONTRACT_31_ROWS", len(contract) == 31, f"expected=31 actual={len(contract)}")
    chk("TARGET_BINDING_31_ROWS", len(binding) == 31, f"expected=31 actual={len(binding)}")

    required = [
        "Row","SHA256","Metric","Value","Original_Unit","Resolved_Unit","Scale",
        "Resolved_Period","FileName","Original_Identity","Lineage"
    ]
    cfields = set(contract[0].keys()) if contract else set()
    missing = [x for x in required if x not in cfields]
    chk("CONTRACT_REQUIRED_FIELDS", not missing, f"missing={missing}")

    target_field = next((x for x in TARGET_ALIASES if x in binding_fields), None)
    status_field = next((x for x in STATUS_ALIASES if x in binding_fields), None)
    binding_field = next((x for x in BINDING_ALIASES if x in binding_fields), None)

    chk(
        "BINDING_TARGET_FIELD_PRESENT",
        target_field is not None,
        f"selected={target_field or 'NONE'} available={sorted(binding_fields)}"
    )

    ckeys = [key(r) for r in contract]
    bkeys = [key(r) for r in binding]
    chk("CONTRACT_IDENTITY_UNIQUE", len(set(ckeys)) == len(ckeys),
        f"unique={len(set(ckeys))} rows={len(ckeys)}")
    chk("BINDING_IDENTITY_UNIQUE", len(set(bkeys)) == len(bkeys),
        f"unique={len(set(bkeys))} rows={len(bkeys)}")
    chk("SCOPE_EXACT_MATCH", set(ckeys) == set(bkeys),
        f"contract_keys={len(set(ckeys))} binding_keys={len(set(bkeys))}")

    by_key = {key(r): r for r in binding}
    targets = [norm_target(first_nonempty(by_key[k], TARGET_ALIASES)) for k in ckeys if k in by_key]
    statuses = [first_nonempty(by_key[k], STATUS_ALIASES) for k in ckeys if k in by_key]
    decisions = [first_nonempty(by_key[k], BINDING_ALIASES) for k in ckeys if k in by_key]

    empty_targets = sum(not x for x in targets)
    invalid_targets = [x for x in targets if not under_evidence(x)]
    empty_status = sum(not x for x in statuses)
    empty_decisions = sum(not x for x in decisions)

    chk("TARGETS_NONEMPTY", empty_targets == 0, f"empty={empty_targets}")
    chk("TARGETS_04_EVIDENCE", not invalid_targets,
        "all target values resolve under vault/04_Evidence"
        if not invalid_targets else f"invalid={invalid_targets[:5]}")
    chk("TARGET_STATUS_PRESENT", empty_status == 0,
        f"empty={empty_status}; native binding vocabulary accepted")
    chk("TARGET_BINDING_PRESENT", empty_decisions == 0, f"empty={empty_decisions}")

    ok = all(x[1] for x in checks)
    auth = "GRANTED" if ok else "NOT_GRANTED"
    execution = "AUTHORIZED_FOR_CONTROLLED_EXECUTION" if ok else "BLOCKED"

    rows = []
    for r in contract:
        b = by_key.get(key(r), {})
        target = norm_target(first_nonempty(b, TARGET_ALIASES))
        rr = dict(r)
        rr.update({
            "Target_Relative": target,
            "Target_Binding": first_nonempty(b, BINDING_ALIASES),
            "Target_Status": first_nonempty(b, STATUS_ALIASES),
            "Authorization_Decision": auth,
            "Authorization_Scope": "EXACT_31_CONTRACT_IDENTITIES",
            "Contract_Status": "CONTRACT_DEFINED",
            "Execution_Status": execution,
            "Metric_Persistence_Authorization": auth,
            "KnowledgeBridge_Write_Authorization": auth,
            "Vault_Write_Authorization": auth,
        })
        rows.append(rr)

    fields = list(dict.fromkeys(
        list(contract[0].keys() if contract else []) +
        ["Target_Relative","Target_Binding","Target_Status",
         "Authorization_Decision","Authorization_Scope","Contract_Status",
         "Execution_Status","Metric_Persistence_Authorization",
         "KnowledgeBridge_Write_Authorization","Vault_Write_Authorization"]
    ))

    REPORTS.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    manifest = {
        "stage": "D-OBSIDIAN-06.31",
        "version": "R2.1_FIXED",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "contract_source": str(CONTRACT.relative_to(REPO)),
        "binding_source": str(binding_path.relative_to(REPO)),
        "binding_target_field_selected": target_field,
        "binding_status_field_selected": status_field,
        "binding_decision_field_selected": binding_field,
        "rows": len(rows),
        "authorization_status": auth,
        "execution_status": execution,
        "vault_write_performed": False,
        "checks": [{"name": n, "pass": p, "detail": d} for n,p,d in checks],
    }
    OUT_JSON.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    md = [
        "# D-OBSIDIAN-06.31 — 0695.7 Explicit Persistence Authorization R2.1 FIXED",
        "",
        "Schema-selection correction: the gate no longer blindly selects an older binding artifact.",
        "",
        f"- Binding source selected: `{binding_path.relative_to(REPO)}`",
        f"- Target field selected: `{target_field}`",
        f"- Status field selected: `{status_field}`",
        f"- Binding decision field selected: `{binding_field}`",
        f"- Rows: **{len(rows)}**",
        f"- Authorization: **{auth}**",
        f"- Execution status: **{execution}**",
        "",
        "## Safety",
        "- The selected binding artifact must contain exactly 31 rows and a target field.",
        "- Target must be nonempty and under `vault/04_Evidence`.",
        "- Identity and scope must match the execution contract exactly.",
        "- This script never writes the Vault.",
        "- Authorization remains fail-closed on any failed gate.",
        "",
        "## Checks",
        "",
    ]
    md += [f"- [{'PASS' if p else 'FAIL'}] {n}: {d}" for n,p,d in checks]
    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    print(f"Binding source selected: {binding_path}")
    print(f"Target field selected  : {target_field}")
    print(f"AUTHORIZATION: {auth}")
    print(f"D-OBSIDIAN-06.31 R2.1: {execution}")
    print(f"CSV: {OUT_CSV}")
    print(f"MD : {OUT_MD}")
    print(f"JSON: {OUT_JSON}")
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
