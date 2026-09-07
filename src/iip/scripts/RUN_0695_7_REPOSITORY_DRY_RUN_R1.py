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
OUTPUT_CSV = REPORTS / "PCIP11_0695_7_REPOSITORY_DRY_RUN_R1.csv"
OUTPUT_MD = REPORTS / "PCIP11_0695_7_REPOSITORY_DRY_RUN_R1.md"

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

    title = pick(row, "Title") or pick(row, "Source_FileName")
    if not title:
        title = f"{ticker} {period} historical metric evidence"

    relevant_facts = {
        "metric_id": pick(row, "Metric_ID"),
        "metric": pick(row, "Metric"),
        "value": pick(row, "Value"),
        "unit": pick(row, "Unit"),
        "scale": pick(row, "Scale"),
        "period": period,
        "semantic_dimension": pick(row, "Semantic_Dimension"),
        "document_id": pick(row, "Document_ID"),
        "document_hash": document_hash,
        "source_locator": pick(row, "Source_Locator"),
        "lineage": pick(row, "Lineage"),
        "canonical_observation_id": pick(row, "Canonical_Observation_ID"),
    }

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
    sig = inspect.signature(ObsidianRepository)
    params = list(sig.parameters.values())

    # Prefer the conventional vault_path/name parameter; otherwise use
    # the first required positional/keyword parameter.
    if "vault_path" in sig.parameters:
        return ObsidianRepository(vault_path=path)
    if "vault" in sig.parameters:
        return ObsidianRepository(vault=path)
    if params:
        first = params[0]
        if first.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ):
            return ObsidianRepository(path)

    raise RuntimeError(f"Unsupported ObsidianRepository constructor: {sig}")


def main() -> int:
    if not INPUT_CSV.exists():
        print(f"ERROR: input not found: {INPUT_CSV}")
        return 2

    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    result_rows: list[dict[str, str]] = []
    failures = Counter()
    created_files: list[Path] = []
    second_write_checks: list[str] = []

    with tempfile.TemporaryDirectory(prefix="iip_0695_7_repo_dryrun_") as tmp:
        temp_vault = Path(tmp)

        try:
            repository = repository_for(temp_vault)
        except Exception as exc:
            print(f"ERROR: could not initialize ObsidianRepository: {exc}")
            return 3

        for idx, row in enumerate(rows, start=2):
            try:
                evidence = build_evidence(row)

                repository.save_evidence(evidence)

                expected_path = (
                    temp_vault / "04_Evidence" / f"{evidence.evidence_id}.md"
                )

                created_exists = expected_path.exists()
                created_nonempty = created_exists and expected_path.stat().st_size > 0

                content = (
                    expected_path.read_text(encoding="utf-8") if created_exists else ""
                )

                frontmatter_checks = {
                    "type": "type: evidence" in content,
                    "evidence_id": f"evidence_id: {evidence.evidence_id}" in content,
                    "ticker": f"ticker: {evidence.ticker}" in content,
                    "document_hash": (
                        f"document_hash: {evidence.document_hash}" in content
                    ),
                }

                first_write_ok = (
                    created_exists
                    and created_nonempty
                    and all(frontmatter_checks.values())
                )

                # Verify append-only behavior: the same evidence must not
                # overwrite an existing file.
                second_write_status = "NOT_TESTED"
                try:
                    repository.save_evidence(evidence)
                    second_write_status = "FAILED_NO_FILEEXISTS_ERROR"
                    failures["append_only_violation"] += 1
                except FileExistsError:
                    second_write_status = "PASS_FILEEXISTS_ERROR"
                except Exception as exc:
                    second_write_status = f"UNEXPECTED:{type(exc).__name__}:{exc}"
                    failures["unexpected_second_write_error"] += 1

                if first_write_ok:
                    status = "READY"
                else:
                    status = "BLOCKED"
                    failures["frontmatter_or_write_failure"] += 1

                if second_write_status != "PASS_FILEEXISTS_ERROR":
                    status = "BLOCKED"

                result_rows.append(
                    {
                        "Source_Row": str(idx),
                        "Knowledge_Evidence_ID": evidence.evidence_id,
                        "Metric_ID": evidence.relevant_facts.get("metric_id", ""),
                        "Ticker": evidence.ticker,
                        "Date": evidence.date.isoformat(),
                        "Metric": evidence.relevant_facts.get("metric", ""),
                        "Value": evidence.relevant_facts.get("value", ""),
                        "Semantic_Dimension": evidence.relevant_facts.get(
                            "semantic_dimension", ""
                        ),
                        "Document_Hash": evidence.document_hash,
                        "Expected_Path": str(expected_path),
                        "First_Write": ("PASS" if first_write_ok else "FAIL"),
                        "Append_Only": second_write_status,
                        "Mapping_Status": status,
                    }
                )

                second_write_checks.append(second_write_status)
                if created_exists:
                    created_files.append(expected_path)

            except Exception as exc:
                failures[f"row_exception:{type(exc).__name__}:{exc}"] += 1
                result_rows.append(
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

        ready = sum(row["Mapping_Status"] == "READY" for row in result_rows)
        blocked = len(result_rows) - ready

        unique_ids = {
            row["Knowledge_Evidence_ID"]
            for row in result_rows
            if row["Knowledge_Evidence_ID"]
        }

        duplicate_rows = len(result_rows) - len(unique_ids)

        append_only_pass = sum(
            value == "PASS_FILEEXISTS_ERROR" for value in second_write_checks
        )

        release_ready = (
            len(result_rows) == len(rows)
            and ready == len(rows)
            and blocked == 0
            and duplicate_rows == 0
            and append_only_pass == len(rows)
            and not failures
        )

        fieldnames = list(result_rows[0].keys()) if result_rows else []
        with OUTPUT_CSV.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(result_rows)

        md = [
            "# PCIP11 — 0695.7 Repository Dry-Run R1",
            "",
            "## Safety",
            "- Official Vault touched: NO",
            "- Official `ObsidianRepository` persistence target: NO",
            "- Test repository: temporary directory only",
            "",
            "## Results",
            f"- Input rows: {len(rows)}",
            f"- Repository writes verified: {ready}",
            f"- Blocked rows: {blocked}",
            f"- Duplicate Knowledge IDs: {duplicate_rows}",
            f"- Append-only checks passed: {append_only_pass}",
            f"- Release ready: {'YES' if release_ready else 'NO'}",
            "",
            "## Constructor",
            f"- ObsidianRepository signature: {inspect.signature(ObsidianRepository)}",
            "",
            "## Failures",
        ]

        if failures:
            md.extend(f"- {key}: {count}" for key, count in sorted(failures.items()))
        else:
            md.append("- none")

        md += [
            "",
            "This dry-run uses the real `ObsidianRepository.save_evidence()` "
            "against a temporary Vault and does not touch the official Vault.",
        ]

        OUTPUT_MD.write_text("\n".join(md), encoding="utf-8")

    print("=" * 90)
    print("0695.7 REPOSITORY DRY-RUN R1")
    print("=" * 90)
    print(f"Input rows                    : {len(rows)}")
    print(f"Repository writes verified   : {ready}")
    print(f"Blocked rows                 : {blocked}")
    print(f"Duplicate Knowledge IDs      : {duplicate_rows}")
    print(f"Append-only checks passed    : {append_only_pass}")
    print(f"Release ready                : {'YES' if release_ready else 'NO'}")
    print("Official Vault touched       : NO")
    print("Official persistence executed: NO")
    print(f"CSV                          : {OUTPUT_CSV}")
    print(f"MD                           : {OUTPUT_MD}")

    return 0 if release_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
