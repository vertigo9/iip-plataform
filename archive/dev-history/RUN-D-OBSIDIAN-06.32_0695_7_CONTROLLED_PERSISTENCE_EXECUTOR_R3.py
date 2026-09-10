from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent
REPORTS = REPO / "reports"
SRC = REPO / "src"
VAULT = REPO / "vault"

AUTH_CSV = REPORTS / "PCIP11_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION_R2_1.csv"
CONTRACT_CSV = REPORTS / "PCIP11_0695_7_EXECUTION_CONTRACT_R1.csv"
OUTPUT_CSV = REPORTS / "PCIP11_0695_7_CONTROLLED_PERSISTENCE_EXECUTION_R1.csv"
OUTPUT_MD = REPORTS / "PCIP11_0695_7_CONTROLLED_PERSISTENCE_EXECUTION_R1.md"
OUTPUT_JSON = REPORTS / "PCIP11_0695_7_CONTROLLED_PERSISTENCE_EXECUTION_R1.json"

KEY = ["Row", "SHA256", "Metric"]

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def load(path: Path):
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def pick(row, *names):
    for n in names:
        v = row.get(n)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""

def key(row):
    return tuple(pick(row, x) for x in KEY)

def norm(v):
    return str(v or "").strip().replace("\\", "/").lstrip("./")

def target_path(rel):
    p = norm(rel)
    if not p.lower().startswith("vault/04_evidence/"):
        raise ValueError(f"target outside vault/04_Evidence: {rel!r}")
    return REPO / Path(*p.split("/"))

def validate_authorization(auth, contract):
    errors = []
    if len(auth) != 31:
        errors.append(f"authorization_rows={len(auth)}")
    if len(contract) != 31:
        errors.append(f"contract_rows={len(contract)}")

    akeys = [key(x) for x in auth]
    ckeys = [key(x) for x in contract]
    if len(set(akeys)) != len(akeys):
        errors.append("authorization_duplicate_identity")
    if len(set(ckeys)) != len(ckeys):
        errors.append("contract_duplicate_identity")
    if set(akeys) != set(ckeys):
        errors.append("authorization_contract_scope_mismatch")

    for i, row in enumerate(auth, 1):
        if pick(row, "Authorization_Decision") != "GRANTED":
            errors.append(f"row_{i}:authorization_not_granted")
        if pick(row, "Metric_Persistence_Authorization") != "GRANTED":
            errors.append(f"row_{i}:metric_persistence_not_granted")
        if pick(row, "KnowledgeBridge_Write_Authorization") != "GRANTED":
            errors.append(f"row_{i}:knowledgebridge_not_granted")
        if pick(row, "Vault_Write_Authorization") != "GRANTED":
            errors.append(f"row_{i}:vault_write_not_granted")
        t = norm(pick(row, "Target_Relative"))
        if not t:
            errors.append(f"row_{i}:empty_target")
        elif not t.lower().startswith("vault/04_evidence/"):
            errors.append(f"row_{i}:target_outside_04_evidence")
        if not pick(row, "Target_Binding"):
            errors.append(f"row_{i}:empty_target_binding")
        if not pick(row, "Target_Status"):
            errors.append(f"row_{i}:empty_target_status")
    return errors

def expected_tokens(row):
    # Conservative identity/content markers used only for pre-existing-file
    # idempotency classification. A file must contain all available markers.
    vals = [
        pick(row, "Knowledge_Evidence_ID"),
        pick(row, "Metric_ID"),
        pick(row, "Metric"),
        pick(row, "Value"),
        pick(row, "Resolved_Unit"),
        pick(row, "Resolved_Period"),
    ]
    return [v for v in vals if v]

def classify_existing(path: Path, row):
    if not path.exists():
        return "MISSING", ""
    if not path.is_file():
        return "CONFLICT", "target exists but is not a regular file"
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return "CONFLICT", f"cannot read target: {type(exc).__name__}:{exc}"
    missing = [t for t in expected_tokens(row) if t not in text]
    if not missing:
        return "IDENTICAL", ""
    return "CONFLICT", "missing identity/content markers: " + ",".join(missing[:6])

