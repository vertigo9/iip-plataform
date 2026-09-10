from __future__ import annotations

import csv
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from iip.intelligence.metric_evidence import (
    EvidenceSourceRole,
    HistoricalMetricEvidence,
    LineageStatus,
    MetricObservation,
    PeriodStatus,
    TickerLineage,
    UnitStatus,
    assess_promotion,
)

ROOT = Path.cwd()
REPORTS = ROOT / "reports"

INPUT_CANDIDATES = REPORTS / "PCIP11_METRIC_PROMOTION_CANDIDATES_0695_6R2.csv"
INPUT_RESOLUTION = REPORTS / "PCIP11_SEMANTIC_RESOLUTION_0695_6R4R4.csv"
OUTPUT = REPORTS / "PCIP11_0695_7_DOMAIN_ASSESSMENT.csv"
SUMMARY = REPORTS / "PCIP11_0695_7_DOMAIN_ASSESSMENT.md"


def pick(row, *names):
    for name in names:
        if name in row and str(row[name]).strip():
            return str(row[name]).strip()
    return ""


def float_value(text: str) -> float:
    s = text.strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def infer_role(row) -> EvidenceSourceRole:
    raw = (
        pick(row, "Evidence_Type", "Source_Role", "Evidence_Role",
             "Canonical_Type", "Document_Role")
        .upper()
    )
    if "DISTRIBUT" in raw:
        return EvidenceSourceRole.DISTRIBUTION
    if "NAV" in raw or "PL" in raw:
        return EvidenceSourceRole.NAV_PL
    if "RESULT" in raw or "DRE" in raw:
        return EvidenceSourceRole.RESULT
    if "PORTFOLIO" in raw or "CREDIT" in raw:
        return EvidenceSourceRole.PORTFOLIO_CREDIT
    if "EVENT" in raw:
        return EvidenceSourceRole.EVENT
    return EvidenceSourceRole.DOCUMENT


def parse_date(value: str):
    from datetime import date
    text = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return date.fromisoformat(text) if fmt == "%Y-%m-%d" else date.fromisoformat(
                __import__("datetime").datetime.strptime(text, fmt).date().isoformat()
            )
        except ValueError:
            continue
    return None


def build_evidence(row):
    original = pick(row, "Original_Ticker", "Content_Ticker", "Ticker") or "PCIP11"
    canonical = "PCIP11" if original.upper() == "CVBI11" else original.upper()

    lineage_status = (
        LineageStatus.HISTORICAL_PREDECESSOR
        if original.upper() == "CVBI11" and canonical == "PCIP11"
        else LineageStatus.CURRENT
        if canonical == original.upper()
        else LineageStatus.UNKNOWN
    )

    period = pick(row, "Resolved_Period", "Content_Period", "Period", "Content_Periods")
    unit = pick(row, "Unit", "Metric_Unit", "Observed_Unit")
    scale = pick(row, "Scale", "Metric_Scale", "Observed_Scale")
    metric = pick(row, "Metric_Name", "Metric", "Metric_Key") or "unresolved_metric"
    value_text = pick(row, "Value", "Metric_Value", "Observed_Value") or "0"
    confidence = float_value(
        pick(row, "Confidence", "Semantic_Confidence", "Evidence_Confidence") or "0"
    )

    period_status = (
        PeriodStatus.EXPLICIT if period and not period.lower() in {"unknown", "n/a", "na"}
        else PeriodStatus.MISSING
    )
    unit_status = (
        UnitStatus.EXPLICIT if unit and unit.lower() not in {"unknown", "n/a", "na"}
        else UnitStatus.MISSING
    )

    from datetime import date
    source_date = parse_date(
        pick(row, "Source_Date", "Document_Date", "Date", "Observation_Date")
    )

    return HistoricalMetricEvidence(
        evidence_id=pick(row, "Evidence_ID", "Candidate_ID", "Metric_ID")
        or ("EV-" + pick(row, "SHA256", "Document_ID", "Historical_ID")[:20]),
        document_id=pick(row, "Document_ID", "Historical_ID", "FileName") or "UNKNOWN-DOC",
        document_hash=pick(row, "SHA256", "Document_Hash") or None,
        original_ticker=original,
        canonical_ticker=canonical,
        lineage=TickerLineage(
            original_ticker=original,
            canonical_ticker=canonical,
            status=lineage_status,
        ),
        source_role=infer_role(row),
        source_title=pick(row, "FileName", "Title", "Source_Title") or "UNKNOWN",
        source_date=source_date,
        observation=MetricObservation(
            metric_name=metric,
            value=float_value(value_text),
            unit=unit or None,
            scale=scale or None,
            period=period or None,
            period_status=period_status,
            unit_status=unit_status,
        ),
        confidence=max(0.0, min(1.0, confidence)),
        source_locator=pick(row, "Source_Locator", "Locator") or None,
        relevant_fact=pick(row, "Relevant_Fact", "Evidence", "Evidence_Summary") or None,
    )


