from __future__ import annotations

import csv
import hashlib
import sys
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------------------
# Reusable IIP historical-persistence preflight.
#
# This runner does NOT write to the Vault.
# It validates a canonicalization CSV against the repository's official
# MetricObservationIdentity + metric_persistence identity functions and,
# optionally, checks previously generated bridge/repository dry-run reports.
#
# Configure only INPUT_CSV. The script derives all other output paths.
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "reports"

# Change this one line for the next asset/batch.
INPUT_CSV = REPORTS / "PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R4.csv"

OUTPUT_CSV = REPORTS / "IIP_HISTORICAL_PERSISTENCE_PREFLIGHT_R1.csv"
OUTPUT_MD = REPORTS / "IIP_HISTORICAL_PERSISTENCE_PREFLIGHT_R1.md"

SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from iip.intelligence.metric_identity import MetricObservationIdentity
from iip.intelligence.metric_persistence import (
    knowledge_evidence_id,
    metric_evidence_id,
)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def f(row: dict[str, str], name: str) -> str:
    return str(row.get(name, "") or "").strip()


def truthy(value: str) -> bool:
    return value.strip().upper() in {"YES", "TRUE", "1", "SIM"}


def build_identity(row: dict[str, str]) -> MetricObservationIdentity:
    ticker = (
        f(row, "Derived_Canonical_Ticker")
        or f(row, "Canonical_Ticker")
        or f(row, "Ticker")
    )
    metric = f(row, "Metric")
    value = f(row, "Resolved_Value") or f(row, "Value")
    unit = f(row, "Resolved_Unit") or f(row, "Unit") or f(row, "Original_Unit")
    scale = f(row, "Scale") or f(row, "Resolved_Scale")
    period = f(row, "Resolved_Period") or f(row, "Period")
    dimension = f(row, "Semantic_Dimension") or f(row, "Resolved_Semantic_Dimension")
    document_hash = (
        f(row, "Document_Hash")
        or f(row, "SHA256")
        or f(row, "Evidence_SHA256")
        or f(row, "SHA")
    )
    document_id = f(row, "Document_ID") or f(row, "Knowledge_Document_ID")
    source_locator = (
        f(row, "Source_Locator")
        or f(row, "SourceLocator")
        or f(row, "Resolution_Selected_Context")
    )
    lineage = f(row, "Lineage") or f(row, "Resolved_Lineage")
    original_ticker = f(row, "Original_Ticker") or f(row, "Original_Identity") or ticker

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


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    print("=" * 90)
    print("IIP HISTORICAL PERSISTENCE PREFLIGHT R1")
    print("=" * 90)

    if not INPUT_CSV.exists():
        print("STATUS                      : FAIL")
        print(f"Reason                      : input not found: {INPUT_CSV}")
        return 2

    rows = load_csv(INPUT_CSV)
    errors: list[str] = []
    output: list[dict[str, str]] = []

    # Require the canonicalization contract fields needed for this generic
    # preflight. Do not silently invent a schema.
    required_schema = {
        "Metric",
        "Value",
        "Resolved_Period",
        "Derived_Canonical_Ticker",
        "Resolved_Unit",
        "Scale",
        "Canonicalization_Status",
        "Persistence_Eligible",
    }
    missing_schema = required_schema.difference(rows[0].keys() if rows else set())
    for column in sorted(missing_schema):
        errors.append(f"missing_input_column:{column}")

    metric_ids: list[str] = []
    knowledge_ids: list[str] = []
    observation_keys: list[str] = []

    if not missing_schema:
        for idx, row in enumerate(rows, start=2):
            row_errors: list[str] = []

            if f(row, "Canonicalization_Status") != "CANONICAL":
                row_errors.append("not_canonical")

            if not truthy(f(row, "Persistence_Eligible")):
                row_errors.append("persistence_not_eligible")

            try:
                identity = build_identity(row)
                metric_id = metric_evidence_id(identity)
                knowledge_id = knowledge_evidence_id(metric_id)
                observation_key = identity.observation_key

                expected_legacy_observation = f(row, "Canonical_Observation_ID")
                if expected_legacy_observation:
                    # Canonical_Observation_ID belongs to the upstream
                    # canonicalization layer; it is preserved but is not used
                    # as the final persistence ID.
                    pass

                metric_ids.append(metric_id)
                knowledge_ids.append(knowledge_id)
                observation_keys.append(observation_key)

                output.append(
                    {
                        "Source_Row": str(idx),
                        "Ticker": identity.canonical_ticker,
                        "Metric": identity.metric_name,
                        "Value": identity.value,
                        "Period": identity.period,
                        "Semantic_Dimension": identity.semantic_dimension or "",
                        "Metric_ID": metric_id,
                        "Knowledge_Evidence_ID": knowledge_id,
                        "Observation_Key": observation_key,
                        "Document_Hash": identity.document_hash,
                        "Status": "PASS" if not row_errors else "BLOCKED",
                        "Failure_Details": ",".join(row_errors),
                    }
                )
            except Exception as exc:
                row_errors.append(f"identity_error:{type(exc).__name__}:{exc}")
                output.append(
                    {
                        "Source_Row": str(idx),
                        "Ticker": f(row, "Derived_Canonical_Ticker"),
                        "Metric": f(row, "Metric"),
                        "Value": f(row, "Resolved_Value") or f(row, "Value"),
                        "Period": f(row, "Resolved_Period") or f(row, "Period"),
                        "Semantic_Dimension": f(row, "Semantic_Dimension"),
                        "Metric_ID": "",
                        "Knowledge_Evidence_ID": "",
                        "Observation_Key": "",
                        "Document_Hash": f(row, "Document_Hash") or f(row, "SHA256"),
                        "Status": "BLOCKED",
                        "Failure_Details": ",".join(row_errors),
                    }
                )
                errors.extend(f"row_{idx}:{item}" for item in row_errors)

    metric_duplicates = {
        key: count for key, count in Counter(metric_ids).items() if count > 1
    }
    knowledge_duplicates = {
        key: count for key, count in Counter(knowledge_ids).items() if count > 1
    }
    observation_duplicates = {
        key: count for key, count in Counter(observation_keys).items() if count > 1
    }

    for key, count in metric_duplicates.items():
        errors.append(f"duplicate_metric_id:{key}:{count}")
    for key, count in knowledge_duplicates.items():
        errors.append(f"duplicate_knowledge_id:{key}:{count}")

    # Distinct values under the same observation key are a collision.
    observation_values: dict[str, set[str]] = {}
    for row in output:
        key = row["Observation_Key"]
        if key:
            observation_values.setdefault(key, set()).add(row["Value"])

    for key, values in observation_values.items():
        if len(values) > 1:
            errors.append(
                f"observation_value_collision:{key}:{','.join(sorted(values))}"
            )

    passed = sum(row["Status"] == "PASS" for row in output)
    blocked = len(output) - passed

    ready = (
        bool(rows)
        and not missing_schema
        and len(output) == len(rows)
        and passed == len(rows)
        and blocked == 0
        and len(metric_ids) == len(set(metric_ids))
        and len(knowledge_ids) == len(set(knowledge_ids))
        and not errors
    )

    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        fields = (
            list(output[0].keys())
            if output
            else [
                "Source_Row",
                "Ticker",
                "Metric",
                "Value",
                "Period",
                "Semantic_Dimension",
                "Metric_ID",
                "Knowledge_Evidence_ID",
                "Observation_Key",
                "Document_Hash",
                "Status",
                "Failure_Details",
            ]
        )
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output)

    lines = [
        "# IIP Historical Persistence Preflight R1",
        "",
        "## Safety",
        "- Mode: READ-ONLY",
        "- Vault modified: NO",
        "- Persistence executed: NO",
        "",
        "## Input",
        f"- File: `{INPUT_CSV.name}`",
        f"- Rows: {len(rows)}",
        f"- Input SHA-256: {sha256_file(INPUT_CSV)}",
        "",
        "## Results",
        f"- Passed rows: {passed}",
        f"- Blocked rows: {blocked}",
        f"- Unique Metric_ID: {len(set(metric_ids))}",
        f"- Unique Knowledge_Evidence_ID: {len(set(knowledge_ids))}",
        f"- Duplicate Metric_ID groups: {len(metric_duplicates)}",
        f"- Duplicate Knowledge_Evidence_ID groups: {len(knowledge_duplicates)}",
        f"- Duplicate Observation_Key groups: {len(observation_duplicates)}",
        f"- Ready for next persistence gate: {'YES' if ready else 'NO'}",
        "",
        "## Failures",
    ]

    if errors:
        lines.extend(f"- {error}" for error in errors)
    else:
        lines.append("- none")

    lines += [
        "",
        "## Contract",
        "- Final Metric_ID comes only from `metric_evidence_id(MetricObservationIdentity)`.",
        "- Final Knowledge_Evidence_ID comes only from `knowledge_evidence_id(Metric_ID)`.",
        "- `Canonical_Observation_ID` remains upstream provenance and is not substituted for the persistence ID.",
        "",
        "This preflight does not write to Obsidian.",
    ]
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"Input rows                  : {len(rows)}")
    print(f"Passed rows                 : {passed}")
    print(f"Blocked rows                : {blocked}")
    print(f"Unique Metric_ID            : {len(set(metric_ids))}")
    print(f"Unique Knowledge IDs        : {len(set(knowledge_ids))}")
    print(f"Duplicate Metric_ID groups  : {len(metric_duplicates)}")
    print(f"Duplicate Knowledge groups  : {len(knowledge_duplicates)}")
    print(f"Ready for next gate         : {'YES' if ready else 'NO'}")
    print("Vault modified              : NO")
    print("Persistence executed        : NO")
    print(f"CSV                         : {OUTPUT_CSV}")
    print(f"MD                          : {OUTPUT_MD}")

    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
