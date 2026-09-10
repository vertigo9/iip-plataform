from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "reports"

DISCOVERY_CSV = REPORTS / "IIP_HISTORICAL_BATCH_DISCOVERY_R1.csv"
SELECTION_CSV = REPORTS / "IIP_HISTORICAL_BATCH_SELECTION_R2.csv"
CANONICAL_CSV = REPORTS / "PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R4.csv"

OUTPUT_CSV = REPORTS / "IIP_HISTORICAL_IDENTITY_RECONSTRUCTION_R1.csv"
OUTPUT_MD = REPORTS / "IIP_HISTORICAL_IDENTITY_RECONSTRUCTION_R1.md"


CONTROL_FILES = {
    "IIP_HISTORICAL_BATCH_DISCOVERY_R1.csv",
    "IIP_HISTORICAL_BATCH_SELECTION_R2.csv",
}


def norm(value):
    return (value or "").strip()


def normalize_column(name):
    return re.sub(r"[^A-Z0-9]", "", (name or "").upper())


def normalize_cnpj(value):
    digits = re.sub(r"\D", "", norm(value))
    return digits if len(digits) == 14 else ""


def ticker_candidates(value):
    if not value:
        return []

    found = []

    for token in re.split(r"[,;|>/\\\s]+", value.upper()):
        token = token.strip()

        if re.fullmatch(r"[A-Z]{4}\d{1,2}", token):
            found.append(token)

    return sorted(set(found))


def discover_cnpjs(row):
    result = set()

    for value in row.values():
        if not value:
            continue

        text = str(value)

        patterns = re.findall(
            r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b",
            text,
        )

        for item in patterns:
            cnpj = normalize_cnpj(item)
            if cnpj:
                result.add(cnpj)

    return sorted(result)


def discover_tickers(row):
    result = set()

    for value in row.values():
        if not value:
            continue

        for ticker in ticker_candidates(str(value)):
            result.add(ticker)

    return sorted(result)


def discover_identity_columns(fieldnames):
    cnpj_fields = []
    ticker_fields = []
    identity_fields = []
    name_fields = []

    for field in fieldnames:
        normalized = normalize_column(field)

        if "CNPJ" in normalized:
            cnpj_fields.append(field)

        if "TICKER" in normalized:
            ticker_fields.append(field)

        if (
            "IDENTITY" in normalized
            or "DENOMINACAO" in normalized
            or "NOME" in normalized
            or "FUNDNAME" in normalized
        ):
            identity_fields.append(field)

        if "NAME" in normalized or "NOME" in normalized or "DENOMINACAO" in normalized:
            name_fields.append(field)

    return (
        cnpj_fields,
        ticker_fields,
        identity_fields,
        name_fields,
    )


def read_csv(path):
    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        return list(csv.DictReader(handle))


def select_candidate_files():
    if not SELECTION_CSV.exists():
        return []

    rows = read_csv(SELECTION_CSV)

    files = []

    for row in rows:
        classification = norm(row.get("classification"))

        if classification not in (
            "READY_CANDIDATE",
            "REVIEW_REQUIRED",
        ):
            continue

        filename = norm(row.get("file") or row.get("file_name"))

        path = norm(row.get("path") or row.get("source_path"))

        if not filename:
            continue

        if filename in CONTROL_FILES:
            continue

        if path:
            candidate = Path(path)
        else:
            candidate = REPORTS / filename

        if candidate.exists():
            files.append(candidate)

    return sorted(
        set(files),
        key=lambda p: p.name.upper(),
    )


def load_canonical_identities():
    result = defaultdict(set)

    if not CANONICAL_CSV.exists():
        return result

    rows = read_csv(CANONICAL_CSV)

    for row in rows:
        tickers = discover_tickers(row)
        cnpjs = discover_cnpjs(row)

        for cnpj in cnpjs:
            result[f"CNPJ:{cnpj}"].update(tickers)

    return result


