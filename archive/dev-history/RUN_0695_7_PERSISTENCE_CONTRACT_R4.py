from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"

INPUT_CSV = REPORTS / "PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R4.csv"
OUTPUT_CSV = REPORTS / "PCIP11_0695_7_PERSISTENCE_CONTRACT_R4.csv"
OUTPUT_MD = REPORTS / "PCIP11_0695_7_PERSISTENCE_CONTRACT_R4.md"

# Ensure local package imports work when this script is run directly.
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from iip.intelligence.metric_identity import MetricObservationIdentity
from iip.intelligence.metric_persistence import (
    metric_evidence_id,
    knowledge_evidence_id,
)


def pick(row: dict[str, str], *names: str, default: str = "") -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def normalize_status(row: dict[str, str]) -> str:
    return pick(
        row,
        "Canonicalization_Status",
        "Status",
        "Resolved_Status",
        default="",
    ).upper()


def truthy(value: str) -> bool:
    return str(value).strip().upper() in {"YES", "TRUE", "1", "SIM"}


def make_identity(row: dict[str, str]) -> MetricObservationIdentity:
    ticker = pick(
        row,
        "Canonical_Ticker",
        "Resolved_Ticker",
        "Ticker",
        "CanonicalTicker",
        "ResolvedTicker",
    )
    original_ticker = pick(
        row,
        "Original_Ticker",
        "OriginalTicker",
        default=ticker,
    )
    metric_name = pick(
        row,
        "Metric",
        "Metric_Name",
        "metric_name",
    )
    value = pick(
        row,
        "Value_Parsed",
        "Resolved_Value",
        "Selected_Value",
        "Value",
    )
    unit = pick(
        row,
        "Resolved_Unit",
        "Unit",
        "Original_Unit",
        default="",
    ) or None
    scale = pick(
        row,
        "Scale",
        "Resolved_Scale",
        default="",
    ) or None
    period = pick(
        row,
        "Resolved_Period",
        "Period",
        "period",
    )
    semantic_dimension = pick(
        row,
        "Semantic_Dimension",
        "Resolved_Semantic_Dimension",
        "Dimension",
        default="",
    ) or None
    document_hash = pick(
        row,
        "Document_Hash",
        "Evidence_SHA256",
        "SHA256",
        "SHA",
        "DocumentHash",
    )
    document_id = pick(
        row,
        "Document_ID",
        "Knowledge_Document_ID",
        "DocumentId",
        default="",
    ) or None
    source_locator = pick(
        row,
        "Source_Locator",
        "SourceLocator",
        "Locator",
        "Selected_Context",
        "Resolved_Context",
        default="",
    ) or None
    lineage = pick(
        row,
        "Lineage",
        "Resolved_Lineage",
        default="",
    ) or None

    missing = []
    for label, value_ in (
        ("ticker", ticker),
        ("metric", metric_name),
        ("value", value),
        ("period", period),
        ("document_hash", document_hash),
    ):
        if not value_:
            missing.append(label)

    if missing:
        raise ValueError(f"missing required identity fields: {', '.join(missing)}")

    return MetricObservationIdentity(
        canonical_ticker=ticker,
        original_ticker=original_ticker,
        metric_name=metric_name,
        value=value,
        unit=unit,
        scale=scale,
        period=period,
        semantic_dimension=semantic_dimension,
        document_hash=document_hash,
        document_id=document_id,
        source_locator=source_locator,
        lineage=lineage,
    )


