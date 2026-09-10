from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "reports"

INPUT_CSV = REPORTS / "PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R4.csv"
CONTRACT_CSV = REPORTS / "PCIP11_0695_7_PERSISTENCE_CONTRACT_R4.csv"
GATE_CSV = REPORTS / "PCIP11_0695_7_PERSISTENCE_EXECUTION_GATE_R1.csv"

PREFLIGHT_SCRIPT = (
    ROOT / "src/iip/scripts/RUN_IIP_HISTORICAL_PERSISTENCE_PREFLIGHT_R1.py"
)
CONTRACT_SCRIPT = ROOT / "src/iip/scripts/RUN_0695_7_PERSISTENCE_CONTRACT_R4.py"
BRIDGE_SCRIPT = ROOT / "src/iip/scripts/RUN_0695_7_KNOWLEDGE_BRIDGE_DRY_RUN_R1.py"
REPO_SCRIPT = ROOT / "src/iip/scripts/RUN_0695_7_REPOSITORY_DRY_RUN_R2.py"
GATE_SCRIPT = ROOT / "src/iip/scripts/RUN_0695_7_PERSISTENCE_EXECUTION_GATE_R1.py"
EXECUTION_SCRIPT = ROOT / "src/iip/scripts/RUN_0695_7_PERSISTENCE_EXECUTION_R1.py"
AUDIT_SCRIPT = ROOT / "src/iip/scripts/RUN_0695_7_PERSISTENCE_POST_AUDIT_R2.py"
CERTIFICATE_SCRIPT = ROOT / "src/iip/scripts/RUN_0695_7_RELEASE_CERTIFICATE_R1.py"

OUTPUT_CSV = REPORTS / "IIP_HISTORICAL_PERSISTENCE_PIPELINE_R2.csv"
OUTPUT_MD = REPORTS / "IIP_HISTORICAL_PERSISTENCE_PIPELINE_R2.md"