def reconstruct():
    candidate_files = select_candidate_files()

    canonical = load_canonical_identities()

    results = []

    for path in candidate_files:
        try:
            rows = read_csv(path)
        except Exception as exc:
            results.append(
                {
                    "source_file": path.name,
                    "source_row": "",
                    "cnpj": "",
                    "tickers": "",
                    "canonical_ticker": "",
                    "identity_key": "",
                    "confidence": "NONE",
                    "decision": "BLOCKED",
                    "reason": f"CSV unreadable: {exc}",
                }
            )
            continue

        if not rows:
            continue

        (
            cnpj_fields,
            ticker_fields,
            identity_fields,
            name_fields,
        ) = discover_identity_columns(list(rows[0].keys()))

        for row_number, row in enumerate(
            rows,
            start=2,
        ):
            cnpjs = discover_cnpjs(row)
            tickers = discover_tickers(row)

            identity_key = ""

            if cnpjs:
                identity_key = "CNPJ:" + cnpjs[0]

            elif tickers:
                identity_key = "TICKER:" + "|".join(tickers)

            canonical_tickers = set()

            for cnpj in cnpjs:
                canonical_tickers.update(
                    canonical.get(
                        f"CNPJ:{cnpj}",
                        set(),
                    )
                )

            if cnpjs and canonical_tickers:
                confidence = "HIGH"
                decision = "IDENTITY_RESOLVED"
                reason = "CNPJ identificado e relacionado a identidade canônica"

            elif cnpjs:
                confidence = "HIGH"
                decision = "IDENTITY_RESOLVED"
                reason = "CNPJ identificado; identidade forte preservada"

            elif len(tickers) >= 2:
                confidence = "MEDIUM"
                decision = "REVIEW_REQUIRED"
                reason = (
                    "múltiplos tickers encontrados; linhagem exige validação adicional"
                )

            elif tickers:
                confidence = "LOW"
                decision = "REVIEW_REQUIRED"
                reason = "ticker identificado, mas sem identidade forte"

            else:
                confidence = "NONE"
                decision = "BLOCKED"
                reason = "nenhum CNPJ ou ticker identificável na linha"

            canonical_ticker = ""

            if canonical_tickers:
                canonical_ticker = sorted(canonical_tickers)[-1]

            elif tickers:
                canonical_ticker = tickers[-1]

            results.append(
                {
                    "source_file": path.name,
                    "source_row": row_number,
                    "cnpj": "|".join(cnpjs),
                    "tickers": "|".join(tickers),
                    "canonical_ticker": canonical_ticker,
                    "identity_key": identity_key,
                    "confidence": confidence,
                    "decision": decision,
                    "reason": reason,
                    "cnpj_fields": "|".join(cnpj_fields),
                    "ticker_fields": "|".join(ticker_fields),
                    "identity_fields": "|".join(identity_fields),
                    "name_fields": "|".join(name_fields),
                }
            )

    return results


def main():

    print("=" * 90)
    print("IIP HISTORICAL IDENTITY RECONSTRUCTION R1")
    print("=" * 90)

    if not REPORTS.exists():
        print(f"ERROR: reports directory not found: {REPORTS}")
        return 1

    if not SELECTION_CSV.exists():
        print(f"ERROR: selection input not found: {SELECTION_CSV}")
        return 1

    results = reconstruct()

    fieldnames = [
        "source_file",
        "source_row",
        "cnpj",
        "tickers",
        "canonical_ticker",
        "identity_key",
        "confidence",
        "decision",
        "reason",
        "cnpj_fields",
        "ticker_fields",
        "identity_fields",
        "name_fields",
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

    identities = defaultdict(set)

    for row in results:
        if row["identity_key"]:
            identities[row["identity_key"]].update(
                filter(
                    None,
                    row["tickers"].split("|"),
                )
            )

    multi_ticker = sum(1 for tickers in identities.values() if len(tickers) > 1)

    md = f"""# IIP Historical Identity Reconstruction R1

## Safety

- Mode: READ-ONLY
- Vault modified: NO
- Persistence executed: NO
- KnowledgeBridge executed: NO
- Repository writes: NO

## Results

- Input candidate files: {len(select_candidate_files())}
- Output records: {len(results)}
- Unique identity keys: {len(identities)}

### Decisions

- IDENTITY_RESOLVED: {decisions.get("IDENTITY_RESOLVED", 0)}
- REVIEW_REQUIRED: {decisions.get("REVIEW_REQUIRED", 0)}
- BLOCKED: {decisions.get("BLOCKED", 0)}

### Confidence

- HIGH: {confidence.get("HIGH", 0)}
- MEDIUM: {confidence.get("MEDIUM", 0)}
- LOW: {confidence.get("LOW", 0)}
- NONE: {confidence.get("NONE", 0)}

### Multi-ticker identities

- {multi_ticker}

## Identity policy

Identity is not determined solely by ticker.

CNPJ is treated as strong identity evidence.

Historical and current tickers are preserved as temporal
attributes.

Multiple tickers may belong to the same canonical identity.

No record is persisted by this stage.

Conflicting or insufficient evidence remains REVIEW_REQUIRED
or BLOCKED.

## Outputs

- CSV: `{OUTPUT_CSV}`
- MD: `{OUTPUT_MD}`
"""

    OUTPUT_MD.write_text(
        md,
        encoding="utf-8",
    )

    print(f"Input candidate files      : {len(select_candidate_files())}")

    print(f"Output records              : {len(results)}")

    print(f"Unique identity keys        : {len(identities)}")

    print(f"IDENTITY_RESOLVED           : {decisions.get('IDENTITY_RESOLVED', 0)}")

    print(f"REVIEW_REQUIRED             : {decisions.get('REVIEW_REQUIRED', 0)}")

    print(f"BLOCKED                     : {decisions.get('BLOCKED', 0)}")

    print(f"HIGH confidence             : {confidence.get('HIGH', 0)}")

    print(f"MEDIUM confidence           : {confidence.get('MEDIUM', 0)}")

    print(f"LOW confidence              : {confidence.get('LOW', 0)}")

    print(f"NONE confidence             : {confidence.get('NONE', 0)}")

    print(f"Multi-ticker identities     : {multi_ticker}")

    print(f"CSV                         : {OUTPUT_CSV}")
    print(f"MD                          : {OUTPUT_MD}")
    print()

    print("Vault modified              : NO")
    print("Persistence executed        : NO")
    print("KnowledgeBridge executed    : NO")
    print("Repository writes           : NO")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
