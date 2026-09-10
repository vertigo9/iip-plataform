from __future__ import annotations

import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "reports"

INPUT_CSV = REPORTS / "IIP_HISTORICAL_IDENTITY_RECONSTRUCTION_R2.csv"
OUTPUT_CSV = REPORTS / "IIP_HISTORICAL_IDENTITY_RECONSTRUCTION_R3.csv"
OUTPUT_MD = REPORTS / "IIP_HISTORICAL_IDENTITY_RECONSTRUCTION_R3.md"


def clean(value):
    return str(value or "").strip()


def split_values(value):
    value = clean(value)

    if not value:
        return []

    for sep in ("|", ";", ","):
        if sep in value:
            return [item.strip() for item in value.split(sep) if item.strip()]

    return [value]


def unique(values):
    result = []
    seen = set()

    for value in values:
        value = clean(value)
        key = value.upper()

        if value and key not in seen:
            seen.add(key)
            result.append(value)

    return result


def normalize_cnpj(value):
    return "".join(c for c in clean(value) if c.isdigit())


def cnpj_key(cnpj):
    cnpj = normalize_cnpj(cnpj)

    if not cnpj:
        return ""

    return f"CNPJ:{cnpj}"


def stable_key(row):
    material = "|".join(
        [
            clean(row.get("source_file")),
            clean(row.get("source_row")),
            clean(row.get("tickers")),
            clean(row.get("cnpj")),
            clean(row.get("periods")),
        ]
    )

    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]

    return f"UNRESOLVED:{digest}"


def ticker_event_class(ticker):
    ticker = clean(ticker).upper()

    if not ticker:
        return "NONE"

    event_tokens = (
        "SUB",
        "DIR",
        "REC",
        "BNS",
        "BON",
        "UNT",
        "PRO",
        "EX",
    )

    if any(ticker.endswith(token) for token in event_tokens):
        return "POSSIBLE_EVENT_TICKER"

    return "NORMAL_TICKER"


def classify_cnpj_count(cnpjs):
    count = len(cnpjs)

    if count == 0:
        return "NO_CNPJ"

    if count == 1:
        return "SINGLE_CNPJ"

    return "MULTIPLE_CNPJ"


