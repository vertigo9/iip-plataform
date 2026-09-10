import csv
import hashlib
import re
from collections import defaultdict, Counter
from pathlib import Path

REPORTS_DIR = Path("reports")
INPUT = REPORTS_DIR / "0695_GENERIC_METRIC_PERSISTENCE_DRY_RUN_R1.csv"
OUTPUT_CSV = REPORTS_DIR / "0695_GENERIC_METRIC_SEMANTIC_IDENTITY_RESOLUTION_R4.csv"
OUTPUT_MD = REPORTS_DIR / "0695_GENERIC_METRIC_SEMANTIC_IDENTITY_RESOLUTION_R4.md"

# Generic semantic dimensions. They describe a basis/context of a metric.
DIMENSION_PATTERNS = {
    "MARKET_VALUE": [
        r"dividend\s+yield\s+anualizado\s+pelo\s+valor\s+do\s+mercado",
        r"dividend\s+yield\s+anualizado.*?valor\s+de\s+mercado",
        r"pelo\s+valor\s+do\s+mercado",
        r"valor\s+de\s+mercado",
        r"cota\s+mercado",
        r"market\s+value",
        r"market\s+price",
    ],
    "NAV": [
        r"dividend\s+yield\s+anualizado\s+pelo\s+valor\s+patrimonial",
        r"dividend\s+yield\s+anualizado.*?valor\s+patrimonial",
        r"pelo\s+valor\s+patrimonial",
        r"valor\s+patrimonial",
        r"cota\s+patrimonial",
        r"net\s+asset\s+value",
        r"\bnav\b",
    ],
    "LTM": [
        r"dividend\s+yield\s+ltm",
        r"yield\s+ltm",
        r"\bltm\b",
    ],
}

TEXT_COLUMNS = [
    "Relevant_Facts",
    "Evidence_Text",
    "Evidence",
    "Relevant_Fact",
    "Source_Context",
    "Source_Text",
    "Context",
]

def clean(value):
    return (value or "").strip()

def load_csv(path):
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []

