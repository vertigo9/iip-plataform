import csv
import hashlib
from collections import defaultdict, Counter
from pathlib import Path

INPUT = Path(r"reports\0695_GENERIC_METRIC_PERSISTENCE_DRY_RUN_R1.csv")
OUTPUT_CSV = Path(r"reports\0695_GENERIC_METRIC_SEMANTIC_IDENTITY_RESOLUTION_R1.csv")
OUTPUT_MD = Path(r"reports\0695_GENERIC_METRIC_SEMANTIC_IDENTITY_RESOLUTION_R1.md")

KNOWN_AMBIGUOUS_METRICS = {
    "dividend_yield_annualized",
}

def clean(value):
    return (value or "").strip()

def norm_ticker(row):
    return clean(row.get("Canonical_Ticker"))

def source_key(row):
    return (
        clean(row.get("SHA256")),
        norm_ticker(row),
        clean(row.get("Metric")),
        clean(row.get("Resolved_Period")),
    )

def semantic_basis_from_text(text):
    t = clean(text).lower()

    # Explicit semantic anchors already present in the historical evidence.
    if "pelo valor do mercado" in t or "valor de mercado" in t:
        return "MARKET_VALUE", "EXPLICIT_TEXT_ANCHOR"

    if "pelo valor patrimonial" in t or "valor patrimonial" in t:
        return "NAV", "EXPLICIT_TEXT_ANCHOR"

    if "ltm" in t:
        return "LTM", "EXPLICIT_TEXT_ANCHOR"

    return None, None

def stable_hash(payload):
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]

def build_observation_key(row, semantic_dimension):
    ticker = norm_ticker(row)
    period = clean(row.get("Resolved_Period"))
    metric = clean(row.get("Metric"))
    value = clean(row.get("Value_Parsed"))
    unit = clean(row.get("Resolved_Unit"))
    scale = clean(row.get("Scale"))
    sha = clean(row.get("SHA256"))

    # IMPORTANT:
    # SHA is part of the source provenance, not the semantic identity by itself.
    # Semantic identity includes the resolved dimension when one exists.
    base = "|".join([
        ticker,
        period,
        metric,
        semantic_dimension or "NO_SEMANTIC_DIMENSION",
        value,
        unit,
        scale,
        sha,
    ])
    return f"obs:{ticker}:{period}:{metric}:{stable_hash(base)}"