def main() -> int:
    if not INPUT_CSV.exists():
        print(f"ERROR: input not found: {INPUT_CSV}")
        return 2

    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    records = []
    blocked_reasons = Counter()

    for idx, row in enumerate(rows, start=2):
        status = normalize_status(row)
        eligible = truthy(
            pick(row, "Persistence_Eligible", "Eligible", default="")
        )

        if status != "CANONICAL":
            blocked_reasons[f"non_canonical:{status or 'EMPTY'}"] += 1
            continue

        if not eligible:
            blocked_reasons["persistence_not_eligible"] += 1
            continue

        try:
            identity = make_identity(row)
        except Exception as exc:
            blocked_reasons[f"identity_error:{exc}"] += 1
            continue

        metric_id = metric_evidence_id(identity)
        knowledge_id = knowledge_evidence_id(metric_id)

        records.append(
            {
                "Source_Row": str(idx),
                "Observation_Key": identity.observation_key,
                "Metric_ID": metric_id,
                "Knowledge_Evidence_ID": knowledge_id,
                "Ticker": identity.canonical_ticker,
                "Original_Ticker": identity.original_ticker or "",
                "Metric": identity.metric_name,
                "Value": identity.value,
                "Unit": identity.unit or "",
                "Scale": identity.scale or "",
                "Period": identity.period,
                "Semantic_Dimension": identity.semantic_dimension or "",
                "Document_ID": identity.document_id or "",
                "Document_Hash": identity.document_hash,
                "Source_Locator": identity.source_locator or "",
                "Lineage": identity.lineage or "",
                "Status": "IDENTITY_READY",
                "Classification": "CANONICAL",
            }
        )

    metric_groups = defaultdict(list)
    knowledge_groups = defaultdict(list)
    observation_groups = defaultdict(list)

    for rec in records:
        metric_groups[rec["Metric_ID"]].append(rec)
        knowledge_groups[rec["Knowledge_Evidence_ID"]].append(rec)
        observation_groups[rec["Observation_Key"]].append(rec)

    metric_duplicates = {
        k: v for k, v in metric_groups.items() if len(v) > 1
    }
    knowledge_duplicates = {
        k: v for k, v in knowledge_groups.items() if len(v) > 1
    }
    observation_collisions = {}

    for key, group in observation_groups.items():
        values = {item["Value"] for item in group}
        dimensions = {item["Semantic_Dimension"] for item in group}
        if len(values) > 1 or len(dimensions) > 1:
            observation_collisions[key] = group

    for rec in records:
        issues = []
        if not rec["Ticker"]:
            issues.append("missing_ticker")
        if not rec["Metric"]:
            issues.append("missing_metric")
        if not rec["Value"]:
            issues.append("missing_value")
        if not rec["Period"]:
            issues.append("missing_period")
        if not rec["Document_Hash"]:
            issues.append("missing_document_hash")
        if issues:
            blocked_reasons.update(issues)

    release_ready = (
        bool(records)
        and not metric_duplicates
        and not knowledge_duplicates
        and not observation_collisions
        and not blocked_reasons
    )

    fieldnames = list(records[0].keys()) if records else [
        "Source_Row", "Observation_Key", "Metric_ID",
        "Knowledge_Evidence_ID", "Ticker", "Original_Ticker", "Metric",
        "Value", "Unit", "Scale", "Period", "Semantic_Dimension",
        "Document_ID", "Document_Hash", "Source_Locator", "Lineage",
        "Status", "Classification",
    ]

    REPORTS.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    md = [
        "# PCIP11 — 0695.7 Persistence Contract R4",
        "",
        "## Safety",
        "- Persistence executed: NO",
        "- KnowledgeBridge executed: NO",
        "- Vault changed: NO",
        "",
        "## Source",
        f"- Input: `{INPUT_CSV.name}`",
        f"- Rows read: {len(rows)}",
        f"- Contract candidates: {len(records)}",
        f"- Canonical/eligible: {len(records)}",
        "",
        "## Identity validation",
        f"- Unique Metric_ID: {len(metric_groups)}",
        f"- Duplicate Metric_ID groups: {len(metric_duplicates)}",
        f"- Unique Knowledge_Evidence_ID: {len(knowledge_groups)}",
        f"- Duplicate Knowledge_Evidence_ID groups: {len(knowledge_duplicates)}",
        f"- Observation identity collisions: {len(observation_collisions)}",
        f"- Release ready: {'YES' if release_ready else 'NO'}",
        "",
        "## Block reasons",
    ]

    if blocked_reasons:
        for key, count in sorted(blocked_reasons.items()):
            md.append(f"- {key}: {count}")
    else:
        md.append("- none")

    md += [
        "",
        "## Contract rule",
        "- Metric_ID is generated exclusively by `metric_evidence_id(MetricObservationIdentity)`.",
        "- Knowledge_Evidence_ID is generated exclusively by `knowledge_evidence_id(Metric_ID)`.",
        "- No manual or row-number-based persistence IDs are used.",
        "- This report is dry-run only; it does not persist to Obsidian.",
        "",
    ]

    OUTPUT_MD.write_text("\n".join(md), encoding="utf-8")

    print("=" * 90)
    print("0695.7 PERSISTENCE CONTRACT R4")
    print("=" * 90)
    print(f"Input rows                    : {len(rows)}")
    print(f"Contract candidates           : {len(records)}")
    print(f"Unique Metric_ID              : {len(metric_groups)}")
    print(f"Duplicate Metric_ID groups    : {len(metric_duplicates)}")
    print(f"Unique Knowledge IDs          : {len(knowledge_groups)}")
    print(f"Duplicate Knowledge ID groups : {len(knowledge_duplicates)}")
    print(f"Observation collisions        : {len(observation_collisions)}")
    print(f"Release ready                 : {'YES' if release_ready else 'NO'}")
    print("Persistence executed          : NO")
    print("KnowledgeBridge executed      : NO")
    print("Vault changed                 : NO")
    print(f"CSV                           : {OUTPUT_CSV}")
    print(f"MD                            : {OUTPUT_MD}")

    return 0 if release_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