def analyze(row):
    tickers = unique(split_values(row.get("tickers")))

    cnpjs = unique(
        [
            normalize_cnpj(value)
            for value in split_values(row.get("cnpj"))
            if normalize_cnpj(value)
        ]
    )

    periods = unique(split_values(row.get("periods")))

    previous_identity = clean(row.get("identity_key"))

    canonical_ticker = clean(row.get("canonical_ticker"))

    event_tickers = [
        ticker
        for ticker in tickers
        if ticker_event_class(ticker) == "POSSIBLE_EVENT_TICKER"
    ]

    normal_tickers = [
        ticker for ticker in tickers if ticker_event_class(ticker) == "NORMAL_TICKER"
    ]

    cnpj_status = classify_cnpj_count(cnpjs)

    # ------------------------------------------------------------
    # IDENTITY EVIDENCE
    # ------------------------------------------------------------

    if len(cnpjs) == 1:
        identity_evidence = "STRONG"
        identity_candidate = cnpj_key(cnpjs[0])

    elif len(cnpjs) > 1:
        identity_evidence = "AMBIGUOUS"
        identity_candidate = previous_identity or stable_key(row)

    elif previous_identity:
        identity_evidence = "INHERITED"
        identity_candidate = previous_identity

    elif len(tickers) == 1:
        identity_evidence = "TICKER_ONLY"
        identity_candidate = stable_key(row)

    elif len(tickers) > 1:
        identity_evidence = "MULTI_TICKER"
        identity_candidate = stable_key(row)

    else:
        identity_evidence = "NONE"
        identity_candidate = stable_key(row)

    # ------------------------------------------------------------
    # DECISION
    # ------------------------------------------------------------

    if identity_evidence == "STRONG":
        decision = "IDENTITY_RESOLVED"
        confidence = "HIGH"

    elif (identity_evidence == "INHERITED" and len(cnpjs) == 0) or (
        len(tickers) > 1 and len(cnpjs) == 0
    ):
        decision = "REVIEW_REQUIRED"
        confidence = "MEDIUM"

    elif identity_evidence == "AMBIGUOUS" or identity_evidence in (
        "TICKER_ONLY",
        "MULTI_TICKER",
    ):
        decision = "REVIEW_REQUIRED"
        confidence = "LOW"

    else:
        decision = "BLOCKED"
        confidence = "NONE"

    # ------------------------------------------------------------
    # EVENT INTERPRETATION
    # ------------------------------------------------------------

    if event_tickers:
        event_class = "POSSIBLE_CORPORATE_EVENT"
    elif len(tickers) > 1:
        event_class = "MULTI_TICKER_REQUIRES_EVENT_ANALYSIS"
    else:
        event_class = "NO_EVENT_SIGNAL"

    # ------------------------------------------------------------
    # CNPJ SEMANTICS
    # ------------------------------------------------------------

    if len(cnpjs) == 1:
        cnpj_role = "PRIMARY_OR_STRONG_IDENTITY_EVIDENCE"

    elif len(cnpjs) > 1:
        cnpj_role = "AMBIGUOUS_MULTIPLE_CNPJ; DO_NOT_COLLAPSE_AUTOMATICALLY"

    else:
        cnpj_role = "NOT_AVAILABLE"

    # ------------------------------------------------------------
    # REASON
    # ------------------------------------------------------------

    reasons = []

    if len(tickers) > 1:
        reasons.append("multiple historical tickers detected")

    if event_tickers:
        reasons.append("possible event-related ticker detected")

    if len(cnpjs) > 1:
        reasons.append("multiple CNPJs detected")

    if len(cnpjs) == 1:
        reasons.append("single CNPJ provides strong identity evidence")

    if periods:
        reasons.append("temporal evidence available")

    if not reasons:
        reasons.append("insufficient identity evidence")

    return {
        "source_file": clean(row.get("source_file")),
        "source_row": clean(row.get("source_row")),
        "canonical_ticker": canonical_ticker,
        "historical_tickers": "|".join(tickers),
        "normal_tickers": "|".join(normal_tickers),
        "event_tickers": "|".join(event_tickers),
        "ticker_count": len(tickers),
        "periods": "|".join(periods),
        "period_count": len(periods),
        "cnpjs": "|".join(cnpjs),
        "cnpj_count": len(cnpjs),
        "cnpj_status": cnpj_status,
        "cnpj_role": cnpj_role,
        "identity_candidate": identity_candidate,
        "previous_identity_key": previous_identity,
        "identity_evidence": identity_evidence,
        "event_class": event_class,
        "decision": decision,
        "confidence": confidence,
        "reason": "; ".join(reasons),
    }


