from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "reports"
INPUT_CSV = REPORTS / "PCIP11_0695_7_PERSISTENCE_CONTRACT_R4.csv"
OUTPUT_CSV = REPORTS / "PCIP11_0695_7_KNOWLEDGE_BRIDGE_DRY_RUN_R1.csv"
OUTPUT_MD = REPORTS / "PCIP11_0695_7_KNOWLEDGE_BRIDGE_DRY_RUN_R1.md"

SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from iip.intelligence.metric_identity import MetricObservationIdentity
from iip.intelligence.metric_persistence import (
    build_knowledge_evidence,
    knowledge_evidence_id,
    metric_evidence_id,
)
from iip.knowledge.models import Evidence


def pick(row: dict[str, str], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def build_identity(row: dict[str, str]) -> MetricObservationIdentity:
    return MetricObservationIdentity(
        canonical_ticker=pick(row, "Ticker"),
        original_ticker=pick(row, "Original_Ticker") or pick(row, "Ticker"),
        metric_name=pick(row, "Metric"),
        value=pick(row, "Value"),
        unit=pick(row, "Unit") or None,
        scale=pick(row, "Scale") or None,
        period=pick(row, "Period"),
        semantic_dimension=pick(row, "Semantic_Dimension") or None,
        document_hash=pick(row, "Document_Hash"),
        document_id=pick(row, "Document_ID") or None,
        source_locator=pick(row, "Source_Locator") or None,
        lineage=pick(row, "Lineage") or None,
    )


def main() -> int:
    if not INPUT_CSV.exists():
        print(f"ERROR: input not found: {INPUT_CSV}")
        return 2

    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    out = []
    failures = Counter()

    for idx, row in enumerate(rows, start=2):
        try:
            identity = build_identity(row)
            metric_id = metric_evidence_id(identity)
            expected_knowledge_id = knowledge_evidence_id(metric_id)

            km = build_knowledge_evidence(
                identity,
                title=pick(row, "FileName")
                or f"{identity.canonical_ticker} {identity.period}",
                source_type="historical_metric",
                source_url=None,
                relevant_facts={
                    "observation_key": identity.observation_key,
                    "metric_id": metric_id,
                    "canonical_observation_id": pick(row, "Canonical_Observation_ID"),
                    "resolution_status": pick(row, "Resolution_Status"),
                    "resolution_type": pick(row, "Resolution_Type"),
                    "resolution_selected_context": pick(
                        row, "Resolution_Selected_Context"
                    ),
                    "lineage": identity.lineage or "",
                },
            )

            # Dry-run mapping to the actual knowledge.models.Evidence shape.
            evidence = Evidence(
                evidence_id=km.evidence_id,
                ticker=km.ticker,
                date=km.date,
                source_type=km.source_type,
                source_url=km.source_url,
                title=km.title,
                document_hash=km.document_hash,
                relevant_facts=km.relevant_facts,
            )

            checks = {
                "metric_id_stable": metric_id == metric_evidence_id(identity),
                "knowledge_id_stable": evidence.evidence_id == expected_knowledge_id,
                "ticker_preserved": evidence.ticker == identity.canonical_ticker,
                "date_preserved": evidence.date.isoformat() == f"{identity.period}-01",
                "document_hash_preserved": evidence.document_hash
                == identity.document_hash,
                "metric_fact_present": evidence.relevant_facts.get("metric")
                == identity.metric_name,
                "value_fact_present": evidence.relevant_facts.get("value")
                == identity.value,
                "semantic_dimension_preserved": (
                    evidence.relevant_facts.get("semantic_dimension")
                    == (identity.semantic_dimension or "")
                ),
                "source_locator_preserved": (
                    evidence.relevant_facts.get("source_locator")
                    == (identity.source_locator or "")
                ),
                "lineage_preserved": (
                    evidence.relevant_facts.get("lineage") == (identity.lineage or "")
                ),
            }

            failed = [key for key, value in checks.items() if not value]
            if failed:
                failures.update(failed)
                status = "BLOCKED"
            else:
                status = "READY"

            out.append(
                {
                    "Source_Row": str(idx),
                    "Metric_ID": metric_id,
                    "Knowledge_Evidence_ID": evidence.evidence_id,
                    "Ticker": evidence.ticker,
                    "Date": evidence.date.isoformat(),
                    "Metric": identity.metric_name,
                    "Value": identity.value,
                    "Unit": identity.unit or "",
                    "Scale": identity.scale or "",
                    "Period": identity.period,
                    "Semantic_Dimension": identity.semantic_dimension or "",
                    "Document_ID": identity.document_id or "",
                    "Document_Hash": evidence.document_hash,
                    "Source_Locator": identity.source_locator or "",
                    "Lineage": identity.lineage or "",
                    "Mapping_Status": status,
                    "Failed_Checks": ",".join(failed),
                }
            )

        except Exception as exc:
            failures[f"exception:{type(exc).__name__}:{exc}"] += 1
            out.append(
                {
                    "Source_Row": str(idx),
                    "Metric_ID": "",
                    "Knowledge_Evidence_ID": "",
                    "Ticker": pick(row, "Ticker"),
                    "Date": "",
                    "Metric": pick(row, "Metric"),
                    "Value": pick(row, "Value"),
                    "Unit": pick(row, "Unit"),
                    "Scale": pick(row, "Scale"),
                    "Period": pick(row, "Period"),
                    "Semantic_Dimension": pick(row, "Semantic_Dimension"),
                    "Document_ID": pick(row, "Document_ID"),
                    "Document_Hash": pick(row, "Document_Hash"),
                    "Source_Locator": pick(row, "Source_Locator"),
                    "Lineage": pick(row, "Lineage"),
                    "Mapping_Status": "BLOCKED",
                    "Failed_Checks": f"exception:{type(exc).__name__}:{exc}",
                }
            )

    ready = sum(row["Mapping_Status"] == "READY" for row in out)
    blocked = len(out) - ready
    metric_ids = [row["Metric_ID"] for row in out if row["Metric_ID"]]
    knowledge_ids = [
        row["Knowledge_Evidence_ID"] for row in out if row["Knowledge_Evidence_ID"]
    ]

    metric_duplicate_count = sum(
        count - 1 for count in Counter(metric_ids).values() if count > 1
    )
    knowledge_duplicate_count = sum(
        count - 1 for count in Counter(knowledge_ids).values() if count > 1
    )

    release_ready = (
        len(out) == 28
        and ready == 28
        and blocked == 0
        and metric_duplicate_count == 0
        and knowledge_duplicate_count == 0
        and not failures
    )

    fieldnames = list(out[0].keys()) if out else []
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out)

    lines = [
        "# PCIP11 — 0695.7 KnowledgeBridge Dry-Run R1",
        "",
        "## Safety",
        "- KnowledgeBridge executed: NO",
        "- Repository save_evidence executed: NO",
        "- Vault changed: NO",
        "",
        "## Results",
        f"- Input rows: {len(rows)}",
        f"- Mapped rows: {ready}",
        f"- Blocked rows: {blocked}",
        f"- Duplicate Metric_ID rows: {metric_duplicate_count}",
        f"- Duplicate Knowledge_Evidence_ID rows: {knowledge_duplicate_count}",
        f"- Release ready: {'YES' if release_ready else 'NO'}",
        "",
        "## Failure details",
    ]
    if failures:
        lines.extend(f"- {key}: {count}" for key, count in sorted(failures.items()))
    else:
        lines.append("- none")

    lines += [
        "",
        "This is a dry-run only. No persistence method is invoked.",
    ]
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print("=" * 90)
    print("0695.7 KNOWLEDGEBRIDGE DRY-RUN R1")
    print("=" * 90)
    print(f"Input rows                    : {len(rows)}")
    print(f"Mapped rows                   : {ready}")
    print(f"Blocked rows                  : {blocked}")
    print(f"Duplicate Metric_ID rows     : {metric_duplicate_count}")
    print(f"Duplicate Knowledge_ID rows  : {knowledge_duplicate_count}")
    print(f"Release ready                 : {'YES' if release_ready else 'NO'}")
    print("KnowledgeBridge executed      : NO")
    print("Repository save_evidence      : NO")
    print("Vault changed                 : NO")
    print(f"CSV                           : {OUTPUT_CSV}")
    print(f"MD                            : {OUTPUT_MD}")
    return 0 if release_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
