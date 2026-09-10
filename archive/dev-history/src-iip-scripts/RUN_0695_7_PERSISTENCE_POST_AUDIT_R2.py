from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "reports"
VAULT = ROOT / "vault"

EXECUTION_CSV = REPORTS / "PCIP11_0695_7_PERSISTENCE_EXECUTION_R1.csv"
GATE_CSV = REPORTS / "PCIP11_0695_7_PERSISTENCE_EXECUTION_GATE_R1.csv"
CONTRACT_CSV = REPORTS / "PCIP11_0695_7_PERSISTENCE_CONTRACT_R4.csv"

OUTPUT_CSV = REPORTS / "PCIP11_0695_7_PERSISTENCE_POST_AUDIT_R2.csv"
OUTPUT_MD = REPORTS / "PCIP11_0695_7_PERSISTENCE_POST_AUDIT_R2.md"

SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from iip.knowledge.repository import ObsidianRepository


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def field(row: dict[str, str], name: str) -> str:
    return str(row.get(name, "") or "").strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    errors: list[str] = []

    for path in (EXECUTION_CSV, GATE_CSV, CONTRACT_CSV):
        if not path.exists():
            errors.append(f"missing_artifact:{path.name}")

    if not VAULT.exists():
        errors.append(f"missing_vault:{VAULT}")

    if errors:
        print("=" * 90)
        print("0695.7 PERSISTENCE POST-AUDIT R2")
        print("=" * 90)
        print("Audit result                : FAIL")
        print("Audit mode                  : READ-ONLY")
        print("Vault modified by audit     : NO")
        for error in errors:
            print(f"  - {error}")
        return 1

    execution = load_csv(EXECUTION_CSV)
    gate = load_csv(GATE_CSV)
    contract = load_csv(CONTRACT_CSV)

    if len(execution) != 28:
        errors.append(f"execution_rows={len(execution)}")
    if len(gate) != 28:
        errors.append(f"gate_rows={len(gate)}")
    if len(contract) != 28:
        errors.append(f"contract_rows={len(contract)}")

    gate_pass = sum(field(row, "Gate_Status") == "PASS" for row in gate)
    if gate_pass != 28:
        errors.append(f"gate_pass_rows={gate_pass}")

    execution_created = sum(field(row, "Result") == "CREATED" for row in execution)
    execution_existing = sum(
        field(row, "Result") == "ALREADY_EXISTS" for row in execution
    )
    execution_failed = sum(
        field(row, "Result").startswith("FAILED") for row in execution
    )

    if execution_created != 28:
        errors.append(f"execution_created={execution_created}")
    if execution_existing != 0:
        errors.append(f"execution_already_exists={execution_existing}")
    if execution_failed != 0:
        errors.append(f"execution_failed={execution_failed}")

    evidence_dir = VAULT / "04_Evidence"
    if not evidence_dir.exists():
        errors.append(f"missing_evidence_directory:{evidence_dir}")

    repository = ObsidianRepository(VAULT)
    results: list[dict[str, str]] = []

    for idx, row in enumerate(execution, start=2):
        evidence_id = field(row, "Knowledge_Evidence_ID")
        ticker = field(row, "Ticker")
        metric_id = field(row, "Metric_ID")
        period = field(row, "Period")
        metric = field(row, "Metric")
        value = field(row, "Value")
        document_hash = field(row, "Document_Hash")
        saved_path_text = field(row, "Saved_Path")

        row_errors: list[str] = []

        if not evidence_id:
            row_errors.append("missing_knowledge_id")

        if not saved_path_text:
            row_errors.append("missing_saved_path")

        expected_path = Path(saved_path_text) if saved_path_text else Path()

        # Primary lookup: exact persisted path from the execution report.
        if saved_path_text and not expected_path.exists():
            row_errors.append("saved_path_missing")

        # Secondary lookup: repository filename convention based on the
        # semantic evidence_id, without requiring ticker in the filename.
        safe_name = repository._safe_filename(evidence_id) if evidence_id else ""
        convention_path = evidence_dir / f"{safe_name}.md" if safe_name else Path()

        if saved_path_text and expected_path.exists() and convention_path.exists():
            if expected_path.resolve() != convention_path.resolve():
                row_errors.append("saved_path_convention_mismatch")

        actual_path = (
            expected_path
            if saved_path_text and expected_path.exists()
            else convention_path
        )

        exists = actual_path.exists() if actual_path else False
        size = actual_path.stat().st_size if exists else 0
        content = actual_path.read_text(encoding="utf-8") if exists else ""
        content_hash = sha256_file(actual_path) if exists else ""

        checks = {
            "file_exists": exists,
            "file_nonempty": size > 0,
            "type_evidence": "type: evidence" in content,
            "evidence_id": f"evidence_id: {evidence_id}" in content,
            "ticker": f"ticker: {ticker}" in content,
            "document_hash": (f"document_hash: {document_hash}" in content),
            "metric_id_fact": f"- metric_id: {metric_id}" in content,
            "metric_fact": f"- metric: {metric}" in content,
            "value_fact": f"- value: {value}" in content,
            "period_fact": f"- period: {period}" in content,
            "semantic_dimension_fact": (
                f"- semantic_dimension: {field(row, 'Semantic_Dimension')}" in content
            ),
            "source_locator_fact": (
                f"- source_locator: {field(row, 'Source_Locator')}" in content
            ),
            "lineage_fact": (f"- lineage: {field(row, 'Lineage')}" in content),
            "canonical_observation_fact": (
                f"- canonical_observation_id: "
                f"{field(row, 'Canonical_Observation_ID')}" in content
            ),
            "resolution_status_fact": (
                f"- resolution_status: {field(row, 'Resolution_Status')}" in content
            ),
            "resolution_type_fact": (
                f"- resolution_type: {field(row, 'Resolution_Type')}" in content
            ),
            "resolution_context_fact": (
                f"- resolution_selected_context: "
                f"{field(row, 'Resolution_Selected_Context')}" in content
            ),
        }

        for check_name, passed in checks.items():
            if not passed:
                row_errors.append(check_name)

        status = "PASS" if not row_errors else "FAIL"
        if row_errors:
            errors.extend(f"row_{idx}:{item}" for item in row_errors)

        results.append(
            {
                "Source_Row": field(row, "Source_Row"),
                "Metric_ID": metric_id,
                "Knowledge_Evidence_ID": evidence_id,
                "Ticker": ticker,
                "Period": period,
                "Metric": metric,
                "Value": value,
                "Saved_Path": str(actual_path),
                "File_Exists": "YES" if exists else "NO",
                "File_Size": str(size),
                "File_SHA256": content_hash,
                "Audit_Status": status,
                "Failure_Details": ",".join(row_errors),
            }
        )

    unique_evidence_ids = {
        field(row, "Knowledge_Evidence_ID")
        for row in execution
        if field(row, "Knowledge_Evidence_ID")
    }
    duplicate_evidence_ids = len(execution) - len(unique_evidence_ids)

    expected_paths = {
        Path(row["Saved_Path"]).resolve()
        for row in execution
        if field(row, "Saved_Path")
    }
    existing_expected_paths = {path for path in expected_paths if path.exists()}

    passed_rows = sum(row["Audit_Status"] == "PASS" for row in results)
    failed_rows = len(results) - passed_rows

    audit_pass = (
        len(execution) == 28
        and len(gate) == 28
        and len(contract) == 28
        and gate_pass == 28
        and execution_created == 28
        and execution_existing == 0
        and execution_failed == 0
        and duplicate_evidence_ids == 0
        and len(existing_expected_paths) == 28
        and passed_rows == 28
        and failed_rows == 0
        and not errors
    )

    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        fieldnames = list(results[0].keys()) if results else []
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    lines = [
        "# PCIP11 — 0695.7 Persistence Post-Audit R2",
        "",
        "## Safety",
        "- Audit mode: READ-ONLY",
        "- Vault modified by audit: NO",
        "",
        "## Results",
        f"- Execution report rows: {len(execution)}",
        f"- Gate rows: {len(gate)}",
        f"- Contract rows: {len(contract)}",
        f"- Gate PASS rows: {gate_pass}",
        f"- Execution CREATED rows: {execution_created}",
        f"- Execution ALREADY_EXISTS rows: {execution_existing}",
        f"- Execution FAILED rows: {execution_failed}",
        f"- Unique Knowledge_Evidence_ID: {len(unique_evidence_ids)}",
        f"- Duplicate Knowledge_Evidence_ID: {duplicate_evidence_ids}",
        f"- Persisted files physically present: {len(existing_expected_paths)}",
        f"- Content-verified records: {passed_rows}",
        f"- Failed records: {failed_rows}",
        f"- Audit result: {'PASS' if audit_pass else 'FAIL'}",
        "",
        "## Audit correction",
        "- R1's ticker-based list_evidence check is intentionally not used.",
        "- Evidence files are verified by persisted Knowledge_Evidence_ID/path, "
        "matching the repository's save_evidence filename contract.",
        "",
        "## Failures",
    ]

    if errors:
        lines.extend(f"- {error}" for error in errors)
    else:
        lines.append("- none")

    lines += [
        "",
        "This audit is read-only and does not modify the Vault.",
    ]

    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print("=" * 90)
    print("0695.7 PERSISTENCE POST-AUDIT R2")
    print("=" * 90)
    print(f"Execution report rows       : {len(execution)}")
    print(f"Gate rows                   : {len(gate)}")
    print(f"Contract rows               : {len(contract)}")
    print(f"Gate PASS rows              : {gate_pass}")
    print(f"Execution CREATED rows      : {execution_created}")
    print(f"Execution ALREADY_EXISTS    : {execution_existing}")
    print(f"Execution FAILED rows       : {execution_failed}")
    print(f"Unique Knowledge IDs        : {len(unique_evidence_ids)}")
    print(f"Duplicate Knowledge IDs     : {duplicate_evidence_ids}")
    print(f"Persisted files present     : {len(existing_expected_paths)}")
    print(f"Content verified            : {passed_rows}")
    print(f"Failed records              : {failed_rows}")
    print(f"Audit result                : {'PASS' if audit_pass else 'FAIL'}")
    print("Audit mode                  : READ-ONLY")
    print("Vault modified by audit     : NO")
    print(f"CSV                         : {OUTPUT_CSV}")
    print(f"MD                          : {OUTPUT_MD}")

    return 0 if audit_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
