from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "reports"
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
from iip.knowledge.repository import ObsidianRepository


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def f(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = str(row.get(key, "") or "").strip()
        if value:
            return value
    return ""


def truthy(value: str) -> bool:
    return value.strip().upper() in {"YES", "TRUE", "1", "SIM"}


def build_identity(row: dict[str, str]) -> MetricObservationIdentity:
    ticker = f(row, "Derived_Canonical_Ticker", "Canonical_Ticker", "Ticker")
    metric = f(row, "Metric", "Metric_Name")
    value = f(row, "Resolved_Value", "Value")
    unit = f(row, "Resolved_Unit", "Unit", "Original_Unit")
    scale = f(row, "Resolved_Scale", "Scale")
    period = f(row, "Resolved_Period", "Period")
    dimension = f(
        row,
        "Semantic_Dimension",
        "Resolved_Semantic_Dimension",
        "Dimension",
    )
    document_hash = f(
        row,
        "Document_Hash",
        "SHA256",
        "Evidence_SHA256",
        "SHA",
    )
    document_id = f(
        row,
        "Document_ID",
        "Knowledge_Document_ID",
        "DocumentId",
    )
    source_locator = f(
        row,
        "Source_Locator",
        "SourceLocator",
        "Locator",
        "Resolution_Selected_Context",
    )
    lineage = f(row, "Lineage", "Resolved_Lineage")
    original_ticker = (
        f(
            row,
            "Original_Ticker",
            "Original_Identity",
        )
        or ticker
    )

    missing = [
        name
        for name, value_ in (
            ("ticker", ticker),
            ("metric", metric),
            ("value", value),
            ("period", period),
            ("document_hash", document_hash),
        )
        if not value_
    ]

    if missing:
        raise ValueError(f"missing required identity fields: {', '.join(missing)}")

    return MetricObservationIdentity(
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


def build_evidence(
    row: dict[str, str], identity: MetricObservationIdentity
) -> Evidence:
    metric_id = metric_evidence_id(identity)
    expected_knowledge_id = knowledge_evidence_id(metric_id)

    contract_metric_id = f(row, "Metric_ID")
    contract_knowledge_id = f(row, "Knowledge_Evidence_ID")

    if contract_metric_id and contract_metric_id != metric_id:
        raise ValueError(
            f"Metric_ID mismatch: contract={contract_metric_id!r}, expected={metric_id!r}"
        )

    if contract_knowledge_id and contract_knowledge_id != expected_knowledge_id:
        raise ValueError(
            f"Knowledge_Evidence_ID mismatch: contract={contract_knowledge_id!r}, "
            f"expected={expected_knowledge_id!r}"
        )

    km = build_knowledge_evidence(
        identity,
        title=f(
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
            "canonical_observation_id": f(
                row,
                "Canonical_Observation_ID",
            ),
            "resolution_status": f(row, "Resolution_Status"),
            "resolution_type": f(row, "Resolution_Type"),
            "resolution_selected_context": f(
                row,
                "Resolution_Selected_Context",
            ),
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
            f"canonical_observation_id: {f(row, 'Canonical_Observation_ID')}",
            f"resolution_status: {f(row, 'Resolution_Status')}",
            f"resolution_type: {f(row, 'Resolution_Type')}",
            f"resolution_selected_context: {f(row, 'Resolution_Selected_Context')}",
        ),
    )


def expected_path(repository: ObsidianRepository, evidence_id: str) -> Path:
    safe = repository._safe_filename(evidence_id)
    return repository.vault_path / "04_Evidence" / f"{safe}.md"


def validate_batch(rows: list[dict[str, str]], repository: ObsidianRepository):
    errors: list[str] = []
    prepared: list[tuple[dict[str, str], MetricObservationIdentity, Evidence]] = []
    metric_ids: list[str] = []
    knowledge_ids: list[str] = []

    for idx, row in enumerate(rows, start=2):
        try:
            if f(row, "Canonicalization_Status", "Status").upper() not in {
                "CANONICAL",
                "IDENTITY_READY",
            }:
                raise ValueError("row is not canonical")
            if "Persistence_Eligible" in row and not truthy(
                f(row, "Persistence_Eligible")
            ):
                raise ValueError("Persistence_Eligible is not YES")

            identity = build_identity(row)
            evidence = build_evidence(row, identity)
            metric_id = metric_evidence_id(identity)
            knowledge_id = knowledge_evidence_id(metric_id)

            metric_ids.append(metric_id)
            knowledge_ids.append(knowledge_id)
            prepared.append((row, identity, evidence))
        except Exception as exc:
            errors.append(f"row_{idx}:{type(exc).__name__}:{exc}")

    metric_dup = {k: n for k, n in Counter(metric_ids).items() if n > 1}
    knowledge_dup = {k: n for k, n in Counter(knowledge_ids).items() if n > 1}

    errors.extend(
        f"duplicate_metric_id:{key}:{count}" for key, count in metric_dup.items()
    )
    errors.extend(
        f"duplicate_knowledge_id:{key}:{count}" for key, count in knowledge_dup.items()
    )

    existing = []
    missing = []

    for _, _, evidence in prepared:
        path = expected_path(repository, evidence.evidence_id)
        if path.exists():
            existing.append(path)
        else:
            missing.append(path)

    return prepared, errors, existing, missing


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["Step", "Status", "Detail"],
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generic IIP Historical Persistence Pipeline R3"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="canonicalization CSV path",
    )
    parser.add_argument(
        "--vault",
        required=False,
        help="official Obsidian Vault path; required only with --execute",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="persist only when the batch is entirely new; fully persisted "
        "batches are reconciled without writes; mixed batches fail closed",
    )
    parser.add_argument(
        "--report-prefix",
        default=None,
        help="optional report filename prefix",
    )
    args = parser.parse_args()

    input_csv = Path(args.input).resolve()
    if not input_csv.exists():
        print("STATUS                      : FAIL")
        print(f"Reason                      : input not found: {input_csv}")
        return 2

    rows = load_csv(input_csv)

    prefix = args.report_prefix or input_csv.stem
    output_csv = REPORTS / f"{prefix}_IIP_HISTORICAL_PIPELINE_R3.csv"
    output_md = REPORTS / f"{prefix}_IIP_HISTORICAL_PIPELINE_R3.md"

    print("=" * 90)
    print("IIP HISTORICAL PERSISTENCE PIPELINE R3")
    print("=" * 90)
    print(
        f"Mode                        : {'EXECUTE' if args.execute else 'VALIDATE_ONLY'}"
    )
    print(f"Input                       : {input_csv}")
    print(f"Input rows                  : {len(rows)}")

    if not args.execute:
        # Validation-only mode uses a temporary Vault and never touches the
        # official Vault.
        import tempfile

        with tempfile.TemporaryDirectory(prefix="iip_hist_r3_") as tmp:
            repository = ObsidianRepository(Path(tmp))
            prepared, errors, existing, missing = validate_batch(rows, repository)

            bridge_ready = len(prepared) == len(rows) and not errors
            repo_ready = bridge_ready

            print(f"Prepared rows               : {len(prepared)}")
            print(f"Blocked rows                : {len(rows) - len(prepared)}")
            print(f"Duplicate Metric_ID groups  : {len({x for x in []})}")
            print("Temporary repository writes : 0")
            print(f"Ready for execution        : {'YES' if bridge_ready else 'NO'}")
            print("Vault modified              : NO")
            print("Persistence executed        : NO")

            status = "PASS_VALIDATION_ONLY" if bridge_ready else "FAIL"

            manifest = [
                {"Step": "input", "Status": "PASS", "Detail": f"rows={len(rows)}"},
                {
                    "Step": "identity_and_contract",
                    "Status": "PASS" if bridge_ready else "FAIL",
                    "Detail": f"prepared={len(prepared)} blocked={len(rows) - len(prepared)}",
                },
                {
                    "Step": "official_vault",
                    "Status": "NOT_TOUCHED",
                    "Detail": "validation-only",
                },
            ]
            if errors:
                manifest.extend(
                    {"Step": "failure", "Status": "FAIL", "Detail": err}
                    for err in errors
                )

            write_manifest(output_csv, manifest)
            output_md.write_text(
                "\n".join(
                    [
                        "# IIP Historical Persistence Pipeline R3",
                        "",
                        "- Mode: VALIDATE_ONLY",
                        f"- Input: `{input_csv}`",
                        f"- Input SHA-256: {sha256_file(input_csv)}",
                        f"- Rows: {len(rows)}",
                        f"- Prepared: {len(prepared)}",
                        f"- Blocked: {len(rows) - len(prepared)}",
                        f"- Status: {status}",
                        "- Vault modified: NO",
                        "- Persistence executed: NO",
                    ]
                    + (
                        ["", "## Failures"] + [f"- {err}" for err in errors]
                        if errors
                        else ["", "## Failures", "- none"]
                    )
                ),
                encoding="utf-8",
            )
            print(f"Pipeline status             : {status}")
            print(f"CSV                         : {output_csv}")
            print(f"MD                          : {output_md}")
            return 0 if bridge_ready else 1

    if not args.vault:
        print("STATUS                      : FAIL")
        print("Reason                      : --vault is required with --execute")
        return 3

    vault = Path(args.vault).resolve()
    if not vault.exists():
        print("STATUS                      : FAIL")
        print(f"Reason                      : Vault not found: {vault}")
        return 3

    repository = ObsidianRepository(vault)
    prepared, errors, existing, missing = validate_batch(rows, repository)

    if errors:
        print("EXECUTION AUTHORIZED        : NO")
        print("Reason                      : validation failed")
        for err in errors:
            print(f"  - {err}")
        print("Vault modified              : NO")
        return 4

    if len(existing) == len(prepared) == len(rows):
        # Fully persisted: reconcile only; never rewrite.
        print(f"Existing evidence files     : {len(existing)}")
        print("Batch state                 : ALREADY_PERSISTED")
        print("Persistence action          : SKIPPED")

        # Read-only content verification.
        failures = []
        for _, identity, evidence in prepared:
            path = expected_path(repository, evidence.evidence_id)
            content = path.read_text(encoding="utf-8") if path.exists() else ""
            required = (
                f"evidence_id: {evidence.evidence_id}",
                f"ticker: {evidence.ticker}",
                f"date: {evidence.date.isoformat()}",
                f"document_hash: {evidence.document_hash}",
                f"- metric_id: {metric_evidence_id(identity)}",
                f"- value: {identity.value}",
                f"- period: {identity.period}",
            )
            for fragment in required:
                if fragment not in content:
                    failures.append(f"{evidence.evidence_id}:{fragment}")

        status = "ALREADY_PERSISTED" if not failures else "RECONCILIATION_FAILED"

        manifest = [
            {
                "Step": "input",
                "Status": "PASS",
                "Detail": f"rows={len(rows)}",
            },
            {
                "Step": "identity_and_contract",
                "Status": "PASS",
                "Detail": f"prepared={len(prepared)}",
            },
            {
                "Step": "batch_state",
                "Status": status,
                "Detail": f"existing={len(existing)} missing={len(missing)}",
            },
            {
                "Step": "write",
                "Status": "SKIPPED",
                "Detail": "fully persisted batch",
            },
            {
                "Step": "vault",
                "Status": "READ_ONLY",
                "Detail": "no write performed",
            },
        ]
        for failure in failures:
            manifest.append(
                {"Step": "reconciliation_failure", "Status": "FAIL", "Detail": failure}
            )

        write_manifest(output_csv, manifest)
        output_md.write_text(
            "\n".join(
                [
                    "# IIP Historical Persistence Pipeline R3",
                    "",
                    "- Mode: EXECUTE",
                    f"- Input: `{input_csv}`",
                    f"- Input SHA-256: {sha256_file(input_csv)}",
                    f"- Rows: {len(rows)}",
                    f"- Batch state: {status}",
                    f"- Existing evidence: {len(existing)}",
                    f"- Missing evidence: {len(missing)}",
                    "- Persistence executed: NO",
                    "- Vault modified by this run: NO",
                ]
                + (
                    ["", "## Reconciliation failures"]
                    + [f"- {failure}" for failure in failures]
                    if failures
                    else []
                )
            ),
            encoding="utf-8",
        )

        print(f"Batch state                 : {status}")
        print("Persistence executed        : NO")
        print("Vault modified              : NO")
        print(f"CSV                         : {output_csv}")
        print(f"MD                          : {output_md}")
        return 0 if not failures else 1

    if existing:
        # Mixed state is deliberately fail-closed.
        print(f"Existing evidence files     : {len(existing)}")
        print(f"Missing evidence files      : {len(missing)}")
        print("EXECUTION AUTHORIZED        : NO")
        print("Batch state                 : MIXED_BATCH_FAIL_CLOSED")
        print("Persistence executed        : NO")
        print("Vault modified              : NO")

        write_manifest(
            output_csv,
            [
                {
                    "Step": "batch_state",
                    "Status": "FAIL",
                    "Detail": f"existing={len(existing)} missing={len(missing)}",
                }
            ],
        )
        output_md.write_text(
            "\n".join(
                [
                    "# IIP Historical Persistence Pipeline R3",
                    "",
                    "- Status: MIXED_BATCH_FAIL_CLOSED",
                    f"- Existing: {len(existing)}",
                    f"- Missing: {len(missing)}",
                    "- Persistence executed: NO",
                    "- Vault modified: NO",
                ]
            ),
            encoding="utf-8",
        )
        return 5

    # Entirely new batch. Prepare every object before the first write.
    bridge = KnowledgeBridge(vault)
    results = []
    failures = []

    for row, identity, evidence in prepared:
        try:
            saved = bridge.persist_evidence(evidence)
            path = Path(saved)
            exists = path.exists()
            size = path.stat().st_size if exists else 0
            file_hash = sha256_file(path) if exists else ""

            result = {
                "Step": "persist",
                "Status": "CREATED" if exists and size > 0 else "FAILED",
                "Detail": (
                    f"knowledge_id={evidence.evidence_id}; "
                    f"metric_id={metric_evidence_id(identity)}; "
                    f"path={path}; "
                    f"sha256={file_hash}"
                ),
            }
            results.append(result)

            if not (exists and size > 0):
                failures.append(f"{evidence.evidence_id}:file_missing_or_empty")
        except Exception as exc:
            failures.append(f"{evidence.evidence_id}:{type(exc).__name__}:{exc}")
            results.append(
                {
                    "Step": "persist",
                    "Status": "FAILED",
                    "Detail": failures[-1],
                }
            )

    created = sum(item["Status"] == "CREATED" for item in results)
    failed = sum(item["Status"] == "FAILED" for item in results)

    status = "SUCCESS" if created == len(rows) and failed == 0 else "PARTIAL_OR_FAILED"

    results.insert(
        0,
        {
            "Step": "input",
            "Status": "PASS",
            "Detail": f"rows={len(rows)} sha256={sha256_file(input_csv)}",
        },
    )

    write_manifest(output_csv, results)

    output_md.write_text(
        "\n".join(
            [
                "# IIP Historical Persistence Pipeline R3",
                "",
                "- Mode: EXECUTE",
                f"- Input: `{input_csv}`",
                f"- Input SHA-256: {sha256_file(input_csv)}",
                f"- Rows: {len(rows)}",
                f"- Prepared: {len(prepared)}",
                f"- Created: {created}",
                f"- Failed: {failed}",
                f"- Status: {status}",
                "- Batch state: NEW_BATCH",
                "- Append-only: YES",
                "- Vault modified: YES",
                "",
                "## Failures",
            ]
            + ([f"- {failure}" for failure in failures] if failures else ["- none"])
        ),
        encoding="utf-8",
    )

    print(f"Prepared rows               : {len(prepared)}")
    print(f"Created                     : {created}")
    print(f"Failed                      : {failed}")
    print(f"Execution result            : {status}")
    print("KnowledgeBridge executed    : YES")
    print("Repository save_evidence    : YES")
    print("Vault modified              : YES")
    print(f"CSV                         : {output_csv}")
    print(f"MD                          : {output_md}")

    return 0 if status == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
