from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "reports"

# Reference configuration for the now-validated PCIP11 0695.7 flow.
# For a future asset, change INPUT_CSV and the asset-specific artifact names.
INPUT_CSV = REPORTS / "PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R4.csv"

STEPS = [
    (
        "preflight",
        ROOT / "src/iip/scripts/RUN_IIP_HISTORICAL_PERSISTENCE_PREFLIGHT_R1.py",
        False,
    ),
    (
        "persistence_contract",
        ROOT / "src/iip/scripts/RUN_0695_7_PERSISTENCE_CONTRACT_R4.py",
        False,
    ),
    (
        "knowledge_bridge_dry_run",
        ROOT / "src/iip/scripts/RUN_0695_7_KNOWLEDGE_BRIDGE_DRY_RUN_R1.py",
        False,
    ),
    (
        "repository_dry_run",
        ROOT / "src/iip/scripts/RUN_0695_7_REPOSITORY_DRY_RUN_R2.py",
        False,
    ),
    (
        "execution_gate",
        ROOT / "src/iip/scripts/RUN_0695_7_PERSISTENCE_EXECUTION_GATE_R1.py",
        False,
    ),
]

EXECUTION_SCRIPT = ROOT / "src/iip/scripts/RUN_0695_7_PERSISTENCE_EXECUTION_R1.py"
AUDIT_SCRIPT = ROOT / "src/iip/scripts/RUN_0695_7_PERSISTENCE_POST_AUDIT_R2.py"
CERTIFICATE_SCRIPT = ROOT / "src/iip/scripts/RUN_0695_7_RELEASE_CERTIFICATE_R1.py"

OUTPUT_CSV = REPORTS / "IIP_HISTORICAL_PERSISTENCE_PIPELINE_R1.csv"
OUTPUT_MD = REPORTS / "IIP_HISTORICAL_PERSISTENCE_PIPELINE_R1.md"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_script(name: str, path: Path) -> tuple[int, str]:
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
    combined = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode, combined


