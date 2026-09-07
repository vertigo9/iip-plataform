from pathlib import Path
import csv
import hashlib
import re


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

INPUT_CANONICAL = REPORTS / "PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R3.csv"
INPUT_RESOLUTION = REPORTS / "PCIP11_0695_7_CONFLICT_RESOLUTION_R2.csv"

OUTPUT_CSV = REPORTS / "PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R4.csv"
OUTPUT_MD = REPORTS / "PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R4.md"


def normalize(value):
    if value is None:
        return ""
    return str(value).strip()


def truthy(value):
    return normalize(value).upper() in {
        "YES", "TRUE", "1"
    }


def semantic_key(row):
    return "|".join([
        normalize(row.get("Derived_Canonical_Ticker")),
        normalize(row.get("Resolved_Period")),
        normalize(row.get("Metric")),
        normalize(row.get("Resolved_Unit")),
        normalize(row.get("Scale")),
    ])


def make_observation_id(row):
    payload = "|".join([
        semantic_key(row),
        normalize(row.get("Value")),
        normalize(row.get("Source_SHA256")),
    ])
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"canonical:{digest}"


def main():

    print("0695.7 EVIDENCE CANONICALIZATION R4")
    print("=" * 88)

    with INPUT_CANONICAL.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:
        canonical_rows = list(csv.DictReader(f))

    with INPUT_RESOLUTION.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:
        resolution_rows = list(csv.DictReader(f))

    resolutions = {}

    for r in resolution_rows:

        if normalize(r.get("Resolution_Status")).upper() != "RESOLVED":
            continue

        if not truthy(r.get("Canonicalization_Eligible")):
            continue

        key = "|".join([
            normalize(r.get("Canonical_Ticker")),
            normalize(r.get("Resolved_Period")),
            normalize(r.get("Metric")),
            normalize(r.get("Resolved_Unit")),
            normalize(r.get("Scale")),
        ])

        resolutions[key] = r

    output_rows = []

    for row in canonical_rows:

        ticker = normalize(row.get("Derived_Canonical_Ticker"))

        if not ticker:
            lineage = normalize(row.get("Lineage"))
            if "->" in lineage:
                ticker = lineage.split("->")[-1].strip()

        key = "|".join([
            ticker,
            normalize(row.get("Resolved_Period")),
            normalize(row.get("Metric")),
            normalize(row.get("Resolved_Unit")),
            normalize(row.get("Scale")),
        ])

        resolution = resolutions.get(key)

        current_status = normalize(
            row.get("Canonicalization_Status")
        ).upper()

        if (
            current_status == "CONFLICT"
            and resolution is not None
        ):

            resolved_value = normalize(
                resolution.get("Resolved_Value")
            )

            row["Derived_Canonical_Ticker"] = ticker
            row["Value"] = resolved_value
            row["Resolved_Value"] = resolved_value

            row["Canonicalization_Status"] = "CANONICAL"
            row["Canonicalization_Reason"] = (
                "resolved_conflict_semantic_disambiguation"
            )

            row["Distinct_Value_Count"] = "1"
            row["Distinct_Values"] = resolved_value

            row["Persistence_Eligible"] = "YES"

            row["Resolution_Status"] = "RESOLVED"
            row["Resolution_Type"] = normalize(
                resolution.get("Resolution_Type")
            )
            row["Resolution_Evidence_SHA256"] = normalize(
                resolution.get("Evidence_SHA256")
            )
            row["Resolution_Selected_Context"] = normalize(
                resolution.get("Selected_Context")
            )
            row["Resolution_Rejected_Value"] = normalize(
                resolution.get("Rejected_Value")
            )

        elif current_status == "CANONICAL":

            row["Derived_Canonical_Ticker"] = ticker
            row["Persistence_Eligible"] = "YES"

        else:

            row["Persistence_Eligible"] = "NO"

        row["Canonical_Observation_ID"] = make_observation_id(row)

        output_rows.append(row)

    # Validation
    canonical_count = sum(
        1 for r in output_rows
        if normalize(r.get("Canonicalization_Status")).upper()
        == "CANONICAL"
    )

    conflict_count = sum(
        1 for r in output_rows
        if normalize(r.get("Canonicalization_Status")).upper()
        == "CONFLICT"
    )

    review_count = sum(
        1 for r in output_rows
        if normalize(r.get("Canonicalization_Status")).upper()
        == "REVIEW"
    )

    eligible_count = sum(
        1 for r in output_rows
        if truthy(r.get("Persistence_Eligible"))
    )

    incomplete_identity = sum(
        1 for r in output_rows
        if not all([
            normalize(r.get("Derived_Canonical_Ticker")),
            normalize(r.get("Resolved_Period")),
            normalize(r.get("Metric")),
            normalize(r.get("Resolved_Unit")),
            normalize(r.get("Scale")),
        ])
    )

    target = [
        r for r in output_rows
        if normalize(r.get("Derived_Canonical_Ticker")) == "PCIP11"
        and normalize(r.get("Resolved_Period")) == "2024-01"
        and normalize(r.get("Metric"))
        == "dividend_yield_annualized"
    ]

    # Preserve all existing columns and add R4 fields.
    fieldnames = []
    for r in output_rows:
        for k in r.keys():
            if k not in fieldnames:
                fieldnames.append(k)

    with OUTPUT_CSV.open(
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            extrasaction="ignore"
        )

        writer.writeheader()

        for row in output_rows:
            writer.writerow(row)

    with OUTPUT_MD.open(
        "w",
        encoding="utf-8"
    ) as f:

        f.write("# 0695.7 Evidence Canonicalization R4\n\n")
        f.write(
            "Propagation of an independently resolved semantic conflict "
            "into the canonical evidence layer.\n\n"
        )

        f.write("## Result\n\n")
        f.write(f"- Input R3 observations: {len(canonical_rows)}\n")
        f.write(f"- Output observations: {len(output_rows)}\n")
        f.write(f"- CANONICAL: {canonical_count}\n")
        f.write(f"- CONFLICT: {conflict_count}\n")
        f.write(f"- REVIEW: {review_count}\n")
        f.write(f"- Persistence eligible: {eligible_count}\n")
        f.write(f"- Incomplete identity: {incomplete_identity}\n\n")

        f.write("## Resolution propagation\n\n")

        if target:
            r = target[0]

            f.write(
                f"- Identity: "
                f"`{r.get('Derived_Canonical_Ticker')}|"
                f"{r.get('Resolved_Period')}|"
                f"{r.get('Metric')}|"
                f"{r.get('Resolved_Unit')}|"
                f"{r.get('Scale')}`\n"
            )

            f.write(
                f"- Value: `{r.get('Value')}`\n"
            )

            f.write(
                f"- Canonicalization status: "
                f"`{r.get('Canonicalization_Status')}`\n"
            )

            f.write(
                f"- Persistence eligible: "
                f"`{r.get('Persistence_Eligible')}`\n"
            )

            f.write(
                f"- Resolution type: "
                f"`{r.get('Resolution_Type', '')}`\n"
            )

            f.write(
                f"- Evidence SHA-256: "
                f"`{r.get('Resolution_Evidence_SHA256', '')}`\n"
            )

        f.write("\n## Safety\n\n")
        f.write("- Persistence executed: NO\n")
        f.write("- KnowledgeBridge executed: NO\n")
        f.write("- Vault changed: NO\n")

    print(f"R3 observations consumed   : {len(canonical_rows)}")
    print(f"Canonical observations      : {len(output_rows)}")
    print(f"CANONICAL / eligible       : {canonical_count}")
    print(f"CONFLICT / blocked         : {conflict_count}")
    print(f"REVIEW / blocked           : {review_count}")
    print(f"Incomplete identity rows   : {incomplete_identity}")

    if target:
        r = target[0]
        print()
        print("TARGET")
        print(f"Ticker                     : {r.get('Derived_Canonical_Ticker')}")
        print(f"Period                     : {r.get('Resolved_Period')}")
        print(f"Metric                     : {r.get('Metric')}")
        print(f"Resolved value             : {r.get('Value')}")
        print(f"Status                     : {r.get('Canonicalization_Status')}")
        print(f"Persistence eligible       : {r.get('Persistence_Eligible')}")

    print()
    print(f"CSV                        : {OUTPUT_CSV}")
    print(f"MD                         : {OUTPUT_MD}")
    print()
    print("Persistence executed       : NO")
    print("KnowledgeBridge executed   : NO")
    print("Vault changed              : NO")


if __name__ == "__main__":
    main()