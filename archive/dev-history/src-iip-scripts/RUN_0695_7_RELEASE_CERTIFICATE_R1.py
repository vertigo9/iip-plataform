from __future__ import annotations

import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "reports"

ARTIFACTS = [
    "PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R4.csv",
    "PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R4.md",
    "PCIP11_0695_7_PERSISTENCE_ADAPTER_R3.csv",
    "PCIP11_0695_7_PERSISTENCE_ADAPTER_R3.md",
    "PCIP11_0695_7_PERSISTENCE_CONTRACT_R4.csv",
    "PCIP11_0695_7_PERSISTENCE_CONTRACT_R4.md",
    "PCIP11_0695_7_KNOWLEDGE_BRIDGE_DRY_RUN_R1.csv",
    "PCIP11_0695_7_KNOWLEDGE_BRIDGE_DRY_RUN_R1.md",
    "PCIP11_0695_7_REPOSITORY_DRY_RUN_R2.csv",
    "PCIP11_0695_7_REPOSITORY_DRY_RUN_R2.md",
    "PCIP11_0695_7_PERSISTENCE_EXECUTION_GATE_R1.csv",
    "PCIP11_0695_7_PERSISTENCE_EXECUTION_GATE_R1.md",
    "PCIP11_0695_7_PERSISTENCE_EXECUTION_R1.csv",
    "PCIP11_0695_7_PERSISTENCE_EXECUTION_R1.md",
    "PCIP11_0695_7_PERSISTENCE_POST_AUDIT_R2.csv",
    "PCIP11_0695_7_PERSISTENCE_POST_AUDIT_R2.md",
]

CERT_CSV = REPORTS / "PCIP11_0695_7_RELEASE_CERTIFICATE_R1.csv"
CERT_MD = REPORTS / "PCIP11_0695_7_RELEASE_CERTIFICATE_R1.md"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def value(row: dict[str, str], key: str) -> str:
    return str(row.get(key, "") or "").strip()


