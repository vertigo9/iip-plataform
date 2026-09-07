from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "reports"
VAULT = ROOT / "vault"

CONTRACT_CSV = REPORTS / "PCIP11_0695_7_PERSISTENCE_CONTRACT_R4.csv"
GATE_CSV = REPORTS / "PCIP11_0695_7_PERSISTENCE_EXECUTION_GATE_R1.csv"

OUTPUT_CSV = REPORTS / "IIP_HISTORICAL_PERSISTENCE_IDEMPOTENT_AUDIT_R1.csv"
OUTPUT_MD = REPORTS / "IIP_HISTORICAL_PERSISTENCE_IDEMPOTENT_AUDIT_R1.md"

SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from iip.knowledge.repository import ObsidianRepository


def f(row: dict[str, str], key: str) -> str:
    return str(row.get(key, "") or "").strip()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def expected_path(repository: ObsidianRepository, evidence_id: str) -> Path:
    safe = repository._safe_filename(evidence_id)
    return VAULT / "04_Evidence" / f"{safe}.md"


def main() -> int:
    print("=" * 90)
    print("IIP HISTORICAL PERSISTENCE IDEMPOTENT AUDIT R1")
    print("=" * 90)
    print("Mode                        : READ-ONLY")

    errors: list[str] = []

    if not CONTRACT_CSV.exists():
        errors.append(f"missing_contract:{CONTRACT_CSV}")
    if not GATE_CSV.exists():
        errors.append(f"missing_gate:{GATE_CSV}")
    if not VAULT.exists():
        errors.append(f"missing_vault:{VAULT}")

    if errors:
        print("Audit result                : FAIL")
        for error in errors:
            print(f"  - {error}")
        return 1

    contract = load_csv(CONTRACT_CSV)
    gate = load_csv(GATE_CSV)

    if len(contract) != 28:
        errors.append(f"contract_rows={len(contract)}")
    if len(gate) != 28:
        errors.append(f"gate_rows={len(gate)}")

    gate_pass = sum(f(row, "Gate_Status") == "PASS" for row in gate)
    if gate_pass != 28:
        errors.append(f"gate_pass_rows={gate_pass}")

    repository = ObsidianRepository(VAULT)
    results: list[dict[str, str]] = []

    for idx, row in enumerate(contract, start=2):
        evidence_id = f(row, "Knowledge_Evidence_ID")
        metric_id = f(row, "Metric_ID")
        ticker = f(row, "Ticker")
        metric = f(row, "Metric")
        value = f(row, "Value")
        period = f(row, "Period")
        semantic = f(row, "Semantic_Dimension")
        document_hash = f(row, "Document_Hash")
        source_locator = f(row, "Source_Locator")
        lineage = f(row, "Lineage")
        canonical_observation = f(row, "Canonical_Observation_ID")

        row_errors: list[str] = []

        if not evidence_id:
            row_errors.append("missing_knowledge_id")
        if not metric_id:
            row_errors.append("missing_metric_id")

        path = expected_path(repository, evidence_id) if evidence_id else Path()
        exists = path.exists() if evidence_id else False
        size = path.stat().st_size if exists else 0
        content = path.read_text(encoding="utf-8") if exists else ""
        file_hash = sha256_file(path) if exists else ""

        expected_fragments = {
            "type": "type: evidence",
            "evidence_id": f"evidence_id: {evidence_id}",
            "ticker": f"ticker: {ticker}",
            "date": f"date: {period}-01",
            "document_hash": f"document_hash: {document_hash}",
            "metric_id": f"- metric_id: {metric_id}",
            "metric": f"- metric: {metric}",
            "value": f"- value: {value}",
            "period": f"- period: {period}",
            "semantic_dimension": f"- semantic_dimension: {semantic}",
            "source_locator": f"- source_locator: {source_locator}",
            "lineage": f"- lineage: {lineage}",
            "canonical_observation_id": (
                f"- canonical_observation_id: {canonical_observation}"
            ),
        }

        checks = {
            "file_exists": exists,
            "file_nonempty": size > 0,
        }
        for name, fragment in expected_fragments.items():
            checks[name] = fragment in content

        for check_name, passed in checks.items():
            if not passed:
                row_errors.append(check_name)

        status = "PASS" if not row_errors else "FAIL"
        if row_errors:
            errors.extend(f"row_{idx}:{failure}" for failure in row_errors)

        results.append(
            {
                "Source_Row": f(row, "Source_Row"),
                "Metric_ID": metric_id,
                "Knowledge_Evidence_ID": evidence_id,
                "Ticker": ticker,
                "Period": period,
                "Metric": metric,
                "Value": value,
                "Expected_Path": str(path),
                "File_Exists": "YES" if exists else "NO",
                "File_Size": str(size),
                "File_SHA256": file_hash,
                "Audit_Status": status,
                "Failure_Details": ",".join(row_errors),
            }
        )

    # Ensure all 28 contract IDs map to distinct physical files.
    expected_paths = {
        Path(row["Expected_Path"]).resolve() for row in results if row["Expected_Path"]
    }
    existing_paths = {path for path in expected_paths if path.exists()}
    unique_ids = {
        row["Knowledge_Evidence_ID"] for row in results if row["Knowledge_Evidence_ID"]
    }

    passed = sum(row["Audit_Status"] == "PASS" for row in results)
    failed = len(results) - passed

    audit_pass = (
        len(contract) == 28
        and len(gate) == 28
        and gate_pass == 28
        and len(unique_ids) == 28
        and len(existing_paths) == 28
        and passed == 28
        and failed == 0
        and not errors
    )

    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        fields = list(results[0].keys()) if results else []
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    lines = [
        "# IIP — Historical Persistence Idempotent Audit R1",
        "",
        "## Safety",
        "- Mode: READ-ONLY",
        "- Vault modified by audit: NO",
        "- This audit does not depend on the last execution outcome.",
        "",
        "## Results",
        f"- Contract rows: {len(contract)}",
        f"- Gate PASS rows: {gate_pass}",
        f"- Unique Knowledge IDs: {len(unique_ids)}",
        f"- Expected files present: {len(existing_paths)}",
        f"- Content verified: {passed}",
        f"- Failed records: {failed}",
        f"- Audit result: {'PASS' if audit_pass else 'FAIL'}",
        "",
        "## Design correction",
        "- Existing evidence is audited from the canonical contract and the physical Vault.",
        "- A prior execution report marked ALREADY_EXISTS does not invalidate already persisted evidence.",
        "",
        "## Failures",
    ]
    if errors:
        lines.extend(f"- {error}" for error in errors)
    else:
        lines.append("- none")

    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"Contract rows               : {len(contract)}")
    print(f"Gate PASS rows              : {gate_pass}")
    print(f"Unique Knowledge IDs        : {len(unique_ids)}")
    print(f"Expected files present      : {len(existing_paths)}")
    print(f"Content verified            : {passed}")
    print(f"Failed records              : {failed}")
    print(f"Audit result                : {'PASS' if audit_pass else 'FAIL'}")
    print("Vault modified by audit     : NO")
    print(f"CSV                         : {OUTPUT_CSV}")
    print(f"MD                          : {OUTPUT_MD}")

    return 0 if audit_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
