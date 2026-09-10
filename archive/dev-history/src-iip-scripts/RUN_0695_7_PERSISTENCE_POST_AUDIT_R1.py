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

OUTPUT_CSV = REPORTS / "PCIP11_0695_7_PERSISTENCE_POST_AUDIT_R1.csv"
OUTPUT_MD = REPORTS / "PCIP11_0695_7_PERSISTENCE_POST_AUDIT_R1.md"

SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from iip.knowledge.repository import ObsidianRepository


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    errors: list[str] = []

    if not EXECUTION_CSV.exists():
        print(f"ERROR: execution report not found: {EXECUTION_CSV}")
        return 2
    if not GATE_CSV.exists():
        print(f"ERROR: gate report not found: {GATE_CSV}")
        return 2
    if not VAULT.exists():
        print(f"ERROR: vault not found: {VAULT}")
        return 2

    execution = load_csv(EXECUTION_CSV)
    gate = load_csv(GATE_CSV)

    if len(execution) != 28:
        errors.append(f"execution_rows={len(execution)}")
    if len(gate) != 28:
        errors.append(f"gate_rows={len(gate)}")

    repository = ObsidianRepository(VAULT)

    results: list[dict[str, str]] = []

    for idx, row in enumerate(execution, start=2):
        evidence_id = row.get("Knowledge_Evidence_ID", "").strip()
        metric_id = row.get("Metric_ID", "").strip()
        ticker = row.get("Ticker", "").strip()
        expected_path = Path(row.get("Saved_Path", "").strip())

        if not evidence_id:
            errors.append(f"row_{idx}:missing_knowledge_id")
            continue

        if not expected_path:
            errors.append(f"row_{idx}:missing_saved_path")
            continue

        actual_exists = expected_path.exists()
        actual_size = expected_path.stat().st_size if actual_exists else 0
        actual_hash = sha256_file(expected_path) if actual_exists else ""

        content = expected_path.read_text(encoding="utf-8") if actual_exists else ""

        checks = {
            "file_exists": actual_exists,
            "file_nonempty": actual_size > 0,
            "type_evidence": "type: evidence" in content,
            "evidence_id": f"evidence_id: {evidence_id}" in content,
            "ticker": f"ticker: {ticker}" in content,
            "document_hash": (
                f"document_hash: {row.get('Document_Hash', '').strip()}" in content
            ),
        }

        # The repository should expose the created evidence when filtered by ticker.
        listed = repository.list_evidence(ticker) if ticker else ()
        listed_match = any(path.resolve() == expected_path.resolve() for path in listed)
        checks["repository_list_evidence"] = listed_match

        status = "PASS" if all(checks.values()) else "FAIL"
        if status == "FAIL":
            for name, passed in checks.items():
                if not passed:
                    errors.append(f"row_{idx}:{name}")

        results.append(
            {
                "Source_Row": row.get("Source_Row", ""),
                "Metric_ID": metric_id,
                "Knowledge_Evidence_ID": evidence_id,
                "Ticker": ticker,
                "Period": row.get("Period", ""),
                "Metric": row.get("Metric", ""),
                "Value": row.get("Value", ""),
                "Saved_Path": str(expected_path),
                "File_Exists": "YES" if actual_exists else "NO",
                "File_Size": str(actual_size),
                "File_SHA256": actual_hash,
                "Audit_Status": status,
            }
        )

    created = sum(r["Audit_Status"] == "PASS" for r in results)
    failed = len(results) - created
    unique_ids = {
        r["Knowledge_Evidence_ID"] for r in results if r["Knowledge_Evidence_ID"]
    }
    duplicate_ids = len(results) - len(unique_ids)

    # Also verify there are exactly 28 files in the expected evidence directory
    # matching the persisted IDs, without modifying anything.
    evidence_dir = VAULT / "04_Evidence"
    expected_files = {
        Path(r["Saved_Path"]).resolve() for r in results if r["Saved_Path"]
    }
    actual_expected_files = (
        {
            p.resolve()
            for p in evidence_dir.glob("*.md")
            if p.resolve() in expected_files
        }
        if evidence_dir.exists()
        else set()
    )

    if len(actual_expected_files) != 28:
        errors.append(f"expected_evidence_files_found={len(actual_expected_files)}")

    audit_pass = (
        len(execution) == 28
        and len(gate) == 28
        and created == 28
        and failed == 0
        and duplicate_ids == 0
        and len(actual_expected_files) == 28
        and not errors
    )

    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        fieldnames = list(results[0].keys()) if results else []
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    lines = [
        "# PCIP11 — 0695.7 Persistence Post-Audit R1",
        "",
        "## Safety",
        "- Audit mode: READ-ONLY",
        "- Vault modified by audit: NO",
        "",
        "## Results",
        f"- Execution report rows: {len(execution)}",
        f"- Gate rows: {len(gate)}",
        f"- Evidence files verified: {created}",
        f"- Failed records: {failed}",
        f"- Duplicate Knowledge IDs: {duplicate_ids}",
        f"- Expected persisted files present: {len(actual_expected_files)}",
        f"- Audit result: {'PASS' if audit_pass else 'FAIL'}",
        "",
        "## Failures",
    ]

    if errors:
        lines.extend(f"- {e}" for e in errors)
    else:
        lines.append("- none")

    lines += [
        "",
        "This audit is read-only and does not modify the Vault.",
    ]
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print("=" * 90)
    print("0695.7 PERSISTENCE POST-AUDIT R1")
    print("=" * 90)
    print(f"Execution report rows       : {len(execution)}")
    print(f"Gate rows                   : {len(gate)}")
    print(f"Evidence files verified     : {created}")
    print(f"Failed records              : {failed}")
    print(f"Duplicate Knowledge IDs     : {duplicate_ids}")
    print(f"Expected files present      : {len(actual_expected_files)}")
    print(f"Audit result                : {'PASS' if audit_pass else 'FAIL'}")
    print("Audit mode                  : READ-ONLY")
    print("Vault modified by audit     : NO")
    print(f"CSV                        : {OUTPUT_CSV}")
    print(f"MD                         : {OUTPUT_MD}")

    return 0 if audit_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
