from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

DOMAIN_FILE = REPORTS / "PCIP11_0695_7_DOMAIN_ASSESSMENT_R1.csv"
TEMPORAL_FILE = REPORTS / "PCIP11_0695_7_TEMPORAL_VALIDATION_GATE_R1.csv"

OUTPUT_CSV = REPORTS / "PCIP11_0695_7_FINAL_PROMOTION_GATE_R1.csv"
OUTPUT_MD = REPORTS / "PCIP11_0695_7_FINAL_PROMOTION_GATE_R1.md"


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


def build_domain_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        get(row, "Row"),
        get(row, "SHA256").upper(),
        get(row, "Metric"),
    )


def build_temporal_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        get(row, "Row"),
        get(row, "SHA256").upper(),
        get(row, "Metric"),
    )


def main() -> None:
    if not DOMAIN_FILE.exists():
        raise FileNotFoundError(DOMAIN_FILE)
    if not TEMPORAL_FILE.exists():
        raise FileNotFoundError(TEMPORAL_FILE)

    domain_rows = read_csv(DOMAIN_FILE)
    temporal_rows = read_csv(TEMPORAL_FILE)

    domain_by_key = {build_domain_key(row): row for row in domain_rows}
    temporal_by_key = {build_temporal_key(row): row for row in temporal_rows}

    output_rows: list[dict[str, str]] = []
    missing_temporal = 0
    mismatched_identity = 0

    for domain in domain_rows:
        key = build_domain_key(domain)
        temporal = temporal_by_key.get(key)

        if temporal is None:
            missing_temporal += 1
            temporal = {}

        # Domain-side eligibility is intentionally read from the existing
        # 0695.7 R1 contract without inventing new interpretations.
        domain_status = get(domain, "Domain_Status")
        domain_action = get(domain, "Promotion_Action")
        domain_resolution = get(domain, "Resolution_Status")
        domain_scale_state = get(domain, "Scale_State")
        domain_plausibility = get(domain, "Plausibility")
        lineage = get(domain, "Lineage")
        original_identity = get(domain, "Original_Identity")

        temporal_gate = get(temporal, "Temporal_Gate")
        temporal_status = get(temporal, "Temporal_Status")
        temporal_confidence = get(temporal, "Temporal_Confidence")
        resolved_period = get(temporal, "Resolved_Period")
        temporal_reason = get(temporal, "Temporal_Gate_Reason")
        pdf_status = get(temporal, "PDF_Status")

        identity_ok = lineage in {"PCIP11", "CVBI11 -> PCIP11"}

        domain_checks = {
            "domain_eligible":
                domain_status == "ELIGIBLE",
            "promotion_action_eligible":
                domain_action == "ELIGIBLE_FOR_PROMOTION_GATE",
            "resolution_auto":
                domain_resolution == "AUTO_RESOLVED_REVIEW_REQUIRED",
            "scale_resolved":
                domain_scale_state == "RESOLVED",
            "plausibility_pass":
                domain_plausibility == "PASS",
            "lineage_known":
                identity_ok,
        }

        temporal_checks = {
            "temporal_gate_pass":
                temporal_gate == "PASS",
            "temporal_status_resolved":
                temporal_status == "RESOLVED",
            "temporal_confidence_high":
                temporal_confidence == "HIGH",
            "resolved_period_present":
                bool(resolved_period),
            "pdf_extracted":
                pdf_status == "YES",
        }

        all_checks = {**domain_checks, **temporal_checks}
        final_pass = all(all_checks.values())

        reasons = [
            name for name, ok in all_checks.items()
            if not ok
        ]

        # Detect key corruption between the two layers.
        temporal_sha = get(temporal, "SHA256").upper()
        temporal_metric = get(temporal, "Metric")
        if temporal and (
            temporal_sha != get(domain, "SHA256").upper()
            or temporal_metric != get(domain, "Metric")
        ):
            mismatched_identity += 1
            final_pass = False
            reasons.append("cross_layer_identity_mismatch")

        output_rows.append({
            "Row": get(domain, "Row"),
            "SHA256": get(domain, "SHA256"),
            "FileName": get(domain, "FileName"),
            "Original_Identity": original_identity,
            "Lineage": lineage,
            "Metric": get(domain, "Metric"),
            "Value": get(domain, "Value"),
            "Original_Unit": get(domain, "Original_Unit"),
            "Resolved_Unit": get(domain, "Resolved_Unit"),
            "Scale": get(domain, "Scale"),
            "Legacy_Period": get(domain, "Period"),
            "Resolved_Period": resolved_period,
            "Domain_Status": domain_status,
            "Domain_Resolution_Status": domain_resolution,
            "Domain_Promotion_Action": domain_action,
            "Domain_Scale_State": domain_scale_state,
            "Domain_Plausibility": domain_plausibility,
            "Temporal_Status": temporal_status,
            "Temporal_Confidence": temporal_confidence,
            "Temporal_Gate": temporal_gate,
            "Temporal_Gate_Reason": temporal_reason,
            "PDF_Status": pdf_status,
            "Final_Promotion_Gate": "PASS" if final_pass else "BLOCKED",
            "Final_Promotion_Gate_Reason": (
                "ALL_DOMAIN_AND_TEMPORAL_CHECKS_PASS"
                if final_pass else "|".join(reasons)
            ),
            "Metric_Persistence_Authorization": (
                "NOT_GRANTED"
                if final_pass else "DENIED"
            ),
            "KnowledgeBridge_Write_Authorization": "NOT_GRANTED",
            "Vault_Write_Authorization": "NOT_GRANTED",
        })

    fieldnames = list(output_rows[0].keys()) if output_rows else []
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    final_counts = Counter(
        row["Final_Promotion_Gate"] for row in output_rows
    )
    reason_counts = Counter(
        row["Final_Promotion_Gate_Reason"]
        for row in output_rows
        if row["Final_Promotion_Gate"] == "BLOCKED"
    )
    period_counts = Counter(
        row["Resolved_Period"]
        for row in output_rows
        if row["Final_Promotion_Gate"] == "PASS"
    )
    lineage_counts = Counter(row["Lineage"] for row in output_rows)

    with OUTPUT_MD.open("w", encoding="utf-8") as handle:
        handle.write("# 0695.7 Final Promotion Gate R1\n\n")
        handle.write(
            "Cross-layer read-only gate combining the existing 0695.7 "
            "domain eligibility with the validated temporal gate. PASS "
            "means structurally eligible for the next persistence stage; "
            "it does not authorize metric persistence, KnowledgeBridge "
            "writes, or Vault writes.\n\n"
        )

        handle.write("## Summary\n\n")
        handle.write(f"- Domain rows: {len(domain_rows)}\n")
        handle.write(f"- Temporal rows: {len(temporal_rows)}\n")
        handle.write(f"- Final PASS: {final_counts.get('PASS', 0)}\n")
        handle.write(f"- Final BLOCKED: {final_counts.get('BLOCKED', 0)}\n")
        handle.write(f"- Missing temporal match: {missing_temporal}\n")
        handle.write(f"- Cross-layer identity mismatch: {mismatched_identity}\n\n")

        handle.write("## Gate logic\n\n")
        handle.write("### Domain checks\n\n")
        handle.write("- Domain_Status == ELIGIBLE\n")
        handle.write("- Promotion_Action == ELIGIBLE_FOR_PROMOTION_GATE\n")
        handle.write("- Resolution_Status == AUTO_RESOLVED_REVIEW_REQUIRED\n")
        handle.write("- Scale_State == RESOLVED\n")
        handle.write("- Plausibility == PASS\n")
        handle.write("- Lineage in {PCIP11, CVBI11 -> PCIP11}\n\n")

        handle.write("### Temporal checks\n\n")
        handle.write("- Temporal_Gate == PASS\n")
        handle.write("- Temporal_Status == RESOLVED\n")
        handle.write("- Temporal_Confidence == HIGH\n")
        handle.write("- Resolved_Period present\n")
        handle.write("- PDF_Status == YES\n\n")

        handle.write("## Final PASS periods\n\n")
        for period, count in sorted(period_counts.items()):
            handle.write(f"- {period}: {count}\n")

        handle.write("\n## Lineage\n\n")
        for lineage, count in sorted(lineage_counts.items()):
            handle.write(f"- {lineage or '(blank)'}: {count}\n")

        handle.write("\n## Blocked reasons\n\n")
        if reason_counts:
            for reason, count in reason_counts.most_common():
                handle.write(f"- {reason}: {count}\n")
        else:
            handle.write("- None\n")

        handle.write("\n## Authorization boundary\n\n")
        handle.write("- Metric persistence: NOT GRANTED\n")
        handle.write("- KnowledgeBridge write: NOT GRANTED\n")
        handle.write("- Vault write: NOT GRANTED\n")
        handle.write("- Legacy artifacts modified: NO\n")

    print("0695.7 FINAL PROMOTION GATE R1")
    print("=" * 100)
    print(f"Domain rows evaluated       : {len(domain_rows)}")
    print(f"Temporal rows available     : {len(temporal_rows)}")
    print(f"FINAL PASS                  : {final_counts.get('PASS', 0)}")
    print(f"FINAL BLOCKED               : {final_counts.get('BLOCKED', 0)}")
    print(f"Missing temporal match      : {missing_temporal}")
    print(f"Cross-layer identity mismatch: {mismatched_identity}")
    print(f"CSV                         : {OUTPUT_CSV}")
    print(f"MD                          : {OUTPUT_MD}")
    print("Metric persistence          : NOT GRANTED")
    print("KnowledgeBridge write       : NOT GRANTED")
    print("Vault changed               : NO")


if __name__ == "__main__":
    configure_utf8()
    main()
