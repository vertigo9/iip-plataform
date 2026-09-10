from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPORTS = Path("reports")
AUTH = REPORTS / "PCIP11_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION_R2_1.csv"
GENERIC = REPORTS / "0695_GENERIC_METRIC_PERSISTENCE_DRY_RUN_R1.csv"
AUDIT = REPORTS / "0695_GENERIC_METRIC_PERSISTENCE_GRANULARITY_AUDIT_R1.csv"

OUT_CSV = REPORTS / "PCIP11_0695_7_SCOPE_DEDUP_AUTH_RECONCILIATION_R1.csv"
OUT_MD = REPORTS / "PCIP11_0695_7_SCOPE_DEDUP_AUTH_RECONCILIATION_R1.md"
OUT_JSON = REPORTS / "PCIP11_0695_7_SCOPE_DEDUP_AUTH_RECONCILIATION_R1.json"

REQUIRED_AUTH = {"Row","SHA256","Metric","Target_Relative","Target_Binding","Target_Status"}
REQUIRED_GENERIC = {
    "Row","SHA256","FileName","Original_Identity","Original_Ticker",
    "Canonical_Ticker","Lineage","Metric","Value_Raw","Value_Parsed",
    "Original_Unit","Resolved_Unit","Scale","Resolved_Period",
    "Document_ID","Metric_Evidence_ID","Knowledge_Evidence_ID",
    "Validation_Status","Validation_Reason"
}

def clean(v):
    return (v or "").strip()

def load_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def key_auth(r):
    return (clean(r["Row"]), clean(r["SHA256"]), clean(r["Metric"]))

def canonical_key(r):
    return (
        clean(r.get("SHA256")),
        clean(r.get("Metric")),
        clean(r.get("Resolved_Period")),
        clean(r.get("Canonical_Ticker")),
        clean(r.get("Value_Parsed")),
        clean(r.get("Resolved_Unit")),
        clean(r.get("Scale")),
    )

def identity_key(r):
    return (clean(r.get("Metric_Evidence_ID")), clean(r.get("Knowledge_Evidence_ID")))