def norm(text):
    text = clean(text).lower()
    # Minimal normalization of frequent extraction mojibake.
    replacements = {
        "ÿ": "i", "ý": "i", "í": "i",
        "ù": "u", "ú": "u",
        "ã": "a", "õ": "o", "ç": "c",
        "ô": "o", "ó": "o",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return re.sub(r"\s+", " ", text)

def value_variants(raw_value, parsed_value):
    variants = set()

    for raw in (clean(raw_value), clean(parsed_value)):
        if not raw:
            continue
        variants.add(norm(raw))

    p = clean(parsed_value)
    if p:
        variants.add(norm(p.replace(".", ",")))

    return {v for v in variants if v}

def dimensions_in_text(text):
    text = norm(text)
    found = []
    for dimension, patterns in DIMENSION_PATTERNS.items():
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
            found.append(dimension)
    return sorted(set(found))

def source_match_key(row):
    # Candidate source group identity includes the resolved period.
    # Historical context lookup elsewhere intentionally uses SHA256 + Metric,
    # so Legacy_Period and Resolved_Period can be reconciled across layers.
    sha = clean(row.get("SHA256"))
    ticker = clean(row.get("Canonical_Ticker")) or clean(row.get("Original_Ticker"))
    metric = clean(row.get("Metric"))
    period = clean(row.get("Resolved_Period"))
    return sha, ticker, metric, period

def candidate_source_context_keys(row):
    """
    Context join deliberately excludes resolved period because historical
    0695 rows can still contain Legacy_Period while the Final Gate contains
    the corrected Resolved_Period.
    """
    sha = clean(row.get("SHA256"))
    metric = clean(row.get("Metric"))
    ticker = clean(row.get("Canonical_Ticker"))
    original_ticker = clean(row.get("Original_Ticker"))

    keys = {
        (sha, metric),
    }
    if ticker:
        keys.add((sha, metric, ticker))
    if original_ticker:
        keys.add((sha, metric, original_ticker))

    return keys

def row_texts(row):
    for field in TEXT_COLUMNS:
        value = clean(row.get(field))
        if value:
            yield field, value

def build_source_index(target_rows):
    target_pairs = set()
    for row in target_rows:
        sha = clean(row.get("SHA256"))
        metric = clean(row.get("Metric"))
        if sha and metric:
            target_pairs.add((sha, metric))

    index = defaultdict(list)

    for path in sorted(REPORTS_DIR.glob("*.csv")):
        if path.name in {
            OUTPUT_CSV.name,
            "0695_GENERIC_METRIC_SEMANTIC_IDENTITY_RESOLUTION_R1.csv",
            "0695_GENERIC_METRIC_SEMANTIC_IDENTITY_RESOLUTION_R2.csv",
            "0695_GENERIC_METRIC_SEMANTIC_IDENTITY_RESOLUTION_R3.csv",
            "0695_GENERIC_METRIC_SEMANTIC_IDENTITY_RESOLUTION_R4.csv",
        }:
            continue

        rows = load_csv(path)
        for row in rows:
            pair = (
                clean(row.get("SHA256")),
                clean(row.get("Metric")),
            )
            if pair not in target_pairs:
                continue

            for field, text in row_texts(row):
                index[pair].append({
                    "report": str(path),
                    "field": field,
                    "text": text,
                    "row": row,
                })

    return index

def local_contexts(text, variants):
    normalized = norm(text)
    snippets = []

    for value in variants:
        start = normalized.find(value)
        if start < 0:
            continue
        left = max(0, start - 240)
        right = min(len(normalized), start + len(value) + 320)
        snippets.append(normalized[left:right])

    # preserve order and remove exact duplicate snippets
    result = []
    seen = set()
    for snippet in snippets:
        if snippet not in seen:
            result.append(snippet)
            seen.add(snippet)
    return result

def resolve_value_dimension(row, source_index):
    pair = (
        clean(row.get("SHA256")),
        clean(row.get("Metric")),
    )
    variants = value_variants(row.get("Value_Raw"), row.get("Value_Parsed"))

    evidence = source_index.get(pair, [])
    local_evidence = []

    for item in evidence:
        for snippet in local_contexts(item["text"], variants):
            dims = dimensions_in_text(snippet)
            if dims:
                local_evidence.append({
                    "dimension": dims,
                    "report": item["report"],
                    "field": item["field"],
                    "snippet": snippet,
                })

    if not local_evidence:
        return "", "NOT_FOUND", "no_value_localized_semantic_context", []

    dimension_hits = Counter()
    for item in local_evidence:
        # One snippet can mention more than one dimension. Count each explicit
        # dimension independently.
        for dimension in item["dimension"]:
            dimension_hits[dimension] += 1

    ranked = dimension_hits.most_common()

    if len(ranked) == 1:
        return (
            ranked[0][0],
            "RESOLVED",
            "value_localized_explicit_semantic_context",
            local_evidence,
        )

    # A unique winner is acceptable when one dimension is strictly better
    # supported by the value-local context.
    if ranked[0][1] > ranked[1][1]:
        return (
            ranked[0][0],
            "RESOLVED",
            "value_localized_best_supported_context",
            local_evidence,
        )

    return (
        "",
        "REVIEW_REQUIRED",
        "multiple_semantic_dimensions_equally_supported_near_value",
        local_evidence,
    )

def stable_key(row, semantic_dimension):
    payload = "|".join([
        clean(row.get("Canonical_Ticker")),
        clean(row.get("Resolved_Period")),
        clean(row.get("Metric")),
        semantic_dimension or "NO_DIMENSION",
        clean(row.get("Value_Parsed")),
        clean(row.get("Resolved_Unit")),
        clean(row.get("Scale")),
        clean(row.get("SHA256")),
    ])
    return (
        f"obs:{clean(row.get('Canonical_Ticker'))}:"
        f"{clean(row.get('Resolved_Period'))}:"
        f"{clean(row.get('Metric'))}:"
        f"{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]}"
    )

def source_period_for_group(siblings):
    """Return the resolved period from the first row in a repeated source group."""
    if not siblings:
        return ""
    return clean(siblings[0].get("Resolved_Period"))

def main():
    print("0695 SEMANTIC IDENTITY RESOLUTION R4")
    print("=" * 115)

    if not INPUT.exists():
        print(f"ERRO: {INPUT.resolve()} não encontrado.")
        return

    rows = load_csv(INPUT)
    print(f"Input rows: {len(rows)}")

    source_index = build_source_index(rows)

    groups = defaultdict(list)
    for row in rows:
        groups[source_match_key(row)].append(row)

    results = []

    for row in rows:
        siblings = groups[source_match_key(row)]
        value_set = {clean(x.get("Value_Parsed")) for x in siblings}

        # Exact duplicate = same source + metric + resolved period + value.
        if len(siblings) > 1 and len(value_set) == 1:
            classification = "EXACT_DUPLICATE"
            dimension = ""
            dimension_status = "NOT_REQUIRED"
            dimension_reason = "same_source_same_metric_same_period_same_value"
            identity_status = "DEDUPLICABLE"
            local_hits = 0

        else:
            dimension, dimension_status, dimension_reason, local_evidence = (
                resolve_value_dimension(row, source_index)
            )
            local_hits = len(local_evidence)

            if len(siblings) == 1:
                classification = "UNIQUE"
                identity_status = (
                    "IDENTITY_READY"
                    if dimension_status == "RESOLVED"
                    else "REVIEW_REQUIRED"
                )
            else:
                classification = "SEMANTICALLY_DISTINCT_CANDIDATES"
                identity_status = (
                    "IDENTITY_READY_WITH_DIMENSION"
                    if dimension_status == "RESOLVED"
                    else "BLOCKED_SEMANTIC_IDENTITY"
                )

        out = dict(row)
        out["Semantic_Dimension_R4"] = dimension
        out["Semantic_Dimension_Status_R4"] = dimension_status
        out["Semantic_Dimension_Reason_R4"] = dimension_reason
        out["Semantic_Local_Context_Hits_R4"] = str(local_hits)
        out["Identity_Classification_R4"] = classification
        out["Observation_Key_R4"] = stable_key(row, dimension)
        out["Identity_Status_R4"] = identity_status
        out["Context_Join_Key_R4"] = (
            f"{clean(row.get('SHA256'))}|{clean(row.get('Metric'))}"
        )
        out["Legacy_Period_Preserved_R4"] = clean(row.get("Legacy_Period"))
        out["Resolved_Period_Preserved_R4"] = clean(row.get("Resolved_Period"))
        results.append(out)

    classifications = Counter(
        clean(r.get("Identity_Classification_R4")) for r in results
    )
    statuses = Counter(
        clean(r.get("Identity_Status_R4")) for r in results
    )
    dimensions = Counter(
        clean(r.get("Semantic_Dimension_R4")) or "(blank)"
        for r in results
    )

    collisions = defaultdict(list)
    for row in results:
        collisions[clean(row.get("Observation_Key_R4"))].append(row)

    collisions = {
        k: v for k, v in collisions.items()
        if k and len(v) > 1
    }

    print("\nIDENTITY CLASSIFICATION")
    print("-" * 115)
    for key in (
        "UNIQUE",
        "EXACT_DUPLICATE",
        "SEMANTICALLY_DISTINCT_CANDIDATES",
    ):
        print(f"{key:40}: {classifications[key]}")

    print("\nIDENTITY STATUS")
    print("-" * 115)
    for key, count in statuses.most_common():
        print(f"{key:40}: {count}")

    print("\nSEMANTIC DIMENSIONS")
    print("-" * 115)
    for key, count in dimensions.most_common():
        print(f"{key:40}: {count}")

    print("\nFOCUSED REVIEW")
    print("-" * 115)

    for identity, siblings in groups.items():
        if len(siblings) <= 1:
            continue

        print(
            f"\nSHA={identity[0]} | Ticker={identity[1]} | "
            f"Metric={identity[2]} | Period={source_period_for_group(siblings)}"
        )

        for row in results:
            if source_match_key(row) != identity:
                continue
            print(
                f"  Row={clean(row.get('Row'))} | "
                f"value={clean(row.get('Value_Parsed'))} | "
                f"classification={clean(row.get('Identity_Classification_R4'))} | "
                f"dimension={clean(row.get('Semantic_Dimension_R4')) or '(blank)'} | "
                f"dim_status={clean(row.get('Semantic_Dimension_Status_R4'))} | "
                f"identity={clean(row.get('Identity_Status_R4'))} | "
                f"hits={clean(row.get('Semantic_Local_Context_Hits_R4'))}"
            )

    print("\nOBSERVATION KEY COLLISIONS")
    print("-" * 115)
    print(f"Colliding keys: {len(collisions)}")
    for key, group in collisions.items():
        print(f"\nKEY: {key}")
        for row in group:
            print(
                f"  Row={clean(row.get('Row'))} | "
                f"value={clean(row.get('Value_Parsed'))} | "
                f"dimension={clean(row.get('Semantic_Dimension_R4')) or '(blank)'} | "
                f"status={clean(row.get('Identity_Status_R4'))}"
            )

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    base = list(rows[0].keys()) if rows else []
    extra = [
        "Semantic_Dimension_R4",
        "Semantic_Dimension_Status_R4",
        "Semantic_Dimension_Reason_R4",
        "Semantic_Local_Context_Hits_R4",
        "Identity_Classification_R4",
        "Observation_Key_R4",
        "Identity_Status_R4",
        "Context_Join_Key_R4",
        "Legacy_Period_Preserved_R4",
        "Resolved_Period_Preserved_R4",
    ]

    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=base + extra)
        writer.writeheader()
        writer.writerows(results)

    md = [
        "# 0695 Semantic Identity Resolution R4",
        "",
        f"- Input rows: **{len(rows)}**",
        "",
        "## Core correction",
        "",
        "- Historical context matching uses `SHA256 + Metric`.",
        "- `Resolved_Period` is deliberately excluded from the cross-layer context join.",
        "- `Legacy_Period` and `Resolved_Period` are both preserved.",
        "- Numeric values are never selected/discarded automatically.",
        "",
        "## Classification",
    ]

    for key in (
        "UNIQUE",
        "EXACT_DUPLICATE",
        "SEMANTICALLY_DISTINCT_CANDIDATES",
    ):
        md.append(f"- `{key}`: **{classifications[key]}**")

    md.extend(["", "## Identity status"])
    for key, count in statuses.most_common():
        md.append(f"- `{key}`: **{count}**")

    md.extend(["", "## Semantic dimensions"])
    for key, count in dimensions.most_common():
        md.append(f"- `{key}`: **{count}**")

    md.extend([
        "",
        "## Focused repeated groups",
    ])

    for identity, siblings in groups.items():
        if len(siblings) <= 1:
            continue
        md.append(
            f"### SHA `{identity[0]}` | Metric `{identity[2]}` | Period `{identity[3]}`"
        )
        for row in results:
            if source_match_key(row) != identity:
                continue
            md.append(
                f"- Row `{clean(row.get('Row'))}` | "
                f"value `{clean(row.get('Value_Parsed'))}` | "
                f"classification `{clean(row.get('Identity_Classification_R4'))}` | "
                f"dimension `{clean(row.get('Semantic_Dimension_R4'))}` | "
                f"dimension_status `{clean(row.get('Semantic_Dimension_Status_R4'))}` | "
                f"identity `{clean(row.get('Identity_Status_R4'))}` | "
                f"hits `{clean(row.get('Semantic_Local_Context_Hits_R4'))}`"
            )

    md.extend([
        "",
        "## Safety",
        "",
        "- No source report modified.",
        "- No metric persistence.",
        "- No KnowledgeBridge.",
        "- Vault unchanged.",
        "- No value was silently discarded.",
    ])

    OUTPUT_MD.write_text("\n".join(md), encoding="utf-8")

    print(f"\nCSV: {OUTPUT_CSV.resolve()}")
    print(f"MD : {OUTPUT_MD.resolve()}")
    print("Metric persistence      : NO")
    print("KnowledgeBridge         : NO")
    print("Vault changed           : NO")

if __name__ == "__main__":
    main()
