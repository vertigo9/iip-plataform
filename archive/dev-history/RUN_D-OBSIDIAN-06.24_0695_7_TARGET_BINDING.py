from __future__ import annotations
import csv, hashlib, json, sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
INPUT = REPORTS / "PCIP11_0695_7_EXPLICIT_EXECUTION_AUTHORIZATION_R1.csv"
OUTPUT = REPORTS / "PCIP11_0695_7_TARGET_BINDING_R2"

OFFICIAL_VAULT = ROOT / "vault"
TARGET_DIR = OFFICIAL_VAULT / "04_Evidence"

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest().upper()

def rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def v(row: dict[str, str], key: str) -> str:
    return str(row.get(key, "") or "").strip()

def build_ids(row: dict[str, str]):
    # Use the official IIP identity functions; do not invent persistence IDs.
    sys.path.insert(0, str(ROOT / "src"))
    from iip.intelligence.metric_identity import MetricObservationIdentity
    from iip.intelligence.metric_persistence import (
        metric_evidence_id,
        knowledge_evidence_id,
    )

    identity = MetricObservationIdentity(
        canonical_ticker=v(row, "Ticker") or "PCIP11",
        original_ticker=v(row, "Original_Ticker") or v(row, "Ticker") or "PCIP11",
        metric_name=v(row, "Metric"),
        value=v(row, "Value"),
        unit=v(row, "Resolved_Unit") or v(row, "Original_Unit") or None,
        scale=v(row, "Scale") or None,
        period=v(row, "Resolved_Period") or v(row, "Period"),
        semantic_dimension=v(row, "Semantic_Dimension") or None,
        document_hash=v(row, "SHA256"),
        document_id=v(row, "Document_ID") or None,
        source_locator=v(row, "Source_Locator") or None,
        lineage=v(row, "Lineage") or None,
    )

    metric_id = metric_evidence_id(identity)
    knowledge_id = knowledge_evidence_id(metric_id)
    suffix = knowledge_id.split(":")[-1]
    target = TARGET_DIR / f"evidence_metric_{suffix}.md"
    return metric_id, knowledge_id, target

def main() -> int:
    print("=" * 100)
    print("D-OBSIDIAN-06.24 — 0695.7 TARGET BINDING R2")
    print("=" * 100)

    if not INPUT.exists():
        print("[BLOCKED] input missing:", INPUT)
        return 2

    source_rows = rows(INPUT)
    print("Input rows:", len(source_rows))

    errors: list[str] = []

    vault_ok = OFFICIAL_VAULT.exists() and OFFICIAL_VAULT.is_dir()
    target_ok = TARGET_DIR.exists() and TARGET_DIR.is_dir()

    if not vault_ok:
        errors.append(f"official vault not found: {OFFICIAL_VAULT}")
    if not target_ok:
        errors.append(f"target directory not found: {TARGET_DIR}")

    output_rows = []

    for row in source_rows:
        result = dict(row)
        try:
            metric_id, knowledge_id, target = build_ids(row)
            result["Metric_ID"] = metric_id
            result["Knowledge_Evidence_ID"] = knowledge_id
            result["Target_Binding"] = str(target)
            result["Target_Relative"] = f"vault/04_Evidence/{target.name}"
            result["Target_Status"] = "TARGET_EXPLICITLY_BOUND"
        except Exception as exc:
            errors.append(
                f"row {v(row, 'Row')}: {type(exc).__name__}: {exc}"
            )
            result["Target_Binding"] = ""
            result["Target_Relative"] = ""
            result["Target_Status"] = "TARGET_BINDING_ERROR"
        output_rows.append(result)

    unique_scope = len({
        (v(row, "Row"), v(row, "SHA256").upper(), v(row, "Metric"))
        for row in source_rows
    }) == 31

    all_bound = (
        len(source_rows) == 31
        and all(
            v(row, "Target_Status") == "TARGET_EXPLICITLY_BOUND"
            for row in output_rows
        )
    )

    status = (
        "PASS"
        if vault_ok and target_ok and unique_scope and all_bound and not errors
        else "BLOCKED"
    )
    decision = (
        "TARGET_EXPLICITLY_BOUND"
        if status == "PASS"
        else "TARGET_BINDING_REQUIRED"
    )

    fields = list(dict.fromkeys(
        key for row in output_rows for key in row
    ))

    with OUTPUT.with_suffix(".csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)

    manifest = {
        "stage": "06.24",
        "revision": "R2",
        "status": status,
        "decision": decision,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "input_sha256": sha256(INPUT),
        "input_rows": len(source_rows),
        "official_vault": str(OFFICIAL_VAULT),
        "target_directory": str(TARGET_DIR),
        "target_rule": (
            "vault/04_Evidence/"
            "evidence_metric_<Knowledge_Evidence_ID suffix>.md"
        ),
        "scope_identity": "Row + SHA256 + Metric",
        "errors": errors,
        "vault_modified": False,
        "persistence_executed": False,
    }

    OUTPUT.with_suffix(".json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    OUTPUT.with_suffix(".md").write_text(
        "\n".join([
            "# D-OBSIDIAN-06.24 — Target Binding R2",
            "",
            f"- Status: **{status}**",
            f"- Decision: **{decision}**",
            f"- Rows: **{len(source_rows)}**",
            f"- Official Vault: `{OFFICIAL_VAULT}`",
            f"- Target: `{TARGET_DIR}`",
            "- Vault modified: **NO**",
            "- Persistence executed: **NO**",
            "",
            "Target binding is derived from the established "
            "Metric_ID/Knowledge_Evidence_ID identity functions; "
            "no target is guessed.",
        ]) + "\n",
        encoding="utf-8",
    )

    print(f"[{'PASS' if status == 'PASS' else 'BLOCKED'}] {decision}")
    print("Target directory:", TARGET_DIR)
    print("Vault modified: NO")
    print(f"D-OBSIDIAN-06.24: {status}")
    return 0 if status == "PASS" else 3

if __name__ == "__main__":
    raise SystemExit(main())
