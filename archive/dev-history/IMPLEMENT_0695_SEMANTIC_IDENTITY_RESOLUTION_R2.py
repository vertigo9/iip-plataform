import csv
import hashlib
import re
from collections import defaultdict, Counter
from pathlib import Path

REPORTS_DIR = Path("reports")
INPUT = REPORTS_DIR / "0695_GENERIC_METRIC_PERSISTENCE_DRY_RUN_R1.csv"
OUTPUT_CSV = REPORTS_DIR / "0695_GENERIC_METRIC_SEMANTIC_IDENTITY_RESOLUTION_R2.csv"
OUTPUT_MD = REPORTS_DIR / "0695_GENERIC_METRIC_SEMANTIC_IDENTITY_RESOLUTION_R2.md"

TEXT_COLUMNS = {
    "Relevant_Facts",
    "Evidence_Text",
    "Relevant_Fact",
    "Evidence",
    "Source_Context",
    "Source_Text",
    "Context",
}

# Generic semantic vocabulary. These are dimensions, not ticker-specific rules.
DIMENSION_PATTERNS = {
    "MARKET_VALUE": [
        r"\bvalor\s+de\s+mercado\b",
        r"\bpelo\s+valor\s+do\s+mercado\b",
        r"\bcota\s+mercado\b",
        r"\bmarket\s+value\b",
        r"\bmarket\s+price\b",
    ],
    "NAV": [
        r"\bvalor\s+patrimonial\b",
        r"\bcota\s+patrimonial\b",
        r"\bpatrim[oô]nio\s+l[ií]quido\b",
        r"\bnav\b",
        r"\bnet\s+asset\s+value\b",
    ],
    "LTM": [
        r"\bdividend\s+yield\s+ltm\b",
        r"\byield\s+ltm\b",
        r"\bltm\b",
    ],
}

def clean(value):
    return (value or "").strip()

def normalize_text(value):
    text = clean(value).lower()
    # Normalize common mojibake enough for semantic matching, without changing
    # the original evidence stored in output.
    replacements = {
        "ð": "d",
        "÷": "o",
        "ú": "u",
        "í": "i",
        "Ý": "i",
        "├": "",
        "º": "",
        "Ô": "o",
        "Ã": "",
        "§": "a",
        "╣": "",
        "╬": "",
        "┌": "",
        "└": "",
    }
    for src, dst in replacements.items():
        text = text.replace(src.lower(), dst)
    return text

def stable_hash(payload):
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]

def load_csv(path):
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []

def semantic_dimensions(text):
    normalized = normalize_text(text)
    found = []
    for dimension, patterns in DIMENSION_PATTERNS.items():
        if any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns):
            found.append(dimension)
    return sorted(set(found))

def source_identity(row):
    return (
        clean(row.get("SHA256")),
        clean(row.get("Canonical_Ticker")) or clean(row.get("Original_Ticker")),
        clean(row.get("Metric")),
        clean(row.get("Resolved_Period")),
    )

def collect_source_context(target_rows):
    """
    Search existing 0695 reports for the same SHA/ticker/metric/period and
    collect textual evidence around the candidate value. No external data and
    no synthetic semantic labels are introduced.
    """
    targets = {
        source_identity(row)
        for row in target_rows
        if clean(row.get("SHA256")) and clean(row.get("Metric"))
    }

    context_by_identity = defaultdict(list)

    report_paths = sorted(REPORTS_DIR.glob("*.csv"))
    for report_path in report_paths:
        # Do not recursively scan generated R2 output or unrelated transient files.
        if report_path.name == OUTPUT_CSV.name:
            continue

        rows = load_csv(report_path)
        if not rows:
            continue

        for row in rows:
            identity = source_identity(row)
            if identity not in targets:
                continue

            text_chunks = []
            for column in row.keys():
                if column in TEXT_COLUMNS:
                    value = clean(row.get(column))
                    if value:
                        text_chunks.append(value)

            if text_chunks:
                for text in text_chunks:
                    context_by_identity[identity].append({
                        "report": str(report_path),
                        "text": text,
                    })

    return context_by_identity

def make_observation_key(row, semantic_dimension):
    parts = [
        clean(row.get("Canonical_Ticker")),
        clean(row.get("Resolved_Period")),
        clean(row.get("Metric")),
        semantic_dimension or "NO_DIMENSION",
        clean(row.get("Value_Parsed")),
        clean(row.get("Resolved_Unit")),
        clean(row.get("Scale")),
        clean(row.get("SHA256")),
    ]
    return (
        f"obs:{clean(row.get('Canonical_Ticker'))}:"
        f"{clean(row.get('Resolved_Period'))}:"
        f"{clean(row.get('Metric'))}:"
        f"{stable_hash('|'.join(parts))}"
    )

