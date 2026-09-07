from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

INPUT_R2 = REPORTS / "PCIP11_0695_7_TEMPORAL_RESOLUTION_R2.csv"
INPUT_AUDIT = REPORTS / "PCIP11_0695_7_TEMPORAL_AUDIT_R1.csv"

OUTPUT_CSV = REPORTS / "PCIP11_0695_7_TEMPORAL_VALIDATION_GATE_R1.csv"
OUTPUT_MD = REPORTS / "PCIP11_0695_7_TEMPORAL_VALIDATION_GATE_R1.md"


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


def main() -> None:
    if not INPUT_R2.exists():
        raise FileNotFoundError(INPUT_R2)
    if not INPUT_AUDIT.exists():
        raise FileNotFoundError(INPUT_AUDIT)

    rows = read_csv(INPUT_R2)
    audit_rows = read_csv(INPUT_AUDIT)

    audit_by_sha = {get(row, "SHA256"): row for row in audit_rows if get(row, "SHA256")}

    output_rows = []

    for row in rows:
        sha = get(row, "SHA256")
        audit = audit_by_sha.get(sha, {})

        checks = {
            "status_resolved": get(row, "Temporal_Status") == "RESOLVED",
            "confidence_high": get(row, "Temporal_Confidence") == "HIGH",
            "resolved_period_present": bool(get(row, "Resolved_Period")),
            "pdf_extracted": get(row, "PDF_Status") == "YES",
            "legacy_period_suspect": get(row, "Current_Period_Suspect") == "YES",
            "physical_document_audit_pass": get(audit, "Audit_Overall") == "PASS",
            "same_period_per_physical_document":
                get(audit, "same_resolved_period_per_sha") == "PASS",
            "no_physical_period_conflict":
                get(audit, "same_resolved_period_per_sha") == "PASS",
            "not_legacy_2003_as_resolved":
                get(row, "Resolved_Period") != "2003-12",
        }

        passed = all(checks.values())
        reasons = []

        for name, ok in checks.items():
            if not ok:
                reasons.append(name)

        output_rows.append({
            **row,
            "Temporal_Gate": "PASS" if passed else "BLOCKED",
            "Temporal_Gate_Reason": (
                "ALL_TEMPORAL_CHECKS_PASS" if passed
                else "|".join(reasons)
            ),
            "Temporal_Promotion_Authorization": (
                "TEMPORAL_PASS_ONLY" if passed else "DENIED"
            ),
        })

    fieldnames = list(output_rows[0].keys()) if output_rows else []
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    gate_counts = Counter(get(row, "Temporal_Gate") for row in output_rows)
    reason_counts = Counter(
        get(row, "Temporal_Gate_Reason")
        for row in output_rows
        if get(row, "Temporal_Gate") != "PASS"
    )

    with OUTPUT_MD.open("w", encoding="utf-8") as handle:
        handle.write("# 0695.7 Temporal Validation Gate R1\n\n")
        handle.write(
            "Read-only temporal gate. PASS means temporal evidence is "
            "sufficient for the next pipeline stage. It does not authorize "
            "metric persistence, KnowledgeBridge writes, or Vault writes.\n\n"
        )

        handle.write("## Summary\n\n")
        handle.write(f"- Input metric rows: {len(rows)}\n")
        handle.write(f"- PASS: {gate_counts.get('PASS', 0)}\n")
        handle.write(f"- BLOCKED: {gate_counts.get('BLOCKED', 0)}\n\n")

        handle.write("## Gate conditions\n\n")
        handle.write("- Temporal_Status == RESOLVED\n")
        handle.write("- Temporal_Confidence == HIGH\n")
        handle.write("- Resolved_Period is present\n")
        handle.write("- PDF_Status == YES\n")
        handle.write("- Current_Period_Suspect == YES (legacy anomaly explicitly quarantined)\n")
        handle.write("- Physical document audit == PASS\n")
        handle.write("- No conflicting resolved period within a physical document\n")
        handle.write("- Resolved_Period != 2003-12\n\n")

        handle.write("## Blocked reasons\n\n")
        if reason_counts:
            for reason, count in reason_counts.most_common():
                handle.write(f"- {reason}: {count}\n")
        else:
            handle.write("- None\n")

        handle.write("\n## Safety boundary\n\n")
        handle.write("- Temporal promotion authorization: TEMPORAL_PASS_ONLY\n")
        handle.write("- Metric promoted: NO\n")
        handle.write("- Vault changed: NO\n")
        handle.write("- KnowledgeBridge write: NO\n")
        handle.write("- This gate does not alter legacy periods.\n")

    print("0695.7 TEMPORAL VALIDATION GATE R1")
    print("=" * 100)
    print(f"Metric rows evaluated     : {len(rows)}")
    print(f"PASS                      : {gate_counts.get('PASS', 0)}")
    print(f"BLOCKED                   : {gate_counts.get('BLOCKED', 0)}")
    print(f"CSV                       : {OUTPUT_CSV}")
    print(f"MD                        : {OUTPUT_MD}")
    print("Metric promoted           : NO")
    print("Vault changed             : NO")
    print("KnowledgeBridge write     : NO")
    print("Temporal authorization    : TEMPORAL_PASS_ONLY")


if __name__ == "__main__":
    configure_utf8()
    main()
