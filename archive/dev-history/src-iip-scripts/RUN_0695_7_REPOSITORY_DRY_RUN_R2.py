from __future__ import annotations

import csv
import inspect
import sys
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "reports"

INPUT_CSV = REPORTS / "PCIP11_0695_7_KNOWLEDGE_BRIDGE_DRY_RUN_R1.csv"
OUTPUT_CSV = REPORTS / "PCIP11_0695_7_REPOSITORY_DRY_RUN_R2.csv"
OUTPUT_MD = REPORTS / "PCIP11_0695_7_REPOSITORY_DRY_RUN_R2.md"

SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from iip.knowledge.models import Evidence
from iip.knowledge.repository import ObsidianRepository


def pick(row: dict[str, str], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def build_evidence(row: dict[str, str]) -> Evidence:
    period = pick(row, "Period")
    if not period or len(period) != 7 or period[4] != "-":
        raise ValueError(f"invalid period: {period!r}")

    year, month = period.split("-")
    evidence_id = pick(row, "Knowledge_Evidence_ID")
    if not evidence_id:
        raise ValueError("missing Knowledge_Evidence_ID")

    ticker = pick(row, "Ticker")
    if not ticker:
        raise ValueError("missing ticker")

    document_hash = pick(row, "Document_Hash")
    if not document_hash:
        raise ValueError("missing document hash")

    title = pick(row, "Title") or pick(
        row,
        "Source_FileName",
        "Source_FileNames",
    )
    if not title:
        title = f"{ticker} {period} historical metric evidence"

    # Evidence.relevant_facts is rendered by the repository as one
    # bullet per iterable item. Keep the traceable facts compact and
    # deterministic.
    relevant_facts = (
        f"metric_id: {pick(row, 'Metric_ID')}",
        f"metric: {pick(row, 'Metric')}",
        f"value: {pick(row, 'Value')}",
        f"unit: {pick(row, 'Unit')}",
        f"scale: {pick(row, 'Scale')}",
        f"period: {period}",
        f"semantic_dimension: {pick(row, 'Semantic_Dimension')}",
        f"document_id: {pick(row, 'Document_ID')}",
        f"document_hash: {document_hash}",
        f"source_locator: {pick(row, 'Source_Locator')}",
        f"lineage: {pick(row, 'Lineage')}",
        f"canonical_observation_id: {pick(row, 'Canonical_Observation_ID')}",
    )

    return Evidence(
        evidence_id=evidence_id,
        ticker=ticker,
        date=date(int(year), int(month), 1),
        source_type="historical_metric",
        source_url=None,
        title=title,
        document_hash=document_hash,
        relevant_facts=relevant_facts,
    )


def repository_for(path: Path) -> ObsidianRepository:
    signature = inspect.signature(ObsidianRepository)
    if "vault_path" in signature.parameters:
        return ObsidianRepository(vault_path=path)
    raise RuntimeError(f"Unsupported ObsidianRepository constructor: {signature}")


def main() -> int:
    if not INPUT_CSV.exists():
        print(f"ERROR: input not found: {INPUT_CSV}")
        return 2

    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    output: list[dict[str, str]] = []
    failures = Counter()

    with tempfile.TemporaryDirectory(prefix="iip_0695_7_repo_dryrun_r2_") as tmp:
        temp_vault = Path(tmp)
        repository = repository_for(temp_vault)

        for idx, row in enumerate(rows, start=2):
            try:
                evidence = build_evidence(row)

                # Use the repository's actual filename sanitization logic.
                safe_name = repository._safe_filename(evidence.evidence_id)
                expected_path = temp_vault / "04_Evidence" / f"{safe_name}.md"

                repository.save_evidence(evidence)

                exists = expected_path.exists()
                nonempty = exists and expected_path.stat().st_size > 0

                content = expected_path.read_text(encoding="utf-8") if exists else ""

                required_fragments = (
                    "---",
                    "type: evidence",
                    f"evidence_id: {evidence.evidence_id}",
                    f"ticker: {evidence.ticker}",
                    f"date: {evidence.date.isoformat()}",
                    f"source_type: {evidence.source_type}",
                    f"document_hash: {evidence.document_hash}",
                    "relevant_facts:",
                    f"- metric_id: {evidence.relevant_facts[0].split(': ', 1)[1]}",
                    f"- metric: {evidence.relevant_facts[1].split(': ', 1)[1]}",
                    f"- value: {evidence.relevant_facts[2].split(': ', 1)[1]}",
                    f"- semantic_dimension: {evidence.relevant_facts[6].split(': ', 1)[1]}",
                    f"- source_locator: {evidence.relevant_facts[9].split(': ', 1)[1]}",
                    f"- lineage: {evidence.relevant_facts[10].split(': ', 1)[1]}",
                    "---",
                )

                content_ok = (
                    exists
                    and nonempty
                    and all(fragment in content for fragment in required_fragments)
                )

                try:
                    repository.save_evidence(evidence)
                    append_status = "FAIL_NO_FILEEXISTS_ERROR"
                    failures["append_only_violation"] += 1
                except FileExistsError:
                    append_status = "PASS_FILEEXISTS_ERROR"
                except Exception as exc:
                    append_status = f"UNEXPECTED:{type(exc).__name__}:{exc}"
                    failures["unexpected_second_write_error"] += 1

                status = (
                    "READY"
                    if content_ok and append_status == "PASS_FILEEXISTS_ERROR"
                    else "BLOCKED"
                )

                if not content_ok:
                    failures["content_validation_failure"] += 1

                output.append(
                    {
                        "Source_Row": str(idx),
                        "Knowledge_Evidence_ID": evidence.evidence_id,
                        "Metric_ID": evidence.relevant_facts[0].split(": ", 1)[1],
                        "Ticker": evidence.ticker,
                        "Date": evidence.date.isoformat(),
                        "Metric": evidence.relevant_facts[1].split(": ", 1)[1],
                        "Value": evidence.relevant_facts[2].split(": ", 1)[1],
                        "Semantic_Dimension": evidence.relevant_facts[6].split(": ", 1)[
                            1
                        ],
                        "Document_Hash": evidence.document_hash,
                        "Expected_Path": str(expected_path),
                        "First_Write": "PASS" if content_ok else "FAIL",
                        "Append_Only": append_status,
                        "Mapping_Status": status,
                    }
                )

            except Exception as exc:
                failures[f"row_exception:{type(exc).__name__}:{exc}"] += 1
                output.append(
                    {
                        "Source_Row": str(idx),
                        "Knowledge_Evidence_ID": pick(row, "Knowledge_Evidence_ID"),
                        "Metric_ID": pick(row, "Metric_ID"),
                        "Ticker": pick(row, "Ticker"),
                        "Date": pick(row, "Date"),
                        "Metric": pick(row, "Metric"),
                        "Value": pick(row, "Value"),
                        "Semantic_Dimension": pick(row, "Semantic_Dimension"),
                        "Document_Hash": pick(row, "Document_Hash"),
                        "Expected_Path": "",
                        "First_Write": "FAIL",
                        "Append_Only": "",
                        "Mapping_Status": "BLOCKED",
                    }
                )

        ready = sum(row["Mapping_Status"] == "READY" for row in output)
        blocked = len(output) - ready

        unique_ids = {
            row["Knowledge_Evidence_ID"]
            for row in output
            if row["Knowledge_Evidence_ID"]
        }
        duplicate_ids = len(output) - len(unique_ids)

        append_pass = sum(
            row["Append_Only"] == "PASS_FILEEXISTS_ERROR" for row in output
        )

        release_ready = (
            len(output) == len(rows)
            and ready == len(rows)
            and blocked == 0
            and duplicate_ids == 0
            and append_pass == len(rows)
            and not failures
        )

        fieldnames = list(output[0].keys()) if output else []

        with OUTPUT_CSV.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=fieldnames,
            )
            writer.writeheader()
            writer.writerows(output)

        lines = [
            "# PCIP11 — 0695.7 Repository Dry-Run R2",
            "",
            "## Safety",
            "- Official Vault touched: NO",
            "- Official persistence executed: NO",
            "- Test repository: temporary directory only",
            "",
            "## Results",
            f"- Input rows: {len(rows)}",
            f"- Repository writes verified: {ready}",
            f"- Blocked rows: {blocked}",
            f"- Duplicate Knowledge IDs: {duplicate_ids}",
            f"- Append-only checks passed: {append_pass}",
            f"- Release ready: {'YES' if release_ready else 'NO'}",
            "",
            "## Validation method",
            "- Filename checked using `ObsidianRepository._safe_filename`.",
            "- Markdown checked against the exact serialization produced by `save_evidence()`.",
            "- Second write checked for `FileExistsError`.",
            "",
            "## Failures",
        ]

        if failures:
            lines.extend(f"- {key}: {count}" for key, count in sorted(failures.items()))
        else:
            lines.append("- none")

        lines += [
            "",
            "This dry-run uses the real `ObsidianRepository.save_evidence()` "
            "against a temporary Vault only.",
        ]

        OUTPUT_MD.write_text(
            "\n".join(lines),
            encoding="utf-8",
        )

    print("=" * 90)
    print("0695.7 REPOSITORY DRY-RUN R2")
    print("=" * 90)
    print(f"Input rows                    : {len(rows)}")
    print(f"Repository writes verified   : {ready}")
    print(f"Blocked rows                 : {blocked}")
    print(f"Duplicate Knowledge IDs      : {duplicate_ids}")
    print(f"Append-only checks passed    : {append_pass}")
    print(f"Release ready                : {'YES' if release_ready else 'NO'}")
    print("Official Vault touched       : NO")
    print("Official persistence executed: NO")
    print(f"CSV                          : {OUTPUT_CSV}")
    print(f"MD                           : {OUTPUT_MD}")

    return 0 if release_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
