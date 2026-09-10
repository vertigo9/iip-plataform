from __future__ import annotations

import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "reports"

INPUT_CSV = REPORTS / "IIP_HISTORICAL_IDENTITY_RECONSTRUCTION_R1.csv"
OUTPUT_CSV = REPORTS / "IIP_HISTORICAL_IDENTITY_RECONSTRUCTION_R2.csv"
OUTPUT_MD = REPORTS / "IIP_HISTORICAL_IDENTITY_RECONSTRUCTION_R2.md"


def clean(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def split_values(value: str | None) -> list[str]:
    value = clean(value)

    if not value:
        return []

    separators = ["|", ";", ","]

    for separator in separators:
        if separator in value:
            return [item.strip() for item in value.split(separator) if item.strip()]

    return [value]


def unique(values: list[str]) -> list[str]:
    result = []
    seen = set()

    for value in values:
        normalized = value.strip().upper()

        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(value.strip())

    return result


def normalize_cnpj(value: str) -> str:
    digits = "".join(character for character in clean(value) if character.isdigit())

    return digits


def identity_key_from_cnpj(cnpj: str) -> str:
    normalized = normalize_cnpj(cnpj)

    if not normalized:
        return ""

    return "CNPJ:" + normalized


def stable_identity_key(
    tickers: list[str],
    cnpjs: list[str],
    source_file: str,
    source_row: str,
) -> str:
    material = "|".join(
        [
            ",".join(sorted(t.upper() for t in tickers)),
            ",".join(sorted(cnpjs)),
            source_file,
            source_row,
        ]
    )

    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]

    return "UNRESOLVED:" + digest


def ticker_is_event_like(ticker: str) -> bool:
    ticker = clean(ticker).upper()

    if not ticker:
        return False

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

    return any(ticker.endswith(token) for token in event_tokens)


def evaluate_record(row: dict) -> dict:
    source_file = clean(row.get("source_file") or row.get("file"))

    source_row = clean(row.get("source_row") or row.get("row"))

    cnpjs = unique(
        [
            normalize_cnpj(value)
            for value in split_values(row.get("cnpj") or row.get("CNPJ"))
            if normalize_cnpj(value)
        ]
    )

    tickers = unique(
        split_values(row.get("tickers") or row.get("Ticker") or row.get("ticker"))
    )

    canonical_ticker = clean(row.get("canonical_ticker") or row.get("Canonical_Ticker"))

    old_identity_key = clean(row.get("identity_key") or row.get("Identity_Key"))

    old_confidence = clean(row.get("confidence") or row.get("Confidence"))

    old_decision = clean(row.get("decision") or row.get("Decision"))

    periods = unique(
        split_values(
            row.get("periods") or row.get("period") or row.get("Content_Periods")
        )
    )

    multi_cnpj = len(cnpjs) > 1
    multi_ticker = len(tickers) > 1

    unique_cnpj_identity = ""

    if len(cnpjs) == 1:
        unique_cnpj_identity = identity_key_from_cnpj(cnpjs[0])

    if unique_cnpj_identity:
        decision = "IDENTITY_RESOLVED"
        confidence = "HIGH"
        identity_key = unique_cnpj_identity
        reason = (
            "CNPJ único fornece evidência forte de continuidade "
            "da identidade; tickers são tratados como aliases históricos."
        )

    elif multi_cnpj:
        decision = "REVIEW_REQUIRED"
        confidence = "LOW"
        identity_key = old_identity_key or stable_identity_key(
            tickers,
            cnpjs,
            source_file,
            source_row,
        )
        reason = (
            "múltiplos CNPJs na mesma evidência; não é seguro "
            "atribuir uma única identidade automaticamente."
        )

    elif multi_ticker:
        decision = "REVIEW_REQUIRED"
        confidence = "MEDIUM"
        identity_key = old_identity_key or stable_identity_key(
            tickers,
            cnpjs,
            source_file,
            source_row,
        )

        event_like = [ticker for ticker in tickers if ticker_is_event_like(ticker)]

        if event_like:
            reason = (
                "múltiplos tickers detectados, incluindo possível "
                "ticker associado a evento corporativo; continuidade "
                "da identidade requer validação temporal/documental."
            )
        else:
            reason = (
                "múltiplos tickers detectados; podem representar "
                "aliases históricos ou instrumentos/eventos distintos."
            )

    elif tickers:
        decision = "REVIEW_REQUIRED"
        confidence = "LOW"
        identity_key = old_identity_key or stable_identity_key(
            tickers,
            cnpjs,
            source_file,
            source_row,
        )
        reason = (
            "ticker disponível sem evidência de identidade suficiente "
            "para resolução automática."
        )

    else:
        decision = "BLOCKED"
        confidence = "NONE"
        identity_key = old_identity_key or stable_identity_key(
            tickers,
            cnpjs,
            source_file,
            source_row,
        )
        reason = (
            "não existem identificadores suficientes para reconstrução de identidade."
        )

    return {
        "source_file": source_file,
        "source_row": source_row,
        "cnpj": "|".join(cnpjs),
        "ticker_count": len(tickers),
        "tickers": "|".join(tickers),
        "canonical_ticker": canonical_ticker,
        "historical_tickers": "|".join(tickers),
        "period_count": len(periods),
        "periods": "|".join(periods),
        "identity_key": identity_key,
        "previous_identity_key": old_identity_key,
        "previous_confidence": old_confidence,
        "previous_decision": old_decision,
        "multi_cnpj": "YES" if multi_cnpj else "NO",
        "multi_ticker": "YES" if multi_ticker else "NO",
        "decision": decision,
        "confidence": confidence,
        "reason": reason,
    }