def main():
    print("=" * 90)
    print("IIP HISTORICAL IDENTITY RECONSTRUCTION R3")
    print("=" * 90)

    if not REPORTS.exists():
        print(f"ERROR: reports directory not found: {REPORTS}")
        return 1

    if not INPUT_CSV.exists():
        print(f"ERROR: input not found: {INPUT_CSV}")
        return 1

    with INPUT_CSV.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))

    results = [analyze(row) for row in rows]

    fieldnames = [
        "source_file",
        "source_row",
        "canonical_ticker",
        "historical_tickers",
        "normal_tickers",
        "event_tickers",
        "ticker_count",
        "periods",
        "period_count",
        "cnpjs",
        "cnpj_count",
        "cnpj_status",
        "cnpj_role",
        "identity_candidate",
        "previous_identity_key",
        "identity_evidence",
        "event_class",
        "decision",
        "confidence",
        "reason",
    ]

    with OUTPUT_CSV.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(results)

    decisions = Counter(row["decision"] for row in results)

    confidence = Counter(row["confidence"] for row in results)

    cnpj_status = Counter(row["cnpj_status"] for row in results)

    event_classes = Counter(row["event_class"] for row in results)

    identities = defaultdict(set)

    for row in results:
        identity = row["identity_candidate"]

        for ticker in split_values(row["historical_tickers"]):
            identities[identity].add(ticker.upper())

    multi_ticker_identities = sum(
        1 for tickers in identities.values() if len(tickers) > 1
    )

    md = f"""# IIP Historical Identity Reconstruction R3

## Safety

- Mode: READ-ONLY
- Vault modified: NO
- Persistence executed: NO
- KnowledgeBridge executed: NO
- Repository writes: NO

## Input

- `{INPUT_CSV}`
- Input records: {len(rows)}

## Decisions

- IDENTITY_RESOLVED: {decisions.get("IDENTITY_RESOLVED", 0)}
- REVIEW_REQUIRED: {decisions.get("REVIEW_REQUIRED", 0)}
- BLOCKED: {decisions.get("BLOCKED", 0)}

## Confidence

- HIGH: {confidence.get("HIGH", 0)}
- MEDIUM: {confidence.get("MEDIUM", 0)}
- LOW: {confidence.get("LOW", 0)}
- NONE: {confidence.get("NONE", 0)}

## CNPJ analysis

- SINGLE_CNPJ: {cnpj_status.get("SINGLE_CNPJ", 0)}
- MULTIPLE_CNPJ: {cnpj_status.get("MULTIPLE_CNPJ", 0)}
- NO_CNPJ: {cnpj_status.get("NO_CNPJ", 0)}

## Event analysis

- POSSIBLE_CORPORATE_EVENT: {event_classes.get("POSSIBLE_CORPORATE_EVENT", 0)}
- MULTI_TICKER_REQUIRES_EVENT_ANALYSIS: {event_classes.get("MULTI_TICKER_REQUIRES_EVENT_ANALYSIS", 0)}
- NO_EVENT_SIGNAL: {event_classes.get("NO_EVENT_SIGNAL", 0)}

## Identity topology

- Unique identity candidates: {len(identities)}
- Multi-ticker identities: {multi_ticker_identities}

## Rules

1. Ticker is not the permanent identity.
2. Multiple tickers may belong to the same historical identity.
3. Temporary/event tickers must not automatically create a new identity.
4. A single CNPJ is strong identity evidence.
5. Multiple CNPJs are ambiguous and must not be collapsed automatically.
6. Temporal evidence is preserved for later event reconstruction.
7. No persistence is allowed from this stage.

## Next gate

The next stage should construct an explicit Identity Registry containing:

- identity_id
- canonical_ticker
- historical_ticker
- valid_from
- valid_to
- event_type
- primary_cnpj
- related_cnpj
- evidence_source
- confidence
- resolution_status

R3 is diagnostic only.
"""

    OUTPUT_MD.write_text(
        md,
        encoding="utf-8",
    )

    print(f"Input records              : {len(rows)}")
    print(f"IDENTITY_RESOLVED          : {decisions.get('IDENTITY_RESOLVED', 0)}")
    print(f"REVIEW_REQUIRED            : {decisions.get('REVIEW_REQUIRED', 0)}")
    print(f"BLOCKED                    : {decisions.get('BLOCKED', 0)}")

    print(f"HIGH confidence            : {confidence.get('HIGH', 0)}")
    print(f"MEDIUM confidence          : {confidence.get('MEDIUM', 0)}")
    print(f"LOW confidence             : {confidence.get('LOW', 0)}")

    print(f"SINGLE_CNPJ                : {cnpj_status.get('SINGLE_CNPJ', 0)}")
    print(f"MULTIPLE_CNPJ              : {cnpj_status.get('MULTIPLE_CNPJ', 0)}")
    print(f"NO_CNPJ                    : {cnpj_status.get('NO_CNPJ', 0)}")

    print(
        f"POSSIBLE_EVENT             : "
        f"{event_classes.get('POSSIBLE_CORPORATE_EVENT', 0)}"
    )

    print(f"Multi-ticker identities    : {multi_ticker_identities}")

    print(f"CSV                        : {OUTPUT_CSV}")
    print(f"MD                         : {OUTPUT_MD}")
    print()

    print("Vault modified             : NO")
    print("Persistence executed       : NO")
    print("KnowledgeBridge executed   : NO")
    print("Repository writes          : NO")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