def main():
    if not INPUT_CANDIDATES.exists():
        raise SystemExit(f"Missing input: {INPUT_CANDIDATES}")

    with INPUT_CANDIDATES.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    resolution = {}
    if INPUT_RESOLUTION.exists():
        with INPUT_RESOLUTION.open("r", encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                key = pick(r, "SHA256", "Historical_ID", "Candidate_ID")
                if key:
                    resolution[key] = r

    output_rows = []
    errors = 0
    status_counter = Counter()
    lineage_counter = Counter()

    for index, row in enumerate(rows, 1):
        key = pick(row, "SHA256", "Historical_ID", "Candidate_ID")
        merged = dict(resolution.get(key, {}))
        merged.update({k: v for k, v in row.items() if str(v).strip()})

        try:
            evidence = build_evidence(merged)
            assessment = assess_promotion(evidence)
            status = assessment.status.value
            reasons = "|".join(assessment.reasons)
            lineage = (
                f"{evidence.original_ticker}->{evidence.canonical_ticker}"
                if evidence.lineage.changed
                else evidence.canonical_ticker
            )

            status_counter[status] += 1
            lineage_counter[lineage] += 1

            output_rows.append({
                "Row": index,
                "Evidence_ID": evidence.evidence_id,
                "Document_ID": evidence.document_id,
                "SHA256": evidence.document_hash or "",
                "Original_Ticker": evidence.original_ticker,
                "Canonical_Ticker": evidence.canonical_ticker,
                "Lineage_Status": evidence.lineage.status.value,
                "Source_Role": evidence.source_role.value,
                "Metric_Name": evidence.observation.metric_name,
                "Value": evidence.observation.value,
                "Unit": evidence.observation.unit or "",
                "Scale": evidence.observation.scale or "",
                "Period": evidence.observation.period or "",
                "Period_Status": evidence.observation.period_status.value,
                "Unit_Status": evidence.observation.unit_status.value,
                "Confidence": evidence.confidence,
                "Promotion_Status": status,
                "Promotion_Reasons": reasons,
                "Domain_Object": "HistoricalMetricEvidence",
            })
        except Exception as exc:
            errors += 1
            output_rows.append({
                "Row": index,
                "Evidence_ID": "",
                "Document_ID": key,
                "SHA256": pick(merged, "SHA256"),
                "Original_Ticker": pick(merged, "Original_Ticker", "Content_Ticker"),
                "Canonical_Ticker": "",
                "Lineage_Status": "",
                "Source_Role": "",
                "Metric_Name": "",
                "Value": "",
                "Unit": "",
                "Scale": "",
                "Period": "",
                "Period_Status": "",
                "Unit_Status": "",
                "Confidence": "",
                "Promotion_Status": "HOLD",
                "Promotion_Reasons": f"domain_build_error:{type(exc).__name__}",
                "Domain_Object": "",
            })

    REPORTS.mkdir(parents=True, exist_ok=True)
    fieldnames = list(output_rows[0].keys()) if output_rows else ["Row"]

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    md = [
        "# PCIP11 - 0695.7 Domain Assessment",
        "",
        f"- Input candidates: {len(rows)}",
        f"- Built domain objects: {len(rows) - errors}",
        f"- Build errors: {errors}",
        f"- ELIGIBLE: {status_counter['ELIGIBLE']}",
        f"- REVIEW: {status_counter['REVIEW']}",
        f"- HOLD: {status_counter['HOLD']}",
        "",
        "## Lineage",
    ]
    for key, count in sorted(lineage_counter.items()):
        md.append(f"- `{key}`: {count}")

    md += [
        "",
        "## Safety",
        "- This run does not modify the Obsidian Vault.",
        "- This run does not persist metrics.",
        "- CVBI11 -> PCIP11 remains explicit; source ticker is not overwritten.",
    ]
    SUMMARY.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("0695.7 REAL CANDIDATE DOMAIN ASSESSMENT")
    print(f"Input candidates : {len(rows)}")
    print(f"Built objects    : {len(rows) - errors}")
    print(f"Build errors     : {errors}")
    print(f"ELIGIBLE         : {status_counter['ELIGIBLE']}")
    print(f"REVIEW           : {status_counter['REVIEW']}")
    print(f"HOLD             : {status_counter['HOLD']}")
    print(f"Output           : {OUTPUT}")
    print(f"Summary          : {SUMMARY}")
    print("")
    print("Vault changed: NO")
    print("Metric promoted: NO")


if __name__ == "__main__":
    main()
