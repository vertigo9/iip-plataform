from __future__ import annotations

import csv
import hashlib
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "reports"

GATE_CSV = REPORTS / "PCIP11_0695_7_PERSISTENCE_EXECUTION_GATE_R1.csv"
CONTRACT_CSV = REPORTS / "PCIP11_0695_7_PERSISTENCE_CONTRACT_R4.csv"

OUTPUT_CSV = REPORTS / "PCIP11_0695_7_PERSISTENCE_EXECUTION_R1.csv"
OUTPUT_MD = REPORTS / "PCIP11_0695_7_PERSISTENCE_EXECUTION_R1.md"

# IMPORTANT:
# Set this explicitly to the user's OFFICIAL Obsidian Vault path before
# running the executor. No default path is assumed.
OFFICIAL_VAULT = r"D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1\vault"

SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from iip.intelligence.metric_identity import MetricObservationIdentity
from iip.intelligence.metric_persistence import (
    build_knowledge_evidence,
    knowledge_evidence_id,
    metric_evidence_id,
)
from iip.knowledge.bridge import KnowledgeBridge
from iip.knowledge.models import Evidence


def pick(row: dict[str, str], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def build_identity(row: dict[str, str]) -> MetricObservationIdentity:
    period = pick(row, "Period")
    if len(period) != 7 or period[4] != "-":
        raise ValueError(f"invalid period: {period!r}")

    return MetricObservationIdentity(
        canonical_ticker=pick(row, "Ticker"),
        original_ticker=pick(row, "Original_Ticker") or pick(row, "Ticker"),
        metric_name=pick(row, "Metric"),
        value=pick(row, "Value"),
        unit=pick(row, "Unit") or None,
        scale=pick(row, "Scale") or None,
        period=period,
        semantic_dimension=pick(row, "Semantic_Dimension") or None,
        document_hash=pick(row, "Document_Hash"),
        document_id=pick(row, "Document_ID") or None,
        source_locator=pick(row, "Source_Locator") or None,
        lineage=pick(row, "Lineage") or None,
    )


def build_evidence(row: dict[str, str]) -> Evidence:
    identity = build_identity(row)

    metric_id = metric_evidence_id(identity)
    expected_knowledge_id = knowledge_evidence_id(metric_id)

    actual_metric_id = pick(row, "Metric_ID")
    actual_knowledge_id = pick(row, "Knowledge_Evidence_ID")

    if actual_metric_id != metric_id:
        raise ValueError(
            f"Metric_ID mismatch: contract={actual_metric_id!r} expected={metric_id!r}"
        )

    if actual_knowledge_id != expected_knowledge_id:
        raise ValueError(
            f"Knowledge_Evidence_ID mismatch: contract={actual_knowledge_id!r} "
            f"expected={expected_knowledge_id!r}"
        )

    km = build_knowledge_evidence(
        identity,
        title=pick(
            row,
            "Title",
            "Source_FileName",
            "Source_FileNames",
        )
        or f"{identity.canonical_ticker} {identity.period} historical metric evidence",
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
            f"semantic_dimension: {identity.semantic_dimension or ''}",
            f"document_id: {identity.document_id or ''}",
            f"document_hash: {identity.document_hash}",
            f"source_locator: {identity.source_locator or ''}",
            f"lineage: {identity.lineage or ''}",
            f"canonical_observation_id: {pick(row, 'Canonical_Observation_ID')}",
            f"resolution_status: {pick(row, 'Resolution_Status')}",
            f"resolution_type: {pick(row, 'Resolution_Type')}",
            f"resolution_selected_context: {pick(row, 'Resolution_Selected_Context')}",
        ),
    )