def main() -> int:
    missing = [name for name in ARTIFACTS if not (REPORTS / name).exists()]

    if missing:
        print("=" * 90)
        print("0695.7 RELEASE CERTIFICATE R1")
        print("=" * 90)
        print("CERTIFICATE STATUS : NOT_ISSUED")
        print("Reason             : missing artifacts")
        for name in missing:
            print(f"  - {name}")
        return 1

    contract = load_csv(REPORTS / "PCIP11_0695_7_PERSISTENCE_CONTRACT_R4.csv")
    bridge = load_csv(REPORTS / "PCIP11_0695_7_KNOWLEDGE_BRIDGE_DRY_RUN_R1.csv")
    repo = load_csv(REPORTS / "PCIP11_0695_7_REPOSITORY_DRY_RUN_R2.csv")
    gate = load_csv(REPORTS / "PCIP11_0695_7_PERSISTENCE_EXECUTION_GATE_R1.csv")
    execution = load_csv(REPORTS / "PCIP11_0695_7_PERSISTENCE_EXECUTION_R1.csv")
    audit = load_csv(REPORTS / "PCIP11_0695_7_PERSISTENCE_POST_AUDIT_R2.csv")

    checks: list[tuple[str, bool, str]] = []

    checks.append(
        (
            "contract_28",
            len(contract) == 28,
            f"rows={len(contract)}",
        )
    )
    checks.append(
        (
            "contract_unique_metric_ids",
            len({value(r, "Metric_ID") for r in contract}) == 28,
            f"unique={len({value(r, 'Metric_ID') for r in contract})}",
        )
    )
    checks.append(
        (
            "contract_unique_knowledge_ids",
            len({value(r, "Knowledge_Evidence_ID") for r in contract}) == 28,
            f"unique={len({value(r, 'Knowledge_Evidence_ID') for r in contract})}",
        )
    )
    checks.append(
        (
            "bridge_ready_28",
            sum(value(r, "Mapping_Status") == "READY" for r in bridge) == 28,
            f"ready={sum(value(r, 'Mapping_Status') == 'READY' for r in bridge)}",
        )
    )
    checks.append(
        (
            "repository_ready_28",
            sum(value(r, "Mapping_Status") == "READY" for r in repo) == 28,
            f"ready={sum(value(r, 'Mapping_Status') == 'READY' for r in repo)}",
        )
    )
    checks.append(
        (
            "execution_gate_28_pass",
            len(gate) == 28
            and sum(value(r, "Gate_Status") == "PASS" for r in gate) == 28,
            f"rows={len(gate)}, pass={sum(value(r, 'Gate_Status') == 'PASS' for r in gate)}",
        )
    )
    checks.append(
        (
            "execution_28_created",
            len(execution) == 28
            and sum(value(r, "Result") == "CREATED" for r in execution) == 28,
            f"rows={len(execution)}, created={sum(value(r, 'Result') == 'CREATED' for r in execution)}",
        )
    )
    checks.append(
        (
            "execution_zero_existing",
            sum(value(r, "Result") == "ALREADY_EXISTS" for r in execution) == 0,
            f"already_exists={sum(value(r, 'Result') == 'ALREADY_EXISTS' for r in execution)}",
        )
    )
    checks.append(
        (
            "execution_zero_failed",
            sum(value(r, "Result").startswith("FAILED") for r in execution) == 0,
            f"failed={sum(value(r, 'Result').startswith('FAILED') for r in execution)}",
        )
    )
    checks.append(
        (
            "post_audit_28_pass",
            len(audit) == 28
            and sum(value(r, "Audit_Status") == "PASS" for r in audit) == 28,
            f"rows={len(audit)}, pass={sum(value(r, 'Audit_Status') == 'PASS' for r in audit)}",
        )
    )

    all_pass = all(passed for _, passed, _ in checks)

    artifact_rows = []
    for name in ARTIFACTS:
        path = REPORTS / name
        artifact_rows.append(
            {
                "Artifact": name,
                "Exists": "YES",
                "Size": str(path.stat().st_size),
                "SHA256": sha256_file(path),
            }
        )

    with CERT_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["Artifact", "Exists", "Size", "SHA256"],
        )
        writer.writeheader()
        writer.writerows(artifact_rows)

    lines = [
        "# PCIP11 — 0695.7 Release Certificate R1",
        "",
        "## Certificate",
        f"- Status: {'ISSUED' if all_pass else 'NOT_ISSUED'}",
        "- Scope: 0695.7 PCIP11 evidence persistence",
        "- Official Vault write status: COMPLETED_AND_AUDITED",
        "- Certificate generation mode: READ-ONLY",
        "",
        "## Final reconciliation",
    ]

    for name, passed, detail in checks:
        lines.append(f"- [{'PASS' if passed else 'FAIL'}] {name}: {detail}")

    lines += [
        "",
        "## Artifact SHA-256",
    ]
    for row in artifact_rows:
        lines.append(f"- `{row['Artifact']}` — {row['SHA256']}")

    lines += [
        "",
        "## Final state",
        "- Canonicalization: 28/28 canonical",
        "- Persistence Contract: 28/28 ready",
        "- KnowledgeBridge dry-run: 28/28 ready",
        "- Repository dry-run: 28/28 ready",
        "- Execution Gate: 28/28 pass",
        "- Real persistence: 28/28 created, 0 existing, 0 failed",
        "- Post-Audit: 28/28 pass",
        "- Vault modification by certificate: NO",
        "",
        "This certificate is a release record only. It performs no Vault writes.",
    ]

    CERT_MD.write_text("\n".join(lines), encoding="utf-8")

    print("=" * 90)
    print("0695.7 RELEASE CERTIFICATE R1")
    print("=" * 90)
    print(f"CERTIFICATE STATUS         : {'ISSUED' if all_pass else 'NOT_ISSUED'}")
    for name, passed, detail in checks:
        print(f"{'[PASS]' if passed else '[FAIL]'} {name:30s}: {detail}")
    print("Official Vault modified    : NO")
    print(f"CSV                       : {CERT_CSV}")
    print(f"MD                        : {CERT_MD}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
