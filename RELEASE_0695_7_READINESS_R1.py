from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

FINAL_GATE_FILE = REPORTS / "PCIP11_0695_7_FINAL_PROMOTION_GATE_R1.csv"
OUTPUT_CSV = REPORTS / "PCIP11_0695_7_RELEASE_READINESS_R1.csv"
OUTPUT_MD = REPORTS / "PCIP11_0695_7_RELEASE_READINESS_R1.md"


REQUIRED_PROVENANCE_FIELDS = (
    "SHA256",
    "FileName",
    "Original_Identity",
    "Lineage",
)

REQUIRED_METRIC_FIELDS = (
    "Metric",
    "Value",
    "Original_Unit",
    "Resolved_Unit",
    "Scale",
    "Resolved_Period",
)

REQUIRED_EVIDENCE_FIELDS = (
    "Temporal_Gate",
    "Temporal_Status",
    "Temporal_Confidence",
    "PDF_Status",
)

VALID_LINEAGES = {"PCIP11", "CVBI11 -> PCIP11"}

DOMAIN_PASS_VALUES = {
    "Domain_Status": "ELIGIBLE",
    "Domain_Resolution_Status": "AUTO_RESOLVED_REVIEW_REQUIRED",
    "Domain_Promotion_Action": "ELIGIBLE_FOR_PROMOTION_GATE",
    "Domain_Scale_State": "RESOLVED",
    "Domain_Plausibility": "PASS",
}