def main() -> int:
    print("=" * 90)
    print("0695.7 PERSISTENCE EXECUTION R1")
    print("=" * 90)

    # Hard stop unless the official Vault path is explicitly configured.
    if not OFFICIAL_VAULT:
        print("EXECUTION AUTHORIZED         : NO")
        print("Reason                       : OFFICIAL_VAULT is not configured")
        print("Persistence executed         : NO")
        print("KnowledgeBridge executed     : NO")
        print("Vault changed                : NO")
        print()
        print("Set OFFICIAL_VAULT in this script to the real Obsidian Vault path")
        print("only after confirming the Execution Gate R1 is still valid.")
        return 2

    vault_path = Path(OFFICIAL_VAULT)
    if not vault_path.exists():
        print("EXECUTION AUTHORIZED         : NO")
        print(f"Reason                       : Vault not found: {vault_path}")
        print("Persistence executed         : NO")
        print("KnowledgeBridge executed     : NO")
        print("Vault changed                : NO")
        return 2

    # Fresh gate revalidation.
    try:
        gate = load_csv(GATE_CSV)
        contract = load_csv(CONTRACT_CSV)
    except Exception as exc:
        print("EXECUTION AUTHORIZED         : NO")
        print(f"Reason                       : cannot load gate artifacts: {exc}")
        print("Persistence executed         : NO")
        print("KnowledgeBridge executed     : NO")
        print("Vault changed                : NO")
        return 3

    errors: list[str] = []

    if len(gate) != 28:
        errors.append(f"gate_rows={len(gate)}")
    if len(contract) != 28:
        errors.append(f"contract_rows={len(contract)}")

    # Rebuild the gate IDs from the current contract.
    metric_ids = []
    knowledge_ids = []

    for idx, row in enumerate(contract, start=2):
        try:
            identity = build_identity(row)
            metric_id = metric_evidence_id(identity)
            knowledge_id = knowledge_evidence_id(metric_id)

            if pick(row, "Metric_ID") != metric_id:
                errors.append(f"row_{idx}:metric_id_mismatch")

            if pick(row, "Knowledge_Evidence_ID") != knowledge_id:
                errors.append(f"row_{idx}:knowledge_id_mismatch")

            metric_ids.append(metric_id)
            knowledge_ids.append(knowledge_id)

        except Exception as exc:
            errors.append(f"row_{idx}:identity_error:{type(exc).__name__}:{exc}")

    if len(set(metric_ids)) != 28:
        errors.append("duplicate_metric_ids")
    if len(set(knowledge_ids)) != 28:
        errors.append("duplicate_knowledge_ids")

    # The gate artifact must itself carry 28 PASS rows.
    gate_statuses = Counter(pick(row, "Gate_Status") for row in gate)
    if gate_statuses.get("PASS", 0) != 28:
        errors.append(f"gate_pass_rows={gate_statuses.get('PASS', 0)}")

    contract_sha = sha256_file(CONTRACT_CSV)
    gate_sha = sha256_file(GATE_CSV)

    if errors:
        print("EXECUTION AUTHORIZED         : NO")
        print("Reason                       : fresh gate validation failed")
        for error in errors:
            print(f"  - {error}")
        print("Persistence executed         : NO")
        print("KnowledgeBridge executed     : NO")
        print("Vault changed                : NO")
        return 4

    # Build all objects before writing any object: fail-closed preparation.
    prepared: list[tuple[dict[str, str], Evidence]] = []
    prep_errors: list[str] = []

    for idx, row in enumerate(contract, start=2):
        try:
            evidence = build_evidence(row)
            prepared.append((row, evidence))
        except Exception as exc:
            prep_errors.append(f"row_{idx}:{type(exc).__name__}:{exc}")

    if prep_errors or len(prepared) != 28:
        print("EXECUTION AUTHORIZED         : NO")
        print("Reason                       : evidence preparation failed")
        for error in prep_errors:
            print(f"  - {error}")
        print("Persistence executed         : NO")
        print("KnowledgeBridge executed     : NO")
        print("Vault changed                : NO")
        return 5

    # Real KnowledgeBridge + real repository.
    bridge = KnowledgeBridge(vault_path)

    results: list[dict[str, str]] = []
    failures = []
    created_paths: list[Path] = []

    for source_row, evidence in prepared:
        try:
            # Persist through the real production bridge.
            saved_path = bridge.persist_evidence(evidence)

            path = Path(saved_path)
            exists = path.exists()
            size = path.stat().st_size if exists else 0
            file_hash = sha256_file(path) if exists else ""

            results.append(
                {
                    "Source_Row": pick(source_row, "Source_Row") or "",
                    "Metric_ID": pick(source_row, "Metric_ID"),
                    "Knowledge_Evidence_ID": evidence.evidence_id,
                    "Ticker": evidence.ticker,
                    "Period": pick(source_row, "Period"),
                    "Metric": pick(source_row, "Metric"),
                    "Value": pick(source_row, "Value"),
                    "Document_Hash": evidence.document_hash,
                    "Saved_Path": str(path),
                    "File_Exists": "YES" if exists else "NO",
                    "File_Size": str(size),
                    "File_SHA256": file_hash,
                    "Result": "CREATED" if exists and size > 0 else "FAILED",
                }
            )

            if exists and size > 0:
                created_paths.append(path)
            else:
                failures.append(f"{evidence.evidence_id}:file_missing_or_empty")

        except FileExistsError:
            # Append-only behavior: do not overwrite.
            results.append(
                {
                    "Source_Row": pick(source_row, "Source_Row") or "",
                    "Metric_ID": pick(source_row, "Metric_ID"),
                    "Knowledge_Evidence_ID": evidence.evidence_id,
                    "Ticker": evidence.ticker,
                    "Period": pick(source_row, "Period"),
                    "Metric": pick(source_row, "Metric"),
                    "Value": pick(source_row, "Value"),
                    "Document_Hash": evidence.document_hash,
                    "Saved_Path": "",
                    "File_Exists": "YES",
                    "File_Size": "",
                    "File_SHA256": "",
                    "Result": "ALREADY_EXISTS",
                }
            )
            failures.append(f"{evidence.evidence_id}:already_exists")

        except Exception as exc:
            results.append(
                {
                    "Source_Row": pick(source_row, "Source_Row") or "",
                    "Metric_ID": pick(source_row, "Metric_ID"),
                    "Knowledge_Evidence_ID": evidence.evidence_id,
                    "Ticker": evidence.ticker,
                    "Period": pick(source_row, "Period"),
                    "Metric": pick(source_row, "Metric"),
                    "Value": pick(source_row, "Value"),
                    "Document_Hash": evidence.document_hash,
                    "Saved_Path": "",
                    "File_Exists": "NO",
                    "File_Size": "",
                    "File_SHA256": "",
                    "Result": f"FAILED:{type(exc).__name__}",
                }
            )
            failures.append(f"{evidence.evidence_id}:{type(exc).__name__}:{exc}")

    created = sum(row["Result"] == "CREATED" for row in results)
    already_exists = sum(row["Result"] == "ALREADY_EXISTS" for row in results)
    failed = len(results) - created - already_exists

    # No rollback: repository is append-only. The report is the audit record.
    # A partial write is therefore surfaced explicitly rather than overwritten.
    success = (
        len(results) == 28
        and created == 28
        and already_exists == 0
        and failed == 0
        and not failures
    )

    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        fieldnames = list(results[0].keys()) if results else []
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    lines = [
        "# PCIP11 â€” 0695.7 Persistence Execution R1",
        "",
        "## Execution",
        "- Execution authorized before write: YES",
        f"- Contract SHA-256: {contract_sha}",
        f"- Gate SHA-256: {gate_sha}",
        f"- Target Vault: `{vault_path}`",
        "",
        "## Results",
        f"- Prepared: {len(prepared)}",
        f"- Created: {created}",
        f"- Already existed: {already_exists}",
        f"- Failed: {failed}",
        f"- Execution result: {'SUCCESS' if success else 'PARTIAL_OR_FAILED'}",
        "- KnowledgeBridge executed: YES",
        "- Repository save_evidence executed: YES",
        f"- Official Vault changed: {'YES' if created > 0 else 'NO'}",
        "",
        "## Failures",
    ]

    if failures:
        lines.extend(f"- {item}" for item in failures)
    else:
        lines.append("- none")

    lines += [
        "",
        "## Safety notes",
        "- The official Vault path is explicit and must be configured in the script.",
        "- The execution revalidates the contract and gate before any write.",
        "- Evidence objects are prepared before writes begin.",
        "- No overwrite or automatic correction is attempted.",
        "- The repository remains append-only.",
    ]

    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"Execution prepared           : {len(prepared)}")
    print(f"Created                       : {created}")
    print(f"Already existed              : {already_exists}")
    print(f"Failed                       : {failed}")
    print(
        f"Execution result              : "
        f"{'SUCCESS' if success else 'PARTIAL_OR_FAILED'}"
    )
    print("KnowledgeBridge executed      : YES")
    print("Repository save_evidence      : YES")
    print(f"Official Vault changed        : {'YES' if created > 0 else 'NO'}")
    print(f"CSV                          : {OUTPUT_CSV}")
    print(f"MD                           : {OUTPUT_MD}")

    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