def main():
    print("0695 SEMANTIC IDENTITY RESOLUTION R2")
    print("=" * 115)

    if not INPUT.exists():
        print(f"ERRO: arquivo não encontrado: {INPUT.resolve()}")
        return

    input_rows = load_csv(INPUT)
    print(f"Input rows: {len(input_rows)}")

    source_context = collect_source_context(input_rows)

    # Group at document + ticker + metric + resolved-period level.
    groups = defaultdict(list)
    for row in input_rows:
        groups[source_identity(row)].append(row)

    results = []
    classification_counts = Counter()
    identity_counts = Counter()
    dimension_counts = Counter()
    collision_preview = defaultdict(list)

    for row in input_rows:
        identity = source_identity(row)
        siblings = groups[identity]

        # Gather all known textual evidence for this source identity.
        evidence_items = source_context.get(identity, [])
        all_text = "\n".join(item["text"] for item in evidence_items)

        dimensions = semantic_dimensions(all_text)
        semantic_dimension = dimensions[0] if len(dimensions) == 1 else ""

        # IMPORTANT:
        # Multiple dimensions in one broad text block are not enough to assign
        # a dimension to a particular numeric candidate. Therefore such a case
        # remains unresolved rather than being guessed.
        if len(dimensions) > 1:
            semantic_status = "REVIEW_REQUIRED"
            semantic_reason = "multiple_semantic_dimensions_found_in_source_context"
        elif len(dimensions) == 1:
            semantic_status = "RESOLVED"
            semantic_reason = "explicit_semantic_dimension_found_in_existing_source_evidence"
        else:
            semantic_status = "NOT_FOUND"
            semantic_reason = "no_explicit_semantic_dimension_found_in_existing_source_evidence"

        values = {clean(r.get("Value_Parsed")) for r in siblings}

        if len(siblings) == 1:
            classification = "UNIQUE"

            if clean(row.get("Metric")) in {"dividend_yield_annualized"} and semantic_status == "REVIEW_REQUIRED":
                identity_status = "BLOCKED_SEMANTIC_IDENTITY"
            elif clean(row.get("Metric")) in {"dividend_yield_annualized"} and semantic_status == "NOT_FOUND":
                identity_status = "REVIEW_REQUIRED"
            else:
                identity_status = "IDENTITY_READY"

        elif len(values) == 1:
            classification = "EXACT_DUPLICATE"
            # Same source, same metric, same period, same value.
            # Keep exactly one canonical identity; persistence layer must handle
            # repeated occurrences idempotently.
            identity_status = "DEDUPLICABLE"
            semantic_dimension = semantic_dimension or "NO_DIMENSION"

        else:
            classification = "SEMANTICALLY_DISTINCT_CANDIDATES"

            # Do not block the entire group. Each value is examined independently.
            # The identity is ready only when the source evidence can provide
            # exactly one semantic dimension.
            if semantic_status == "RESOLVED":
                identity_status = "IDENTITY_READY_WITH_DIMENSION"
            else:
                identity_status = "BLOCKED_SEMANTIC_IDENTITY"

        # Preserve exact original value and provenance in the observation key.
        observation_key = make_observation_key(row, semantic_dimension)

        out = dict(row)
        out["Semantic_Dimension"] = semantic_dimension
        out["Semantic_Dimension_Status"] = semantic_status
        out["Semantic_Dimension_Reason"] = semantic_reason
        out["Semantic_Dimensions_Found"] = "|".join(dimensions)
        out["Source_Evidence_Hits"] = str(len(evidence_items))
        out["Source_Evidence_Reports"] = "|".join(sorted({
            item["report"] for item in evidence_items
        }))
        out["Identity_Classification"] = classification
        out["Observation_Key_R2"] = observation_key
        out["Identity_Status_R2"] = identity_status
        out["Original_Metric_Evidence_ID"] = clean(row.get("Metric_Evidence_ID"))
        out["Original_Knowledge_Evidence_ID"] = clean(row.get("Knowledge_Evidence_ID"))

        results.append(out)
        classification_counts[classification] += 1
        identity_counts[identity_status] += 1

        dimension_counts[semantic_dimension or "(blank)"] += 1
        collision_preview[observation_key].append(out)

    collisions = {
        key: rows for key, rows in collision_preview.items()
        if key and len(rows) > 1
    }

    # Write CSV.
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    base_fields = list(input_rows[0].keys()) if input_rows else []
    extra_fields = [
        "Semantic_Dimension",
        "Semantic_Dimension_Status",
        "Semantic_Dimension_Reason",
        "Semantic_Dimensions_Found",
        "Source_Evidence_Hits",
        "Source_Evidence_Reports",
        "Identity_Classification",
        "Observation_Key_R2",
        "Identity_Status_R2",
        "Original_Metric_Evidence_ID",
        "Original_Knowledge_Evidence_ID",
    ]

    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=base_fields + extra_fields)
        writer.writeheader()
        writer.writerows(results)

    print("\nIDENTITY CLASSIFICATION")
    print("-" * 115)
    for key in (
        "UNIQUE",
        "EXACT_DUPLICATE",
        "SEMANTICALLY_DISTINCT_CANDIDATES",
    ):
        print(f"{key:40}: {classification_counts[key]}")

    print("\nIDENTITY STATUS")
    print("-" * 115)
    for key, count in identity_counts.most_common():
        print(f"{key:40}: {count}")

    print("\nSEMANTIC DIMENSIONS")
    print("-" * 115)
    for key, count in dimension_counts.most_common():
        print(f"{key:40}: {count}")

    print("\nOBSERVATION KEY COLLISIONS")
    print("-" * 115)
    print(f"Colliding keys: {len(collisions)}")
    for key, rows in collisions.items():
        print(f"\nKEY: {key}")
        for row in rows:
            print(
                f"  Row={clean(row.get('Row'))} | "
                f"value={clean(row.get('Value_Parsed'))} | "
                f"dimension={clean(row.get('Semantic_Dimension')) or '(blank)'} | "
                f"status={clean(row.get('Identity_Status_R2'))}"
            )

    print("\nREPEATED SOURCE GROUPS")
    print("-" * 115)
    repeated_groups = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"Repeated groups: {len(repeated_groups)}")

    for idx, (identity, siblings) in enumerate(repeated_groups.items(), 1):
        print(f"\nGROUP {idx}")
        print(f"SHA256={identity[0]}")
        print(f"Ticker={identity[1]}")
        print(f"Metric={identity[2]}")
        print(f"Period={identity[3]}")
        for row in siblings:
            print(
                f"  Row={clean(row.get('Row'))} | "
                f"value={clean(row.get('Value_Parsed'))} | "
                f"classification={clean(row.get('Identity_Classification'))} | "
                f"dimension={clean(row.get('Semantic_Dimension')) or '(blank)'} | "
                f"status={clean(row.get('Identity_Status_R2'))}"
            )

    md = [
        "# 0695 Semantic Identity Resolution R2",
        "",
        f"- Input rows: **{len(input_rows)}**",
        f"- Reports searched for source context: **{len(list(REPORTS_DIR.glob('*.csv')))}**",
        "",
        "## Identity classification",
    ]

    for key in (
        "UNIQUE",
        "EXACT_DUPLICATE",
        "SEMANTICALLY_DISTINCT_CANDIDATES",
    ):
        md.append(f"- `{key}`: **{classification_counts[key]}**")

    md.extend(["", "## Identity status"])
    for key, count in identity_counts.most_common():
        md.append(f"- `{key}`: **{count}**")

    md.extend(["", "## Semantic dimensions"])
    for key, count in dimension_counts.most_common():
        md.append(f"- `{key}`: **{count}**")

    md.extend([
        "",
        "## Repeated source groups",
    ])

    if not repeated_groups:
        md.append("- None")
    else:
        for idx, (identity, siblings) in enumerate(repeated_groups.items(), 1):
            md.append(f"### Group {idx}")
            md.append(f"- SHA256: `{identity[0]}`")
            md.append(f"- Ticker: `{identity[1]}`")
            md.append(f"- Metric: `{identity[2]}`")
            md.append(f"- Period: `{identity[3]}`")
            for row in siblings:
                md.append(
                    f"- Row `{clean(row.get('Row'))}` | "
                    f"value `{clean(row.get('Value_Parsed'))}` | "
                    f"classification `{clean(row.get('Identity_Classification'))}` | "
                    f"dimension `{clean(row.get('Semantic_Dimension'))}` | "
                    f"status `{clean(row.get('Identity_Status_R2'))}`"
                )

    md.extend([
        "",
        "## Safety",
        "",
        "- No existing source report was modified.",
        "- Metric persistence: **NOT EXECUTED**.",
        "- KnowledgeBridge: **NOT EXECUTED**.",
        "- Vault: **NOT CHANGED**.",
        "- No numeric value was selected or discarded automatically.",
        "- Exact duplicates are marked as deduplicable; semantically unresolved observations remain blocked.",
    ])

    OUTPUT_MD.write_text("\n".join(md), encoding="utf-8")

    print(f"\nCSV: {OUTPUT_CSV.resolve()}")
    print(f"MD : {OUTPUT_MD.resolve()}")
    print("Metric persistence      : NO")
    print("KnowledgeBridge         : NO")
    print("Vault changed           : NO")

if __name__ == "__main__":
    main()