def main():
    print("D-OBSIDIAN-06.31.2 — 0695.7 SCOPE DEDUP & AUTH RECONCILIATION R1")
    print("=" * 100)
    for p in (AUTH, GENERIC, AUDIT):
        if not p.exists():
            raise FileNotFoundError(str(p))

    auth = load_csv(AUTH)
    generic = load_csv(GENERIC)
    audit = load_csv(AUDIT)

    missing_auth = REQUIRED_AUTH - set(auth[0])
    missing_generic = REQUIRED_GENERIC - set(generic[0])
    if missing_auth or missing_generic:
        raise ValueError(f"schema failure: auth={sorted(missing_auth)} generic={sorted(missing_generic)}")

    # Authorization scope is preserved exactly; this gate never deletes source rows.
    auth_map = defaultdict(list)
    for r in auth:
        auth_map[key_auth(r)].append(r)

    generic_map = defaultdict(list)
    for r in generic:
        generic_map[key_auth(r)].append(r)

    audit_map = defaultdict(list)
    for r in audit:
        k = (clean(r.get("SHA256")), clean(r.get("Metric")), clean(r.get("Resolved_Period")))
        audit_map[k].append(r)

    classifications = []
    canonical_groups = defaultdict(list)

    for r in generic:
        if clean(r.get("Validation_Status")).upper() != "READY":
            continue
        ck = canonical_key(r)
        canonical_groups[ck].append(r)

    # A canonical persistence identity is selected once per full canonical observation.
    # Exact duplicates are represented as aliases, not additional writes.
    selected = {}
    for ck, rows in canonical_groups.items():
        rows_sorted = sorted(rows, key=lambda x: int(clean(x.get("Row")) or "0"))
        selected[ck] = rows_sorted[0]

    auth_seen_canonical = defaultdict(list)
    for ar in auth:
        matches = generic_map.get(key_auth(ar), [])
        if not matches:
            classifications.append((ar, "BLOCKED_NO_GENERIC_MATCH", "", ""))
            continue

        ready = [x for x in matches if clean(x.get("Validation_Status")).upper() == "READY"]
        if not ready:
            classifications.append((ar, "BLOCKED_GENERIC_NOT_READY", "", ""))
            continue

        # Multiple generic rows can be the same semantic observation.
        ck = canonical_key(ready[0])
        can = selected[ck]
        mid = clean(can.get("Metric_Evidence_ID"))
        kid = clean(can.get("Knowledge_Evidence_ID"))
        auth_seen_canonical[ck].append(ar)

        if len(ready) > 1:
            same_identity = len({identity_key(x) for x in ready}) == 1
            cls = "EXACT_DUPLICATE_ALIAS" if same_identity else "BLOCKED_SEMANTIC_CONFLICT"
        else:
            cls = "CANONICAL_PERSISTENCE_SCOPE"

        classifications.append((ar, cls, mid, kid))

    # Verify canonical identities are unique before producing a recommendation.
    canonical_ids = [(k, v) for k, v in selected.items()]
    mids = [clean(v.get("Metric_Evidence_ID")) for _, v in canonical_ids]
    kids = [clean(v.get("Knowledge_Evidence_ID")) for _, v in canonical_ids]
    unique_mid = len(mids) == len(set(mids))
    unique_kid = len(kids) == len(set(kids))

    # Expected current architecture: 31 authorized observations -> 28 canonical persistence identities.
    canonical_count = len(canonical_ids)
    exact_aliases = sum(1 for _, cls, _, _ in classifications if cls == "EXACT_DUPLICATE_ALIAS")
    blocked = sum(1 for _, cls, _, _ in classifications if cls.startswith("BLOCKED_"))
    canonical_auth = sum(1 for _, cls, _, _ in classifications if cls == "CANONICAL_PERSISTENCE_SCOPE")

    status = (
        "READY_FOR_AUTHORIZATION_RECONCILIATION_REVIEW"
        if canonical_count == 28 and unique_mid and unique_kid and blocked == 0
        else "BLOCKED_REQUIRES_SEMANTIC_REVIEW"
    )

    out_rows = []
    for ar, cls, mid, kid in classifications:
        out_rows.append({
            "Authorization_Row": clean(ar.get("Row")),
            "SHA256": clean(ar.get("SHA256")),
            "Metric": clean(ar.get("Metric")),
            "Target_Relative": clean(ar.get("Target_Relative")),
            "Target_Binding": clean(ar.get("Target_Binding")),
            "Target_Status": clean(ar.get("Target_Status")),
            "Classification": cls,
            "Canonical_Metric_ID": mid,
            "Canonical_Knowledge_Evidence_ID": kid,
            "Write_Action": "NO_WRITE",
        })

    REPORTS.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0]))
        w.writeheader()
        w.writerows(out_rows)

    md = [
        "# D-OBSIDIAN-06.31.2 — Scope Dedup & Authorization Reconciliation R1",
        "",
        "READ-ONLY / FAIL-CLOSED / NO AUTHORIZATION GRANT / NO VAULT WRITE",
        "",
        f"- Authorization rows: **{len(auth)}**",
        f"- Generic rows: **{len(generic)}**",
        f"- Canonical READY persistence identities: **{canonical_count}**",
        f"- Canonical authorization rows: **{canonical_auth}**",
        f"- Exact duplicate aliases: **{exact_aliases}**",
        f"- Blocked rows: **{blocked}**",
        f"- Unique Metric IDs: **{unique_mid}**",
        f"- Unique Knowledge IDs: **{unique_kid}**",
        f"- Final status: **{status}**",
        "",
        "## Safety boundary",
        "- The 31-row authorization artifact remains the source scope and is not modified.",
        "- Exact duplicates are classified as aliases only; they are never silently collapsed in the source.",
        "- No Metric persistence, KnowledgeBridge execution, Vault write, overwrite, delete, rename, or move is performed.",
        "- This artifact does not grant authorization.",
    ]
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

    import json
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "authorization_rows": len(auth),
        "generic_rows": len(generic),
        "canonical_ready_persistence_identities": canonical_count,
        "canonical_authorization_rows": canonical_auth,
        "exact_duplicate_aliases": exact_aliases,
        "blocked_rows": blocked,
        "unique_metric_ids": unique_mid,
        "unique_knowledge_ids": unique_kid,
        "authorization_granted": False,
        "vault_changed": False,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[PASS] AUTHORIZATION_ROWS: {len(auth)}")
    print(f"[PASS] GENERIC_ROWS: {len(generic)}")
    print(f"CANONICAL READY persistence identities: {canonical_count}")
    print(f"CANONICAL authorization rows        : {canonical_auth}")
    print(f"EXACT duplicate aliases             : {exact_aliases}")
    print(f"BLOCKED rows                        : {blocked}")
    print(f"Unique Metric IDs                   : {unique_mid}")
    print(f"Unique Knowledge IDs                : {unique_kid}")
    print(f"AUTHORIZATION: NOT GRANTED")
    print(f"VAULT CHANGED: NO")
    print(f"FINAL STATUS: {status}")
    print(f"CSV: {OUT_CSV}")
    print(f"MD : {OUT_MD}")
    print(f"JSON: {OUT_JSON}")

if __name__ == "__main__":
    main()