TEMPORAL_PASS_VALUES = {
    "Temporal_Gate": "PASS",
    "Temporal_Status": "RESOLVED",
    "Temporal_Confidence": "HIGH",
    "PDF_Status": "YES",
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


def get(row: dict[str, str], key: str) -> str:
    return (row.get(key) or "").strip()


def required_nonblank(row: dict[str, str], fields: tuple[str, ...]) -> tuple[bool, list[str]]:
    missing = [field for field in fields if not get(row, field)]
    return not missing, missing


def validate_pass_row(row: dict[str, str]) -> tuple[bool, list[str]]:
    failures: list[str] = []

    provenance_ok, provenance_missing = required_nonblank(
        row, REQUIRED_PROVENANCE_FIELDS
    )
    if not provenance_ok:
        failures.extend(f"missing_{field}" for field in provenance_missing)

    metric_ok, metric_missing = required_nonblank(
        row, REQUIRED_METRIC_FIELDS
    )
    if not metric_ok:
        failures.extend(f"missing_{field}" for field in metric_missing)

    evidence_ok, evidence_missing = required_nonblank(
        row, REQUIRED_EVIDENCE_FIELDS
    )
    if not evidence_ok:
        failures.extend(f"missing_{field}" for field in evidence_missing)

    if get(row, "Lineage") not in VALID_LINEAGES:
        failures.append("invalid_lineage")

    if not get(row, "Metric"):
        failures.append("empty_metric")

    if get(row, "Metric") == "UNSTRUCTURED_EVIDENCE":
        failures.append("unstructured_evidence_metric")

    for field, expected in DOMAIN_PASS_VALUES.items():
        if get(row, field) != expected:
            failures.append(f"{field}_not_{expected}")

    for field, expected in TEMPORAL_PASS_VALUES.items():
        if get(row, field) != expected:
            failures.append(f"{field}_not_{expected}")

    if get(row, "Resolved_Period") == "2003-12":
        failures.append("resolved_period_is_known_legacy_false_positive")

    if get(row, "Metric_Persistence_Authorization") != "NOT_GRANTED":
        failures.append("persistence_authorization_not_locked")

    if get(row, "KnowledgeBridge_Write_Authorization") != "NOT_GRANTED":
        failures.append("knowledgebridge_authorization_not_locked")

    if get(row, "Vault_Write_Authorization") != "NOT_GRANTED":
        failures.append("vault_authorization_not_locked")

    return not failures, failures


def classify_blocked_row(row: dict[str, str]) -> tuple[str, str]:
    reason = get(row, "Final_Promotion_Gate_Reason")

    legitimate_prefixes = (
        "domain_eligible",
        "promotion_action_eligible",
        "resolution_auto",
        "scale_resolved",
        "plausibility_pass",
        "lineage_known",
    )

    if any(token in reason for token in legitimate_prefixes):
        return "EXPECTED_DOMAIN_BLOCK", reason

    if reason:
        return "REVIEW_REQUIRED", reason

    return "INVALID_BLOCK_REASON", "empty_block_reason"


def main() -> None:
    if not FINAL_GATE_FILE.exists():
        raise FileNotFoundError(FINAL_GATE_FILE)

    rows = read_csv(FINAL_GATE_FILE)

    output_rows: list[dict[str, str]] = []

    pass_rows = [row for row in rows if get(row, "Final_Promotion_Gate") == "PASS"]
    blocked_rows = [
        row for row in rows if get(row, "Final_Promotion_Gate") == "BLOCKED"
    ]

    # Duplicate integrity.
    key_counter = Counter(
        (
            get(row, "Row"),
            get(row, "SHA256").upper(),
            get(row, "Metric"),
        )
        for row in rows
    )

    duplicate_keys = {
        key for key, count in key_counter.items()
        if count > 1
    }

    for row in rows:
        final_status = get(row, "Final_Promotion_Gate")

        if final_status == "PASS":
            checks = {
                "pass_row_contract": validate_pass_row(row)[0],
                "no_duplicate_identity":
                    (
                        get(row, "Row"),
                        get(row, "SHA256").upper(),
                        get(row, "Metric"),
                    ) not in duplicate_keys,
            }
            failures = []
            _, detailed_failures = validate_pass_row(row)
            failures.extend(detailed_failures)
            if not checks["no_duplicate_identity"]:
                failures.append("duplicate_identity_key")

            readiness = all(checks.values())
            readiness_status = "READY" if readiness else "BLOCKED"
            readiness_reason = (
                "ALL_RELEASE_READINESS_CHECKS_PASS"
                if readiness else "|".join(failures)
            )
        else:
            category, blocked_reason = classify_blocked_row(row)
            readiness_status = "EXPECTED_BLOCK" if category == "EXPECTED_DOMAIN_BLOCK" else "REVIEW"
            readiness_reason = blocked_reason

        output_rows.append({
            "Row": get(row, "Row"),
            "SHA256": get(row, "SHA256"),
            "FileName": get(row, "FileName"),
            "Original_Identity": get(row, "Original_Identity"),
            "Lineage": get(row, "Lineage"),
            "Metric": get(row, "Metric"),
            "Value": get(row, "Value"),
            "Original_Unit": get(row, "Original_Unit"),
            "Resolved_Unit": get(row, "Resolved_Unit"),
            "Scale": get(row, "Scale"),
            "Legacy_Period": get(row, "Legacy_Period"),
            "Resolved_Period": get(row, "Resolved_Period"),
            "Final_Promotion_Gate": final_status,
            "Release_Readiness": readiness_status,
            "Release_Readiness_Reason": readiness_reason,
            "Metric_Persistence_Authorization": get(
                row, "Metric_Persistence_Authorization"
            ),
            "KnowledgeBridge_Write_Authorization": get(
                row, "KnowledgeBridge_Write_Authorization"
            ),
            "Vault_Write_Authorization": get(
                row, "Vault_Write_Authorization"
            ),
        })

    fieldnames = list(output_rows[0].keys()) if output_rows else []
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    readiness_counts = Counter(
        row["Release_Readiness"] for row in output_rows
    )
    lineage_counts = Counter(
        row["Lineage"] for row in output_rows
    )
    ready_period_counts = Counter(
        row["Resolved_Period"]
        for row in output_rows
        if row["Release_Readiness"] == "READY"
    )

    pass_fail_counts = Counter()
    pass_reason_counts = Counter()

    for source_row, output_row in zip(rows, output_rows):
        if get(source_row, "Final_Promotion_Gate") == "PASS":
            ok, detailed_failures = validate_pass_row(source_row)
            pass_fail_counts["PASS" if ok else "FAIL"] += 1
            if not ok:
                for reason in detailed_failures:
                    pass_reason_counts[reason] += 1

    final_global_status = "READY_FOR_PERSISTENCE_DESIGN_REVIEW"
    if readiness_counts.get("READY", 0) != len(pass_rows):
        final_global_status = "BLOCKED_BY_RELEASE_READINESS"
    if readiness_counts.get("REVIEW", 0) > 0:
        final_global_status = "REVIEW_REQUIRED_ON_BLOCKED_ROWS"
    if duplicate_keys:
        final_global_status = "BLOCKED_BY_DUPLICATE_IDENTITY"

    with OUTPUT_MD.open("w", encoding="utf-8") as handle:
        handle.write("# 0695.7 Release Readiness R1\n\n")
        handle.write(
            "Final pre-persistence audit over the 0695.7 Final Promotion Gate. "
            "This report does not persist metrics, write KnowledgeBridge, or modify the Vault.\n\n"
        )

        handle.write("## Global status\n\n")
        handle.write(f"- Status: **{final_global_status}**\n")
        handle.write(f"- Total rows: {len(rows)}\n")
        handle.write(f"- Final PASS: {len(pass_rows)}\n")
        handle.write(f"- Final BLOCKED: {len(blocked_rows)}\n")
        handle.write(f"- Release READY: {readiness_counts.get('READY', 0)}\n")
        handle.write(
            f"- Expected domain blocks: {readiness_counts.get('EXPECTED_BLOCK', 0)}\n"
        )
        handle.write(f"- Review: {readiness_counts.get('REVIEW', 0)}\n")
        handle.write(f"- Duplicate identity keys: {len(duplicate_keys)}\n\n")

        handle.write("## PASS-row readiness contract\n\n")
        for field in REQUIRED_PROVENANCE_FIELDS + REQUIRED_METRIC_FIELDS + REQUIRED_EVIDENCE_FIELDS:
            handle.write(f"- `{field}` present\n")
        handle.write("- Valid lineage\n")
        handle.write("- Domain eligibility contract preserved\n")
        handle.write("- Temporal HIGH/PASS contract preserved\n")
        handle.write("- Resolved period != legacy false-positive `2003-12`\n")
        handle.write("- Persistence / KnowledgeBridge / Vault authorization remains NOT GRANTED\n\n")

        handle.write("## Ready periods\n\n")
        for period, count in sorted(ready_period_counts.items()):
            handle.write(f"- {period}: {count}\n")

        handle.write("\n## Lineage distribution\n\n")
        for lineage, count in sorted(lineage_counts.items()):
            handle.write(f"- {lineage or '(blank)'}: {count}\n")

        handle.write("\n## PASS-row validation\n\n")
        for key, count in pass_fail_counts.items():
            handle.write(f"- {key}: {count}\n")

        handle.write("\n## PASS-row failures\n\n")
        if pass_reason_counts:
            for reason, count in pass_reason_counts.most_common():
                handle.write(f"- {reason}: {count}\n")
        else:
            handle.write("- None\n")

        handle.write("\n## Blocked-row classification\n\n")
        for row in output_rows:
            if row["Release_Readiness"] in {"EXPECTED_BLOCK", "REVIEW"}:
                handle.write(
                    f"- Row {row['Row']} | SHA {row['SHA256']} | "
                    f"Metric {row['Metric']} | "
                    f"{row['Release_Readiness']} | {row['Release_Readiness_Reason']}\n"
                )

        handle.write("\n## Safety boundary\n\n")
        handle.write("- Metric persistence: NOT GRANTED\n")
        handle.write("- KnowledgeBridge write: NOT GRANTED\n")
        handle.write("- Vault write: NOT GRANTED\n")
        handle.write("- Legacy artifacts modified: NO\n")

    print("0695.7 RELEASE READINESS R1")
    print("=" * 100)
    print(f"Rows evaluated              : {len(rows)}")
    print(f"Final PASS                  : {len(pass_rows)}")
    print(f"Final BLOCKED               : {len(blocked_rows)}")
    print(f"Release READY               : {readiness_counts.get('READY', 0)}")
    print(f"Expected domain blocks      : {readiness_counts.get('EXPECTED_BLOCK', 0)}")
    print(f"Review                      : {readiness_counts.get('REVIEW', 0)}")
    print(f"Duplicate identity keys     : {len(duplicate_keys)}")
    print(f"Global status               : {final_global_status}")
    print(f"CSV                         : {OUTPUT_CSV}")
    print(f"MD                          : {OUTPUT_MD}")
    print("Metric persistence          : NOT GRANTED")
    print("KnowledgeBridge write       : NOT GRANTED")
    print("Vault changed               : NO")


if __name__ == "__main__":
    configure_utf8()
    main()
