from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

INPUT_R2 = REPORTS / "PCIP11_0695_7_TEMPORAL_RESOLUTION_R2.csv"
OUTPUT_AUDIT_CSV = REPORTS / "PCIP11_0695_7_TEMPORAL_AUDIT_R1.csv"
OUTPUT_AUDIT_MD = REPORTS / "PCIP11_0695_7_TEMPORAL_AUDIT_R1.md"


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

    rows = read_csv(INPUT_R2)

    # Audit invariant 1: one resolved period per SHA.
    by_sha: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_sha[get(row, "SHA256")].append(row)

    audit_rows: list[dict[str, str]] = []
    sha_conflicts = []

    for sha, group in sorted(by_sha.items()):
        periods = sorted({get(row, "Resolved_Period") for row in group if get(row, "Resolved_Period")})
        statuses = sorted({get(row, "Temporal_Status") for row in group})
        confidences = sorted({get(row, "Temporal_Confidence") for row in group})
        reasons = sorted({get(row, "Temporal_Reason") for row in group})
        pdf_statuses = sorted({get(row, "PDF_Status") for row in group})

        conflict = len(periods) > 1
        if conflict:
            sha_conflicts.append(sha)

        first = group[0]

        checks = {
            "same_resolved_period_per_sha": "PASS" if len(periods) <= 1 else "FAIL",
            "same_status_per_sha": "PASS" if len(statuses) <= 1 else "FAIL",
            "same_confidence_per_sha": "PASS" if len(confidences) <= 1 else "FAIL",
            "all_pdf_extracted": "PASS" if pdf_statuses == ["YES"] else "FAIL",
            "all_resolved": "PASS" if statuses == ["RESOLVED"] else "FAIL",
            "no_blank_resolved_period": "PASS" if periods and "" not in periods else "FAIL",
            "legacy_period_preserved": "PASS" if get(first, "Current_Period_Legacy") else "FAIL",
            "legacy_period_flagged_suspect": "PASS"
                if get(first, "Current_Period_Suspect") == "YES" else "FAIL",
        }

        overall = "PASS" if all(v == "PASS" for v in checks.values()) else "FAIL"

        audit_rows.append({
            "SHA256": sha,
            "FileName": get(first, "FileName"),
            "PDF_Path": get(first, "PDF_Path"),
            "Metric_Count": str(len(group)),
            "Metrics": "|".join(sorted({get(r, "Metric") for r in group if get(r, "Metric")})),
            "Resolved_Periods": "|".join(periods),
            "Temporal_Statuses": "|".join(statuses),
            "Temporal_Confidences": "|".join(confidences),
            "Temporal_Reasons": "|".join(reasons),
            "PDF_Statuses": "|".join(pdf_statuses),
            "Audit_Overall": overall,
            **checks,
        })

    fieldnames = list(audit_rows[0].keys()) if audit_rows else []
    with OUTPUT_AUDIT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(audit_rows)

    overall_counts = Counter(row["Audit_Overall"] for row in audit_rows)
    check_failures = Counter()
    for row in audit_rows:
        for key, value in row.items():
            if key.startswith("same_") or key in (
                "all_pdf_extracted",
                "all_resolved",
                "no_blank_resolved_period",
                "legacy_period_preserved",
                "legacy_period_flagged_suspect",
            ):
                if value == "FAIL":
                    check_failures[key] += 1

    period_counts = Counter()
    for row in rows:
        period = get(row, "Resolved_Period")
        if period:
            period_counts[period] += 1

    with OUTPUT_AUDIT_MD.open("w", encoding="utf-8") as handle:
        handle.write("# 0695.7 Temporal Audit R1\n\n")
        handle.write(
            "Read-only audit over the R2 temporal-resolution output. "
            "No Vault write and no metric promotion.\n\n"
        )

        handle.write("## Scope\n\n")
        handle.write(f"- Candidate metric rows: {len(rows)}\n")
        handle.write(f"- Physical documents (unique SHA256): {len(by_sha)}\n")
        handle.write(f"- Audit PASS: {overall_counts.get('PASS', 0)}\n")
        handle.write(f"- Audit FAIL: {overall_counts.get('FAIL', 0)}\n")
        handle.write(f"- SHA period conflicts: {len(sha_conflicts)}\n\n")

        handle.write("## Resolved periods by metric row\n\n")
        for period, count in sorted(period_counts.items()):
            handle.write(f"- {period}: {count}\n")

        handle.write("\n## Failed checks\n\n")
        if check_failures:
            for name, count in check_failures.most_common():
                handle.write(f"- {name}: {count}\n")
        else:
            handle.write("- None\n")

        handle.write("\n## Physical documents audited\n\n")
        for row in audit_rows:
            handle.write(
                f"- {row['SHA256']} | {row['FileName']} | "
                f"metrics={row['Metric_Count']} | periods={row['Resolved_Periods']} | "
                f"overall={row['Audit_Overall']}\n"
            )

        handle.write("\n## Safety\n\n")
        handle.write("- Vault changed: NO\n")
        handle.write("- Metric promoted: NO\n")
        handle.write("- Legacy artifacts modified: NO\n")

    print("0695.7 TEMPORAL AUDIT R1")
    print("=" * 100)
    print(f"Metric rows audited     : {len(rows)}")
    print(f"Physical documents      : {len(by_sha)}")
    print(f"Audit PASS              : {overall_counts.get('PASS', 0)}")
    print(f"Audit FAIL              : {overall_counts.get('FAIL', 0)}")
    print(f"SHA period conflicts    : {len(sha_conflicts)}")
    print(f"CSV                     : {OUTPUT_AUDIT_CSV}")
    print(f"MD                      : {OUTPUT_AUDIT_MD}")
    print("Vault changed           : NO")
    print("Metric promoted         : NO")


if __name__ == "__main__":
    configure_utf8()
    main()
