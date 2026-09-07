from __future__ import annotations

import csv
import hashlib
import sys
from collections import Counter
from dataclasses import asdict
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

# Current 0695.7 execution source. The adapter itself is generic and does not
# hard-code PCIP11; this is only the first available production-shaped input.
DEFAULT_INPUT = REPORTS / "PCIP11_0695_7_FINAL_PROMOTION_GATE_R1.csv"

OUTPUT_CSV = REPORTS / "0695_GENERIC_METRIC_PERSISTENCE_DRY_RUN_R1.csv"
OUTPUT_MD = REPORTS / "0695_GENERIC_METRIC_PERSISTENCE_DRY_RUN_R1.md"

VALID_LINEAGES = {
    "PCIP11": ("PCIP11", "PCIP11", "CURRENT"),
    "CVBI11 -> PCIP11": ("CVBI11", "PCIP11", "HISTORICAL_PREDECESSOR"),
}


def configure_utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def read_csv(path: Path) -> list[dict[str, str]]:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"Não foi possível ler: {path}")


def get(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = (row.get(key) or "").strip()
        if value:
            return value
    return ""


def slug(value: str) -> str:
    result = []
    for char in (value or "").strip():
        if char.isalnum() or char in ("-", "_", "."):
            result.append(char)
        else:
            result.append("_")
    return "".join(result).strip("_")


def canonical_lineage(lineage_text: str, original_ticker: str) -> tuple[str, str, str]:
    lineage = (lineage_text or "").strip()

    if lineage in VALID_LINEAGES:
        return VALID_LINEAGES[lineage]

    # Generic current-asset case: a row may carry only the canonical ticker.
    if lineage and "->" not in lineage:
        ticker = lineage.upper()
        return ticker, ticker, "CURRENT"

    # Generic historical lineage fallback, e.g. "OLD -> NEW".
    if "->" in lineage:
        parts = [part.strip().upper() for part in lineage.split("->", 1)]
        if len(parts) == 2 and all(parts):
            return parts[0], parts[1], "HISTORICAL_PREDECESSOR"

    if original_ticker:
        ticker = original_ticker.upper()
        return ticker, ticker, "UNKNOWN"

    return "", "", "UNKNOWN"


def parse_float(value: str) -> float:
    normalized = (value or "").strip().replace(".", "").replace(",", ".")
    return float(normalized)


def parse_date_from_period(period: str) -> date | None:
    period = (period or "").strip()
    if len(period) != 7 or period[4] != "-":
        return None

    try:
        year = int(period[:4])
        month = int(period[5:7])
        return date(year, month, 1)
    except ValueError:
        return None


def stable_document_id(sha256: str, filename: str) -> str:
    # Preserve a human-recognizable prefix while making the identifier stable.
    digest = hashlib.sha256(
        f"{sha256.upper()}|{filename}".encode("utf-8")
    ).hexdigest()[:24]

    return f"historical_document:{sha256.upper()[:16]}:{digest}"


def stable_metric_evidence_id(
    document_id: str,
    original_ticker: str,
    canonical_ticker: str,
    metric: str,
    period: str,
) -> str:
    payload = "|".join(
        (
            document_id,
            original_ticker.upper(),
            canonical_ticker.upper(),
            metric,
            period,
        )
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"metric:{canonical_ticker.upper()}:{period}:{metric}:{digest}"


def stable_knowledge_evidence_id(
    metric_evidence_id: str,
) -> str:
    digest = hashlib.sha256(
        metric_evidence_id.encode("utf-8")
    ).hexdigest()[:24]
    return f"evidence:metric:{digest}"


def build_relevant_facts(row: dict[str, str], original_ticker: str, canonical_ticker: str, lineage_status: str) -> tuple[str, ...]:
    facts = []

    facts.append(f"metric={get(row, 'Metric')}")
    facts.append(f"value={get(row, 'Value')}")
    facts.append(f"unit={get(row, 'Resolved_Unit', 'Original_Unit')}")
    facts.append(f"scale={get(row, 'Scale')}")
    facts.append(f"period={get(row, 'Resolved_Period')}")
    facts.append(f"legacy_period={get(row, 'Legacy_Period')}")
    facts.append(f"original_ticker={original_ticker}")
    facts.append(f"canonical_ticker={canonical_ticker}")
    facts.append(f"lineage_status={lineage_status}")
    facts.append(f"sha256={get(row, 'SHA256')}")
    facts.append(f"source_file={get(row, 'FileName')}")
    facts.append(f"temporal_reason={get(row, 'Temporal_Gate_Reason')}")

    # Optional evidence trace fields from final gate.
    source_role = get(row, "Domain_Source_Role", "Source_Role", "Document_Role")
    if source_role:
        facts.append(f"source_role={source_role}")

    evidence_text = get(row, "Evidence_Text", "Relevant_Fact")
    if evidence_text:
        # Keep the fact compact; detailed source text remains outside the
        # knowledge model until a future evidence-document contract exists.
        compact = " ".join(evidence_text.split())
        if len(compact) > 500:
            compact = compact[:500] + "..."
        facts.append(f"evidence_text={compact}")

    return tuple(facts)


def validate_row(row: dict[str, str]) -> tuple[bool, list[str]]:
    failures = []

    for field in ("SHA256", "FileName", "Metric", "Value", "Resolved_Period"):
        if not get(row, field):
            failures.append(f"missing_{field}")

    if len(get(row, "SHA256")) != 64:
        failures.append("invalid_sha256_length")

    lineage = get(row, "Lineage")
    if not lineage:
        failures.append("missing_lineage")

    resolved_unit = get(row, "Resolved_Unit", "Original_Unit")
    if not resolved_unit:
        failures.append("missing_unit")

    if not get(row, "Scale"):
        failures.append("missing_scale")

    if get(row, "Resolved_Period") == "2003-12":
        failures.append("resolved_period_is_legacy_false_positive")

    if get(row, "Final_Promotion_Gate") != "PASS":
        failures.append("row_not_final_pass")

    if get(row, "Temporal_Gate") != "PASS":
        failures.append("temporal_gate_not_pass")

    return not failures, failures


def dry_run_build(row: dict[str, str]) -> dict[str, object]:
    valid, validation_failures = validate_row(row)

    original_ticker, canonical_ticker, lineage_status = canonical_lineage(
        get(row, "Lineage"),
        get(row, "Original_Identity"),
    )

    metric = get(row, "Metric")
    value_raw = get(row, "Value")
    period = get(row, "Resolved_Period")
    sha256 = get(row, "SHA256").upper()
    filename = get(row, "FileName")

    value = None
    value_error = ""
    if value_raw:
        try:
            value = parse_float(value_raw)
        except (TypeError, ValueError):
            value_error = "invalid_numeric_value"

    source_date = parse_date_from_period(period)
    if period and source_date is None:
        validation_failures.append("invalid_resolved_period")

    document_id = stable_document_id(sha256, filename)
    metric_evidence_id = stable_metric_evidence_id(
        document_id,
        original_ticker,
        canonical_ticker,
        metric,
        period,
    )
    knowledge_evidence_id = stable_knowledge_evidence_id(metric_evidence_id)

    if value_error:
        validation_failures.append(value_error)

    if original_ticker and canonical_ticker:
        if lineage_status == "CURRENT" and original_ticker != canonical_ticker:
            validation_failures.append("current_lineage_ticker_mismatch")

    ready = valid and not validation_failures and value is not None and source_date is not None

    return {
        "Row": get(row, "Row"),
        "SHA256": sha256,
        "FileName": filename,
        "Original_Identity": get(row, "Original_Identity"),
        "Original_Ticker": original_ticker,
        "Canonical_Ticker": canonical_ticker,
        "Lineage": get(row, "Lineage"),
        "Lineage_Status": lineage_status,
        "Metric": metric,
        "Value_Raw": value_raw,
        "Value_Parsed": "" if value is None else str(value),
        "Original_Unit": get(row, "Original_Unit"),
        "Resolved_Unit": get(row, "Resolved_Unit"),
        "Scale": get(row, "Scale"),
        "Legacy_Period": get(row, "Legacy_Period"),
        "Resolved_Period": period,
        "Source_Date": "" if source_date is None else source_date.isoformat(),
        "Document_ID": document_id,
        "Metric_Evidence_ID": metric_evidence_id,
        "Knowledge_Evidence_ID": knowledge_evidence_id,
        "Relevant_Facts_Count": "0",
        "Relevant_Facts": "",
        "Validation_Status": "READY" if ready else "BLOCKED",
        "Validation_Reason": "ALL_DRY_RUN_CHECKS_PASS" if ready else "|".join(sorted(set(validation_failures))),
        "Persistence_Executed": "NO",
        "KnowledgeBridge_Executed": "NO",
        "Vault_Changed": "NO",
    }


def main() -> None:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT

    if not input_path.exists():
        raise FileNotFoundError(input_path)

    rows = read_csv(input_path)

    output_rows = []
    seen_metric_ids: Counter[str] = Counter()
    seen_knowledge_ids: Counter[str] = Counter()
    seen_document_metric_keys: Counter[tuple[str, str, str]] = Counter()

    for row in rows:
        if get(row, "Final_Promotion_Gate") != "PASS":
            continue

        result = dry_run_build(row)

        facts = build_relevant_facts(
            row,
            result["Original_Ticker"],
            result["Canonical_Ticker"],
            result["Lineage_Status"],
        )

        result["Relevant_Facts_Count"] = str(len(facts))
        result["Relevant_Facts"] = " | ".join(facts)

        output_rows.append(result)

        seen_metric_ids[result["Metric_Evidence_ID"]] += 1
        seen_knowledge_ids[result["Knowledge_Evidence_ID"]] += 1
        seen_document_metric_keys[
            (
                result["SHA256"],
                result["Metric"],
                result["Resolved_Period"],
            )
        ] += 1

    duplicate_metric_ids = [
        key for key, count in seen_metric_ids.items() if count > 1
    ]
    duplicate_knowledge_ids = [
        key for key, count in seen_knowledge_ids.items() if count > 1
    ]
    duplicate_document_metric_keys = [
        key for key, count in seen_document_metric_keys.items() if count > 1
    ]

    for result in output_rows:
        extra_failures = []

        if result["Metric_Evidence_ID"] in duplicate_metric_ids:
            extra_failures.append("duplicate_metric_evidence_id")

        if result["Knowledge_Evidence_ID"] in duplicate_knowledge_ids:
            extra_failures.append("duplicate_knowledge_evidence_id")

        key = (
            result["SHA256"],
            result["Metric"],
            result["Resolved_Period"],
        )
        if key in duplicate_document_metric_keys:
            extra_failures.append("duplicate_document_metric_period")

        if extra_failures:
            result["Validation_Status"] = "BLOCKED"
            existing = result["Validation_Reason"]
            result["Validation_Reason"] = "|".join(
                part for part in (existing, *extra_failures) if part
            )

    fieldnames = list(output_rows[0].keys()) if output_rows else []
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    validation_counts = Counter(
        row["Validation_Status"] for row in output_rows
    )
    lineage_counts = Counter(
        row["Lineage_Status"] for row in output_rows
    )
    ticker_counts = Counter(
        row["Canonical_Ticker"] for row in output_rows
    )

    reasons = Counter()
    for row in output_rows:
        if row["Validation_Status"] == "BLOCKED":
            for reason in row["Validation_Reason"].split("|"):
                if reason:
                    reasons[reason] += 1

    with OUTPUT_MD.open("w", encoding="utf-8") as handle:
        handle.write("# Generic Metric Persistence Dry-Run R1\n\n")
        handle.write(
            "Generic adapter dry-run for the IIP metric persistence contract. "
            "The current input is the 0695.7 PCIP11 gate output, but the adapter "
            "contains no PCIP11-specific persistence logic and is intended for "
            "all tickers and historical lineages.\n\n"
        )

        handle.write("## Input\n\n")
        handle.write(f"- `{input_path}`\n")
        handle.write(f"- Final PASS rows consumed: {len(rows)} total input rows, ")
        handle.write(f"{len(output_rows)} PASS rows selected.\n\n")

        handle.write("## Result\n\n")
        handle.write(f"- READY: {validation_counts.get('READY', 0)}\n")
        handle.write(f"- BLOCKED: {validation_counts.get('BLOCKED', 0)}\n")
        handle.write(f"- Duplicate Metric_Evidence_ID: {len(duplicate_metric_ids)}\n")
        handle.write(f"- Duplicate Knowledge_Evidence_ID: {len(duplicate_knowledge_ids)}\n")
        handle.write(
            f"- Duplicate SHA+Metric+Resolved_Period keys: "
            f"{len(duplicate_document_metric_keys)}\n\n"
        )

        handle.write("## Canonical tickers\n\n")
        for ticker, count in sorted(ticker_counts.items()):
            handle.write(f"- {ticker}: {count}\n")

        handle.write("\n## Lineage statuses\n\n")
        for status, count in sorted(lineage_counts.items()):
            handle.write(f"- {status}: {count}\n")

        handle.write("\n## Block reasons\n\n")
        if reasons:
            for reason, count in reasons.most_common():
                handle.write(f"- {reason}: {count}\n")
        else:
            handle.write("- None\n")

        handle.write("\n## Contract mapping\n\n")
        handle.write(
            "- HistoricalMetricEvidence is the domain source object.\n"
            "- Knowledge Evidence is the persistence-facing model.\n"
            "- Platform Evidence is NOT used as the semantic destination.\n"
            "- EvidenceChain remains a separate provenance linkage.\n"
            "- KnowledgeBridge persistence is NOT executed in this dry-run.\n"
        )

        handle.write("\n## Safety\n\n")
        handle.write("- Persistence executed: NO\n")
        handle.write("- KnowledgeBridge executed: NO\n")
        handle.write("- Vault changed: NO\n")

    print("069 GENERIC METRIC PERSISTENCE DRY-RUN R1")
    print("=" * 100)
    print(f"Input rows                 : {len(rows)}")
    print(f"Final PASS rows consumed   : {len(output_rows)}")
    print(f"READY                      : {validation_counts.get('READY', 0)}")
    print(f"BLOCKED                    : {validation_counts.get('BLOCKED', 0)}")
    print(f"Duplicate Metric IDs       : {len(duplicate_metric_ids)}")
    print(f"Duplicate Knowledge IDs    : {len(duplicate_knowledge_ids)}")
    print(f"Duplicate SHA+metric+period: {len(duplicate_document_metric_keys)}")
    print(f"Tickers represented        : {len(ticker_counts)}")
    print(f"CSV                        : {OUTPUT_CSV}")
    print(f"MD                         : {OUTPUT_MD}")
    print("Persistence executed       : NO")
    print("KnowledgeBridge executed   : NO")
    print("Vault changed              : NO")


if __name__ == "__main__":
    configure_utf8()
    main()