def read_last_nonempty_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def report_exists(name: str) -> bool:
    return (REPORTS / name).exists()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="IIP Historical Persistence Pipeline R1"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="run the real persistence step; otherwise stop before it",
    )
    parser.add_argument(
        "--vault",
        default=None,
        help="official Vault path; required with --execute",
    )
    args = parser.parse_args()

    REPORTS.mkdir(parents=True, exist_ok=True)

    print("=" * 90)
    print("IIP HISTORICAL PERSISTENCE PIPELINE R1")
    print("=" * 90)
    print(
        f"Mode                        : {'EXECUTE' if args.execute else 'VALIDATE_ONLY'}"
    )
    print(f"Input                       : {INPUT_CSV}")

    if not INPUT_CSV.exists():
        print("Pipeline status             : FAIL")
        print(f"Reason                      : input not found: {INPUT_CSV}")
        return 2

    results: list[dict[str, str]] = []
    overall_pass = True

    # Generic preflight should always run first.
    # The current preflight script is configured for the reference PCIP11 input.
    for step_name, script_path, _ in STEPS:
        returncode, output = run_script(step_name, script_path)
        ok = returncode == 0
        overall_pass = overall_pass and ok
        results.append(
            {
                "Step": step_name,
                "Script": str(script_path),
                "Return_Code": str(returncode),
                "Status": "PASS" if ok else "FAIL",
                "Last_Output_Line": read_last_nonempty_line(output),
            }
        )
        print(f"[{'PASS' if ok else 'FAIL'}] {step_name:28s} return_code={returncode}")
        if not ok:
            print(output)
            break

    # Never proceed to real persistence if any preceding gate failed.
    if overall_pass and args.execute:
        if not args.vault:
            print("Pipeline status             : FAIL")
            print("Reason                      : --vault is required with --execute")
            overall_pass = False
        else:
            vault = Path(args.vault)
            if not vault.exists():
                print("Pipeline status             : FAIL")
                print(f"Reason                      : Vault not found: {vault}")
                overall_pass = False
            else:
                # Update the executor's explicit Vault configuration in a
                # controlled way, preserving the executor's own safety gates.
                executor_text = EXECUTION_SCRIPT.read_text(encoding="utf-8")
                marker = "OFFICIAL_VAULT = "
                lines = executor_text.splitlines()
                changed = False
                for i, line in enumerate(lines):
                    if line.startswith(marker):
                        lines[i] = f'OFFICIAL_VAULT = r"{vault}"'
                        changed = True
                        break

                if not changed:
                    print("Pipeline status             : FAIL")
                    print(
                        "Reason                      : OFFICIAL_VAULT marker not found"
                    )
                    overall_pass = False
                else:
                    EXECUTION_SCRIPT.write_text(
                        "\n".join(lines) + "\n",
                        encoding="utf-8",
                    )

        if overall_pass:
            returncode, output = run_script("persistence_execution", EXECUTION_SCRIPT)
            ok = returncode == 0
            overall_pass = overall_pass and ok
            results.append(
                {
                    "Step": "persistence_execution",
                    "Script": str(EXECUTION_SCRIPT),
                    "Return_Code": str(returncode),
                    "Status": "PASS" if ok else "FAIL",
                    "Last_Output_Line": read_last_nonempty_line(output),
                }
            )
            print(
                f"[{'PASS' if ok else 'FAIL'}] "
                f"{'persistence_execution':28s} return_code={returncode}"
            )
            if not ok:
                print(output)

        # Audit only after a successful real execution.
        if overall_pass:
            returncode, output = run_script("post_audit", AUDIT_SCRIPT)
            ok = returncode == 0
            overall_pass = overall_pass and ok
            results.append(
                {
                    "Step": "post_audit",
                    "Script": str(AUDIT_SCRIPT),
                    "Return_Code": str(returncode),
                    "Status": "PASS" if ok else "FAIL",
                    "Last_Output_Line": read_last_nonempty_line(output),
                }
            )
            print(
                f"[{'PASS' if ok else 'FAIL'}] "
                f"{'post_audit':28s} return_code={returncode}"
            )
            if not ok:
                print(output)

        # Certificate only after successful post-audit.
        if overall_pass:
            returncode, output = run_script("release_certificate", CERTIFICATE_SCRIPT)
            ok = returncode == 0
            overall_pass = overall_pass and ok
            results.append(
                {
                    "Step": "release_certificate",
                    "Script": str(CERTIFICATE_SCRIPT),
                    "Return_Code": str(returncode),
                    "Status": "PASS" if ok else "FAIL",
                    "Last_Output_Line": read_last_nonempty_line(output),
                }
            )
            print(
                f"[{'PASS' if ok else 'FAIL'}] "
                f"{'release_certificate':28s} return_code={returncode}"
            )
            if not ok:
                print(output)

    if not args.execute and overall_pass:
        print("[STOP] validation_only                 before real persistence")

    # Save orchestration manifest.
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "Step",
                "Script",
                "Return_Code",
                "Status",
                "Last_Output_Line",
            ],
        )
        writer.writeheader()
        writer.writerows(results)

    lines = [
        "# IIP — Historical Persistence Pipeline R1",
        "",
        "## Mode",
        f"- Execution requested: {'YES' if args.execute else 'NO'}",
        f"- Pipeline status: {'PASS' if overall_pass else 'FAIL'}",
        f"- Input SHA-256: {sha256_file(INPUT_CSV)}",
        "",
        "## Safety",
        "- Default mode is VALIDATE_ONLY.",
        "- Real persistence is never reached unless all prior gates pass.",
        "- The real executor keeps its own Execution Gate and append-only protections.",
        "",
        "## Steps",
    ]

    for row in results:
        lines.append(
            f"- [{row['Status']}] {row['Step']} — return_code={row['Return_Code']}"
        )

    lines += [
        "",
        "## Policy",
        "- A failed gate stops the pipeline.",
        "- Validation mode never writes to the Vault.",
        "- Execution mode requires an explicit --vault argument.",
        "- Post-audit and release certificate run only after successful execution.",
    ]

    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"Pipeline status             : {'PASS' if overall_pass else 'FAIL'}")
    print(f"Manifest CSV                : {OUTPUT_CSV}")
    print(f"Manifest MD                 : {OUTPUT_MD}")

    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