def run_script(path: Path) -> tuple[int, str]:
    if not path.exists():
        return 127, f"script not found: {path}"
    completed = subprocess.run(
        [sys.executable, str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.returncode, (completed.stdout or "") + (completed.stderr or "")


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def f(row: dict[str, str], key: str) -> str:
    return str(row.get(key, "") or "").strip()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def expected_path(vault: Path, evidence_id: str) -> Path:
    # Same filename policy as ObsidianRepository._safe_filename.
    invalid = '<>:"/\\|?*'
    safe = evidence_id
    for char in invalid:
        safe = safe.replace(char, "_")
    safe = " ".join(safe.split())
    while "__" in safe:
        safe = safe.replace("__", "_")
    safe = safe.strip(" ._") or "record"
    return vault / "04_Evidence" / f"{safe}.md"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="IIP Historical Persistence Pipeline R2"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="perform real persistence only when the batch is entirely new",
    )
    parser.add_argument(
        "--vault",
        default=None,
        help="official Vault path; required with --execute",
    )
    args = parser.parse_args()

    REPORTS.mkdir(parents=True, exist_ok=True)

    print("=" * 90)
    print("IIP HISTORICAL PERSISTENCE PIPELINE R2")
    print("=" * 90)
    print(
        f"Mode                        : {'EXECUTE' if args.execute else 'VALIDATE_ONLY'}"
    )
    print(f"Input                       : {INPUT_CSV}")

    results: list[dict[str, str]] = []
    errors: list[str] = []

    # R2 intentionally reuses the proven gates instead of duplicating their logic.
    steps = [
        ("preflight", PREFLIGHT_SCRIPT),
        ("persistence_contract", CONTRACT_SCRIPT),
        ("knowledge_bridge_dry_run", BRIDGE_SCRIPT),
        ("repository_dry_run", REPO_SCRIPT),
        ("execution_gate", GATE_SCRIPT),
    ]

    for name, script in steps:
        rc, output = run_script(script)
        ok = rc == 0
        results.append(
            {
                "Step": name,
                "Script": str(script),
                "Return_Code": str(rc),
                "Status": "PASS" if ok else "FAIL",
                "Detail": output.strip().splitlines()[-1] if output.strip() else "",
            }
        )
        print(f"[{'PASS' if ok else 'FAIL'}] {name:28s} return_code={rc}")
        if not ok:
            errors.append(f"{name}:return_code={rc}")
            print(output)
            break

    if not errors and args.execute:
        if not args.vault:
            errors.append("--vault is required with --execute")
        else:
            vault = Path(args.vault)
            if not vault.exists():
                errors.append(f"vault_not_found:{vault}")

            if not errors:
                contract = load_csv(CONTRACT_CSV)
                if len(contract) != 28:
                    errors.append(f"contract_rows={len(contract)}")

                existing = []
                missing = []

                for row in contract:
                    evidence_id = f(row, "Knowledge_Evidence_ID")
                    path = expected_path(vault, evidence_id)
                    (existing if path.exists() else missing).append(path)

                print(f"Existing evidence files       : {len(existing)}")
                print(f"Missing evidence files        : {len(missing)}")

                if len(existing) == 28:
                    # Idempotent path: never call save_evidence again.
                    print("[INFO] Entire batch already persisted; skipping write.")
                    results.append(
                        {
                            "Step": "idempotent_reconciliation",
                            "Script": str(AUDIT_SCRIPT),
                            "Return_Code": "0",
                            "Status": "ALREADY_PERSISTED",
                            "Detail": "28/28 evidence files already exist",
                        }
                    )

                    rc, output = run_script(AUDIT_SCRIPT)
                    ok = rc == 0
                    results.append(
                        {
                            "Step": "post_audit",
                            "Script": str(AUDIT_SCRIPT),
                            "Return_Code": str(rc),
                            "Status": "PASS" if ok else "FAIL",
                            "Detail": output.strip().splitlines()[-1]
                            if output.strip()
                            else "",
                        }
                    )
                    if not ok:
                        errors.append(f"post_audit:return_code={rc}")
                        print(output)

                    if ok:
                        rc, output = run_script(CERTIFICATE_SCRIPT)
                        ok = rc == 0
                        results.append(
                            {
                                "Step": "release_certificate",
                                "Script": str(CERTIFICATE_SCRIPT),
                                "Return_Code": str(rc),
                                "Status": "PASS" if ok else "FAIL",
                                "Detail": output.strip().splitlines()[-1]
                                if output.strip()
                                else "",
                            }
                        )
                        if not ok:
                            errors.append(f"release_certificate:return_code={rc}")
                            print(output)

                elif len(existing) == 0:
                    # Entirely new batch: run the proven real executor.
                    executor_lines = EXECUTION_SCRIPT.read_text(
                        encoding="utf-8"
                    ).splitlines()
                    marker = "OFFICIAL_VAULT = "
                    replaced = False
                    for i, line in enumerate(executor_lines):
                        if line.startswith(marker):
                            executor_lines[i] = f'OFFICIAL_VAULT = r"{vault}"'
                            replaced = True
                            break

                    if not replaced:
                        errors.append("OFFICIAL_VAULT marker not found")
                    else:
                        EXECUTION_SCRIPT.write_text(
                            "\n".join(executor_lines) + "\n",
                            encoding="utf-8",
                        )

                    if not errors:
                        rc, output = run_script(EXECUTION_SCRIPT)
                        ok = rc == 0
                        results.append(
                            {
                                "Step": "persistence_execution",
                                "Script": str(EXECUTION_SCRIPT),
                                "Return_Code": str(rc),
                                "Status": "PASS" if ok else "FAIL",
                                "Detail": output.strip().splitlines()[-1]
                                if output.strip()
                                else "",
                            }
                        )
                        print(f"[{'PASS' if ok else 'FAIL'}] persistence_execution")
                        if not ok:
                            errors.append(f"persistence_execution:return_code={rc}")
                            print(output)

                        if ok:
                            rc, output = run_script(AUDIT_SCRIPT)
                            ok = rc == 0
                            results.append(
                                {
                                    "Step": "post_audit",
                                    "Script": str(AUDIT_SCRIPT),
                                    "Return_Code": str(rc),
                                    "Status": "PASS" if ok else "FAIL",
                                    "Detail": output.strip().splitlines()[-1]
                                    if output.strip()
                                    else "",
                                }
                            )
                            print(f"[{'PASS' if ok else 'FAIL'}] post_audit")
                            if not ok:
                                errors.append(f"post_audit:return_code={rc}")
                                print(output)

                        if not errors:
                            rc, output = run_script(CERTIFICATE_SCRIPT)
                            ok = rc == 0
                            results.append(
                                {
                                    "Step": "release_certificate",
                                    "Script": str(CERTIFICATE_SCRIPT),
                                    "Return_Code": str(rc),
                                    "Status": "PASS" if ok else "FAIL",
                                    "Detail": output.strip().splitlines()[-1]
                                    if output.strip()
                                    else "",
                                }
                            )
                            print(f"[{'PASS' if ok else 'FAIL'}] release_certificate")
                            if not ok:
                                errors.append(f"release_certificate:return_code={rc}")
                                print(output)

                else:
                    # Mixed state is deliberately fail-closed. The current
                    # single-batch executor must not be allowed to collide
                    # with already persisted records.
                    errors.append(
                        f"mixed_batch_state:existing={len(existing)},missing={len(missing)}"
                    )
                    print(
                        "[STOP] Mixed persisted/new batch detected; "
                        "no persistence attempted."
                    )

    pipeline_status = "PASS" if not errors else "FAIL"
    if not args.execute and not errors:
        pipeline_status = "PASS_VALIDATION_ONLY"
        print("[STOP] validation_only before real persistence")

    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["Step", "Script", "Return_Code", "Status", "Detail"],
        )
        writer.writeheader()
        writer.writerows(results)

    lines = [
        "# IIP — Historical Persistence Pipeline R2",
        "",
        "## Status",
        f"- Pipeline status: {pipeline_status}",
        f"- Mode: {'EXECUTE' if args.execute else 'VALIDATE_ONLY'}",
        f"- Input SHA-256: {sha256_file(INPUT_CSV) if INPUT_CSV.exists() else 'N/A'}",
        "",
        "## Safety",
        "- Default mode is validation-only.",
        "- Fully persisted batches are treated as ALREADY_PERSISTED and are never rewritten.",
        "- Mixed persisted/new batches are fail-closed.",
        "- Existing evidence is never overwritten.",
        "",
        "## Steps",
    ]

    for row in results:
        lines.append(f"- [{row['Status']}] {row['Step']} — {row['Detail']}")

    lines += [
        "",
        "## Errors",
    ]
    if errors:
        lines.extend(f"- {error}" for error in errors)
    else:
        lines.append("- none")

    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"Pipeline status             : {pipeline_status}")
    print(f"Manifest CSV                : {OUTPUT_CSV}")
    print(f"Manifest MD                 : {OUTPUT_MD}")

    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