def main():
    print("0695 SEMANTIC IDENTITY RESOLUTION R1")
    print("=" * 110)

    if not INPUT.exists():
        print(f"ERRO: arquivo não encontrado: {INPUT.resolve()}")
        return

    with INPUT.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    print(f"Input rows: {len(rows)}")

    groups = defaultdict(list)
    for row in rows:
        groups[source_key(row)].append(row)

    output = []
    classification_counts = Counter()
    dimension_counts = Counter()
    blocked_identity = []

    for row in rows:
        group = groups[source_key(row)]
        metric = clean(row.get("Metric"))
        value = clean(row.get("Value_Parsed"))
        relevant_facts = clean(row.get("Relevant_Facts"))

        semantic_dimension = None
        semantic_dimension_status = "NOT_REQUIRED"
        semantic_reason = ""

        # First use explicit context contained in the candidate evidence itself.
        detected_dimension, detected_reason = semantic_basis_from_text(relevant_facts)
        if detected_dimension:
            semantic_dimension = detected_dimension
            semantic_dimension_status = "RESOLVED"
            semantic_reason = detected_reason

        # Unique observations do not require a semantic discriminator unless the
        # metric is known to be structurally ambiguous and the source context is absent.
        if len(group) == 1:
            classification = "UNIQUE"

            if metric in KNOWN_AMBIGUOUS_METRICS and not semantic_dimension:
                semantic_dimension_status = "REVIEW_REQUIRED"
                semantic_reason = "ambiguous_metric_without_explicit_semantic_dimension"
                identity_status = "BLOCKED_SEMANTIC_IDENTITY"
                blocked_identity.append(row)
            else:
                identity_status = "IDENTITY_READY"

        else:
            values = {clean(r.get("Value_Parsed")) for r in group}
            exact_same = len(values) == 1

            if exact_same:
                classification = "EXACT_DUPLICATE"
                # Exact duplicate does not require a new semantic dimension.
                if not semantic_dimension:
                    semantic_dimension = "NO_SEMANTIC_DIMENSION"
                identity_status = "DEDUPLICABLE"
                semantic_dimension_status = (
                    "RESOLVED" if semantic_dimension != "NO_SEMANTIC_DIMENSION"
                    else "NOT_REQUIRED"
                )
                if not semantic_reason:
                    semantic_reason = "same source, metric, period and value"

            else:
                classification = "SEMANTICALLY_DISTINCT_CANDIDATES"

                # For an ambiguous metric with multiple values, we must not
                # invent a basis. The current candidate report may not retain
                # the original source locator needed for a safe split.
                if metric in KNOWN_AMBIGUOUS_METRICS:
                    if semantic_dimension:
                        identity_status = "IDENTITY_READY_WITH_DIMENSION"
                    else:
                        identity_status = "BLOCKED_SEMANTIC_IDENTITY"
                        semantic_dimension_status = "REVIEW_REQUIRED"
                        semantic_reason = (
                            "multiple_values_for_same_metric_period_without_"
                            "explicit_semantic_dimension_in_candidate"
                        )
                        blocked_identity.append(row)
                else:
                    identity_status = "REVIEW_REQUIRED"

        observation_key = build_observation_key(row, semantic_dimension)

        out = dict(row)
        out["Semantic_Dimension"] = semantic_dimension or ""
        out["Semantic_Dimension_Status"] = semantic_dimension_status
        out["Semantic_Dimension_Reason"] = semantic_reason
        out["Identity_Classification"] = classification
        out["Observation_Key"] = observation_key
        out["Identity_Status"] = identity_status
        out["Original_Metric_Evidence_ID"] = clean(row.get("Metric_Evidence_ID"))
        out["Original_Knowledge_Evidence_ID"] = clean(row.get("Knowledge_Evidence_ID"))

        output.append(out)
        classification_counts[classification] += 1
        dimension_counts[semantic_dimension or "(blank)"] += 1

    # Recalculate collisions on the new observation key.
    key_groups = defaultdict(list)
    for row in output:
        key_groups[clean(row.get("Observation_Key"))].append(row)

    key_collisions = {
        key: items for key, items in key_groups.items()
        if key and len(items) > 1
    }

    # Write CSV.
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) + [
        "Semantic_Dimension",
        "Semantic_Dimension_Status",
        "Semantic_Dimension_Reason",
        "Identity_Classification",
        "Observation_Key",
        "Identity_Status",
        "Original_Metric_Evidence_ID",
        "Original_Knowledge_Evidence_ID",
    ]

    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output)

    # Console.
    print("\nIDENTITY CLASSIFICATION")
    print("-" * 110)
    for key in (
        "UNIQUE",
        "EXACT_DUPLICATE",
        "SEMANTICALLY_DISTINCT_CANDIDATES",
    ):
        print(f"{key:40}: {classification_counts[key]}")

    print("\nSEMANTIC DIMENSIONS")
    print("-" * 110)
    for key, count in dimension_counts.most_common():
        print(f"{key:40}: {count}")

    identity_counts = Counter(clean(r.get("Identity_Status")) for r in output)
    print("\nIDENTITY STATUS")
    print("-" * 110)
    for key, count in identity_counts.most_common():
        print(f"{key:40}: {count}")

    print("\nOBSERVATION KEY COLLISIONS")
    print("-" * 110)
    print(f"Colliding keys: {len(key_collisions)}")
    for key, items in key_collisions.items():
        print(f"\nKEY: {key}")
        for r in items:
            print(
                f"  Row={clean(r.get('Row'))} | "
                f"value={clean(r.get('Value_Parsed'))} | "
                f"dimension={clean(r.get('Semantic_Dimension'))} | "
                f"classification={clean(r.get('Identity_Classification'))}"
            )

    print("\nFOCUSED AMBIGUITY REVIEW")
    print("-" * 110)
    for row in output:
        if (
            clean(row.get("Metric")) == "dividend_yield_annualized"
            and clean(row.get("SHA256"))
            == "A2E7F14687B7025AE81F056A7EC24D75C06D6057E7F5EB8A73128BF4AD2E8B90"
        ):
            print(
                f"Row={clean(row.get('Row'))} | "
                f"value={clean(row.get('Value_Parsed'))} | "
                f"dimension={clean(row.get('Semantic_Dimension')) or '(blank)'} | "
                f"dimension_status={clean(row.get('Semantic_Dimension_Status'))} | "
                f"identity={clean(row.get('Identity_Status'))} | "
                f"reason={clean(row.get('Semantic_Dimension_Reason'))}"
            )

    # Markdown.
    md = [
        "# 0695 Semantic Identity Resolution R1",
        "",
        f"- Input rows: **{len(rows)}**",
        "",
        "## Classification",
    ]
    for key in (
        "UNIQUE",
        "EXACT_DUPLICATE",
        "SEMANTICALLY_DISTINCT_CANDIDATES",
    ):
        md.append(f"- `{key}`: **{classification_counts[key]}**")

    md.extend([
        "",
        "## Identity status",
    ])
    for key, count in identity_counts.most_common():
        md.append(f"- `{key}`: **{count}**")

    md.extend([
        "",
        "## Semantic dimensions",
    ])
    for key, count in dimension_counts.most_common():
        md.append(f"- `{key}`: **{count}**")

    md.extend([
        "",
        "## Observation key collisions",
        "",
        f"- Colliding keys: **{len(key_collisions)}**",
    ])

    if key_collisions:
        for key, items in key_collisions.items():
            md.append(f"### `{key}`")
            for r in items:
                md.append(
                    f"- Row `{clean(r.get('Row'))}` | "
                    f"value `{clean(r.get('Value_Parsed'))}` | "
                    f"dimension `{clean(r.get('Semantic_Dimension'))}` | "
                    f"identity `{clean(r.get('Identity_Status'))}`"
                )

    md.extend([
        "",
        "## Safety",
        "",
        "- Existing 0695 source reports were not modified.",
        "- Metric persistence: **NOT EXECUTED**.",
        "- KnowledgeBridge: **NOT EXECUTED**.",
        "- Vault: **NOT CHANGED**.",
        "- No automatic value selection was performed for semantically distinct observations.",
    ])

    OUTPUT_MD.write_text("\n".join(md), encoding="utf-8")

    print(f"\nCSV: {OUTPUT_CSV.resolve()}")
    print(f"MD : {OUTPUT_MD.resolve()}")
    print("Metric persistence      : NO")
    print("KnowledgeBridge         : NO")
    print("Vault changed           : NO")

if __name__ == "__main__":
    main()