def main() -> int:
    print("=" * 90)
    print("IIP HISTORICAL IDENTITY RECONSTRUCTION R2")
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
        reader = csv.DictReader(handle)
        source_rows = list(reader)

    output_rows = [evaluate_record(row) for row in source_rows]

    fieldnames = [
        "source_file",
        "source_row",
        "cnpj",
        "ticker_count",
        "tickers",
        "canonical_ticker",
        "historical_tickers",
        "period_count",
        "periods",
        "identity_key",
        "previous_identity_key",
        "previous_confidence",
        "previous_decision",
        "multi_cnpj",
        "multi_ticker",
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
        writer.writerows(output_rows)

    decisions = Counter(row["decision"] for row in output_rows)

    confidence = Counter(row["confidence"] for row in output_rows)

    identity_groups = defaultdict(set)

    for row in output_rows:
        identity = row["identity_key"]

        if identity:
            for ticker in split_values(row["tickers"]):
                identity_groups[identity].add(ticker.upper())

    multi_ticker_identities = sum(
        1 for tickers in identity_groups.values() if len(tickers) > 1
    )

    multi_cnpj_records = sum(1 for row in output_rows if row["multi_cnpj"] == "YES")

    md = f"""# IIP Historical Identity Reconstruction R2

## Safety

- Mode: READ-ONLY
- Vault modified: NO
- Persistence executed: NO
- KnowledgeBridge executed: NO
- Repository writes: NO

## Input

- `{INPUT_CSV}`
- Input records: {len(source_rows)}

## Result

- IDENTITY_RESOLVED: {decisions.get("IDENTITY_RESOLVED", 0)}
- REVIEW_REQUIRED: {decisions.get("REVIEW_REQUIRED", 0)}
- BLOCKED: {decisions.get("BLOCKED", 0)}

## Confidence

- HIGH: {confidence.get("HIGH", 0)}
- MEDIUM: {confidence.get("MEDIUM", 0)}
- LOW: {confidence.get("LOW", 0)}
- NONE: {confidence.get("NONE", 0)}

## Identity structure

- Unique identity keys: {len(identity_groups)}
- Multi-ticker identities: {multi_ticker_identities}
- Records with multiple CNPJs: {multi_cnpj_records}

## Identity rules

### CNPJ

A single consistent CNPJ is strong identity evidence.

A record containing multiple CNPJs is ambiguous and must not
automatically collapse all CNPJs into one identity.

### Ticker

Ticker is treated as a historical identifier, not as the permanent
identity of the asset.

A single identity may therefore have multiple historical tickers.

### Corporate events

Temporary or event-related tickers must not automatically create a
new identity.

Examples include identifiers associated with subscriptions,
bonus issues, rights, conversions, reorganizations or other
corporate events.

### Temporal continuity

Ticker changes across time may represent continuity of the same
underlying identity.

The system therefore preserves historical tickers instead of
replacing the previous ticker.

## Promotion rule

Only `IDENTITY_RESOLVED` records with strong evidence may be considered
for the next gate.

`REVIEW_REQUIRED` records must remain outside automatic persistence.

`BLOCKED` records must not be persisted.

## Important

This R2 is diagnostic only.

It does not modify the Obsidian Vault and does not execute persistence.
"""

    OUTPUT_MD.write_text(
        md,
        encoding="utf-8",
    )

    print(f"Input records              : {len(source_rows)}")

    print(f"IDENTITY_RESOLVED          : {decisions.get('IDENTITY_RESOLVED', 0)}")

    print(f"REVIEW_REQUIRED            : {decisions.get('REVIEW_REQUIRED', 0)}")

    print(f"BLOCKED                    : {decisions.get('BLOCKED', 0)}")

    print(f"HIGH confidence            : {confidence.get('HIGH', 0)}")

    print(f"MEDIUM confidence          : {confidence.get('MEDIUM', 0)}")

    print(f"LOW confidence             : {confidence.get('LOW', 0)}")

    print(f"NONE confidence            : {confidence.get('NONE', 0)}")

    print(f"Unique identity keys       : {len(identity_groups)}")

    print(f"Multi-ticker identities    : {multi_ticker_identities}")

    print(f"Multiple-CNPJ records      : {multi_cnpj_records}")

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