def build_evidence(row):
    from iip.intelligence.metric_identity import MetricObservationIdentity
    from iip.intelligence.metric_persistence import (
        build_knowledge_evidence,
        knowledge_evidence_id,
        metric_evidence_id,
    )
    from iip.knowledge.models import Evidence

    ticker = pick(row, "Derived_Canonical_Ticker", "Canonical_Ticker", "Ticker")
    if not ticker:
        authorized_metric_id = pick(row, "Metric_ID")
        m = re.match(r"^metric:([^:]+):", authorized_metric_id)
        if m:
            ticker = m.group(1)
    metric = pick(row, "Metric", "Metric_Name")
    value = pick(row, "Resolved_Value", "Value")
    unit = pick(row, "Resolved_Unit", "Unit", "Original_Unit")
    scale = pick(row, "Resolved_Scale", "Scale")
    period = pick(row, "Resolved_Period", "Period")
    dimension = pick(row, "Semantic_Dimension", "Resolved_Semantic_Dimension", "Dimension")
    document_hash = pick(row, "Document_Hash", "SHA256", "Evidence_SHA256", "SHA")
    document_id = pick(row, "Document_ID", "Knowledge_Document_ID", "DocumentId")
    source_locator = pick(row, "Source_Locator", "SourceLocator", "Locator", "Resolution_Selected_Context")
    lineage = pick(row, "Lineage", "Resolved_Lineage")
    original_ticker = pick(row, "Original_Ticker", "Original_Identity") or ticker

    missing = [
        name for name, value_ in (
            ("ticker", ticker), ("metric", metric), ("value", value),
            ("period", period), ("document_hash", document_hash),
        ) if not value_
    ]
    if missing:
        raise ValueError(f"missing required identity fields: {', '.join(missing)}")

    identity = MetricObservationIdentity(
        canonical_ticker=ticker,
        original_ticker=original_ticker,
        metric_name=metric,
        value=value,
        unit=unit or None,
        scale=scale or None,
        period=period,
        semantic_dimension=dimension or None,
        document_hash=document_hash,
        document_id=document_id or None,
        source_locator=source_locator or None,
        lineage=lineage or None,
    )
    metric_id = metric_evidence_id(identity)
    knowledge_id = knowledge_evidence_id(metric_id)

    if pick(row, "Metric_ID") != metric_id:
        raise ValueError(f"Metric_ID mismatch for row {pick(row,'Row')}")
    if pick(row, "Knowledge_Evidence_ID") != knowledge_id:
        raise ValueError(f"Knowledge_Evidence_ID mismatch for row {pick(row,'Row')}")

    km = build_knowledge_evidence(
        identity,
        title=pick(row, "Title", "Source_FileName", "FileName") or
              f"{identity.canonical_ticker} {identity.period} historical metric evidence",
        source_type="historical_metric",
        source_url=None,
        relevant_facts={
            "metric_id": metric_id,
            "canonical_observation_id": pick(row, "Canonical_Observation_ID"),
            "resolution_status": pick(row, "Resolution_Status"),
            "resolution_type": pick(row, "Resolution_Type"),
            "resolution_selected_context": pick(row, "Resolution_Selected_Context"),
        },
    )
    return Evidence(
        evidence_id=km.evidence_id,
        ticker=km.ticker,
        date=km.date,
        source_type=km.source_type,
        source_url=km.source_url,
        title=km.title,
        document_hash=km.document_hash,
        relevant_facts=(
            f"metric_id: {metric_id}",
            f"metric: {identity.metric_name}",
            f"value: {identity.value}",
            f"unit: {identity.unit or ''}",
            f"scale: {identity.scale or ''}",
            f"period: {identity.period}",
            f"document_id: {identity.document_id or ''}",
            f"document_hash: {identity.document_hash}",
            f"lineage: {identity.lineage or ''}",
        ),
    )

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true",
                    help="perform real persistence; without this flag the run is read-only")
    args = ap.parse_args()

    print("=" * 96)
    print("D-OBSIDIAN-06.32 — 0695.7 CONTROLLED PERSISTENCE EXECUTOR R5")
    print("=" * 96)
    print("Mode:", "EXECUTE" if args.execute else "DRY-RUN")

    errors = []
    try:
        auth = load(AUTH_CSV)
        contract = load(CONTRACT_CSV)
    except Exception as exc:
        print(f"[FAIL] LOAD_ARTIFACTS: {type(exc).__name__}:{exc}")
        return 2

    errors.extend(validate_authorization(auth, contract))
    if errors:
        for e in errors:
            print("[FAIL]", e)
        print("EXECUTION: BLOCKED")
        print("Vault changed: NO")
        return 3

    by_key = {key(r): r for r in auth}
    pre = []
    for row in contract:
        a = by_key[key(row)]
        p = target_path(pick(a, "Target_Relative"))
        state, detail = classify_existing(p, row)
        pre.append((row, a, p, state, detail))

    conflicts = [x for x in pre if x[3] == "CONFLICT"]
    missing = [x for x in pre if x[3] == "MISSING"]
    identical = [x for x in pre if x[3] == "IDENTICAL"]

    print(f"[PASS] AUTHORIZATION_31_ROWS: {len(auth)}")
    print(f"[PASS] CONTRACT_31_ROWS: {len(contract)}")
    print(f"[PASS] SCOPE_EXACT_MATCH: {len(pre)}")
    print(f"Existing identical targets: {len(identical)}")
    print(f"New targets: {len(missing)}")
    print(f"Conflicting targets: {len(conflicts)}")

    results = []
    if conflicts:
        for row, a, p, state, detail in conflicts:
            results.append({
                "Row": pick(row, "Row"),
                "Metric_ID": pick(row, "Metric_ID"),
                "Knowledge_Evidence_ID": pick(row, "Knowledge_Evidence_ID"),
                "Target_Relative": pick(a, "Target_Relative"),
                "Result": "BLOCK_CONFLICT",
                "Detail": detail,
            })
        print("[STOP] conflicting pre-existing targets detected; no writes attempted")
        final = "BLOCKED_CONFLICT"
    elif not args.execute:
        for row, a, p, state, detail in pre:
            results.append({
                "Row": pick(row, "Row"),
                "Metric_ID": pick(row, "Metric_ID"),
                "Knowledge_Evidence_ID": pick(row, "Knowledge_Evidence_ID"),
                "Target_Relative": pick(a, "Target_Relative"),
                "Result": "NO_OP_IDENTICAL" if state == "IDENTICAL" else "READY_TO_CREATE",
                "Detail": detail,
            })
        final = "DRY_RUN_PASS"
        print("[PASS] DRY_RUN: no Vault writes performed")
    else:
        if str(SRC) not in sys.path:
            sys.path.insert(0, str(SRC))
        from iip.knowledge.bridge import KnowledgeBridge

        # Prepare every new evidence object before the first write.
        prepared = []
        try:
            for row, a, p, state, detail in pre:
                if state == "IDENTICAL":
                    prepared.append((row, a, p, state, None))
                else:
                    # Identity authority is the authorized artifact. The execution
                    # contract is the scope carrier and may omit identity fields
                    # that are already present in the authorization manifest.
                    identity_row = dict(a)
                    identity_row.update(
                        {k: v for k, v in row.items() if str(v or "").strip()}
                    )
                    # Fail closed: if the contract omitted Metric_ID, retain the
                    # authorized Metric_ID from `a` rather than inventing identity.
                    if not str(row.get("Metric_ID") or "").strip():
                        identity_row["Metric_ID"] = pick(a, "Metric_ID")
                    if not str(row.get("Knowledge_Evidence_ID") or "").strip():
                        identity_row["Knowledge_Evidence_ID"] = pick(
                            a, "Knowledge_Evidence_ID"
                        )
                    prepared.append(
                        (row, a, p, state, build_evidence(identity_row))
                    )
        except Exception as exc:
            print(f"[STOP] preparation failure: {type(exc).__name__}:{exc}")
            print("Vault changed: NO")
            return 4

        bridge = KnowledgeBridge(str(VAULT))
        stop = False
        for row, a, expected, state, evidence in prepared:
            if stop:
                results.append({
                    "Row": pick(row, "Row"),
                    "Metric_ID": pick(row, "Metric_ID"),
                    "Knowledge_Evidence_ID": pick(row, "Knowledge_Evidence_ID"),
                    "Target_Relative": pick(a, "Target_Relative"),
                    "Result": "NOT_ATTEMPTED_AFTER_FAILURE",
                    "Detail": "",
                })
                continue
            if state == "IDENTICAL":
                results.append({
                    "Row": pick(row, "Row"),
                    "Metric_ID": pick(row, "Metric_ID"),
                    "Knowledge_Evidence_ID": pick(row, "Knowledge_Evidence_ID"),
                    "Target_Relative": pick(a, "Target_Relative"),
                    "Result": "NO_OP_IDENTICAL",
                    "Detail": "",
                })
                continue
            try:
                saved = Path(bridge.persist_evidence(evidence))
                saved_abs = saved.resolve()
                expected_abs = expected.resolve()
                if saved_abs != expected_abs:
                    stop = True
                    results.append({
                        "Row": pick(row, "Row"),
                        "Metric_ID": pick(row, "Metric_ID"),
                        "Knowledge_Evidence_ID": pick(row, "Knowledge_Evidence_ID"),
                        "Target_Relative": pick(a, "Target_Relative"),
                        "Result": "BLOCK_TARGET_MISMATCH",
                        "Detail": f"saved={saved_abs} expected={expected_abs}",
                    })
                    print("[STOP] executor returned a target different from the authorized Target_Relative")
                    continue
                if not saved.exists() or saved.stat().st_size == 0:
                    stop = True
                    results.append({
                        "Row": pick(row, "Row"),
                        "Metric_ID": pick(row, "Metric_ID"),
                        "Knowledge_Evidence_ID": pick(row, "Knowledge_Evidence_ID"),
                        "Target_Relative": pick(a, "Target_Relative"),
                        "Result": "FAILED_EMPTY_TARGET",
                        "Detail": "",
                    })
                    continue
                results.append({
                    "Row": pick(row, "Row"),
                    "Metric_ID": pick(row, "Metric_ID"),
                    "Knowledge_Evidence_ID": pick(row, "Knowledge_Evidence_ID"),
                    "Target_Relative": pick(a, "Target_Relative"),
                    "Result": "CREATED",
                    "Detail": str(saved_abs),
                })
            except Exception as exc:
                stop = True
                results.append({
                    "Row": pick(row, "Row"),
                    "Metric_ID": pick(row, "Metric_ID"),
                    "Knowledge_Evidence_ID": pick(row, "Knowledge_Evidence_ID"),
                    "Target_Relative": pick(a, "Target_Relative"),
                    "Result": f"FAILED_{type(exc).__name__}",
                    "Detail": str(exc),
                })

        created = sum(r["Result"] == "CREATED" for r in results)
        failed = sum(r["Result"].startswith("FAILED") or r["Result"].startswith("BLOCK_") for r in results)
        final = "EXECUTION_PASS" if created == len(missing) and failed == 0 else "PARTIAL_OR_FAILED"
        print(f"Created: {created}")
        print(f"Failed/blocked: {failed}")

    fieldnames = ["Row","Metric_ID","Knowledge_Evidence_ID","Target_Relative","Result","Detail"]
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(results)

    report = {
        "stage": "D-OBSIDIAN-06.32",
        "version": "R1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "EXECUTE" if args.execute else "DRY_RUN",
        "authorization_sha256": sha256_file(AUTH_CSV),
        "contract_sha256": sha256_file(CONTRACT_CSV),
        "rows": len(contract),
        "identical_targets": len(identical),
        "new_targets": len(missing),
        "conflicts": len(conflicts),
        "final_status": final,
        "vault_changed": bool(args.execute and final in {"EXECUTION_PASS", "PARTIAL_OR_FAILED"}),
        "rollback": "NOT_PERFORMED",
    }
    OUTPUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    OUTPUT_MD.write_text(
        "# D-OBSIDIAN-06.32 — Controlled Persistence Execution R1\n\n" +
        f"- Mode: **{report['mode']}**\n" +
        f"- Authorization SHA-256: `{report['authorization_sha256']}`\n" +
        f"- Contract SHA-256: `{report['contract_sha256']}`\n" +
        f"- Rows: **{report['rows']}**\n" +
        f"- Identical targets: **{report['identical_targets']}**\n" +
        f"- New targets: **{report['new_targets']}**\n" +
        f"- Conflicts: **{report['conflicts']}**\n" +
        f"- Final status: **{report['final_status']}**\n" +
        f"- Vault changed: **{'YES' if report['vault_changed'] else 'NO'}**\n\n" +
        "The executor consumes the explicit 06.31 authorization artifact. " +
        "It does not overwrite conflicting files. A target mismatch returned by the bridge stops further writes.\n",
        encoding="utf-8",
    )
    print(f"FINAL STATUS: {final}")
    print(f"CSV: {OUTPUT_CSV}")
    print(f"MD : {OUTPUT_MD}")
    print(f"JSON: {OUTPUT_JSON}")
    return 0 if final in {"DRY_RUN_PASS", "EXECUTION_PASS"} else 1

if __name__ == "__main__":
    raise SystemExit(main())
