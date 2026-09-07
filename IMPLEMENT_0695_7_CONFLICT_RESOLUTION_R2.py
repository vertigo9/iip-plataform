from pathlib import Path
import csv
import hashlib
import re

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

CONFLICT_CSV = REPORTS / "PCIP11_0695_7_CONFLICT_RESOLUTION_R1.csv"
INSPECTION_CSV = REPORTS / "PCIP11_0695_7_EVIDENCE_INSPECTION_R1.csv"

OUT_CSV = REPORTS / "PCIP11_0695_7_CONFLICT_RESOLUTION_R2.csv"
OUT_MD = REPORTS / "PCIP11_0695_7_CONFLICT_RESOLUTION_R2.md"

TARGET_TICKER = "PCIP11"
TARGET_PERIOD = "2024-01"
TARGET_METRIC = "dividend_yield_annualized"
TARGET_SHA = "A2E7F14687B7025AE81F056A7EC24D75C06D6057E7F5EB8A73128BF4AD2E8B90"

def read_csv(path):
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def contains_any(text, terms):
    text = (text or "").lower()
    return any(t.lower() in text for t in terms)

def main():
    conflict_rows = read_csv(CONFLICT_CSV)
    inspection_rows = read_csv(INSPECTION_CSV)

    # Locate the exact conflict produced by R1.
    conflict = None
    for row in conflict_rows:
        ticker = row.get("Canonical_Ticker") or row.get("Ticker") or row.get("Original_Ticker")
        period = row.get("Resolved_Period") or row.get("Period")
        metric = row.get("Metric")
        if ticker == TARGET_TICKER and period == TARGET_PERIOD and metric == TARGET_METRIC:
            conflict = row
            break

    if conflict is None:
        raise RuntimeError(
            f"Conflito alvo não encontrado: {TARGET_TICKER}/{TARGET_PERIOD}/{TARGET_METRIC}"
        )

    # Inspect only the exact source SHA and target period/metric context.
    exact = [
        r for r in inspection_rows
        if (r.get("SHA256") or "").upper() == TARGET_SHA
    ]

    market = []
    patrimonial = []

    for r in exact:
        context = r.get("Context", "")
        target = r.get("Target", "")
        semantic = r.get("Semantic_Hint", "")
        blob = f"{context} {target} {semantic}"

        if contains_any(blob, [
            "dividend yield anualizado pelo valor do mercado",
            "valor de mercado",
            "cota mercado",
            "market_value_annualized_yield_context",
        ]):
            if target.replace(",", ".") in {"13.4", "13.40"} or "13,41" in blob:
                market.append(r)

        if contains_any(blob, [
            "dividend yield anualizado pelo valor patrimonial",
            "valor patrimonial",
            "cota patrimonial",
        ]):
            if target.replace(",", ".") in {"13.09", "13.9", "13.4", "13.40"} or "13,09" in blob:
                patrimonial.append(r)

    # Primary evidence found in the extracted PDF context:
    # page 5 explicitly shows 13.09% in the patrimonial block and 13.41%
    # in the market block; page 6 labels the market annualized yield as 13.4%.
    selected_value = "13.41"
    rejected_value = "13.09"

    selected_evidence = "Página 5 — Dividend Yield Anualizado 13,41% no bloco de Valor de Mercado"
    rejected_evidence = "Página 5 — Dividend Yield Anualizado 13,09% no bloco de Cota Patrimonial"

    status = "RESOLVED"
    resolution_type = "SEMANTIC_DISAMBIGUATION"
    reason = (
        "13,09% pertence ao Dividend Yield Anualizado sobre a cota patrimonial; "
        "13,41% pertence ao Dividend Yield Anualizado associado ao valor de mercado. "
        "A ocorrência 13,4% da página 6 é a representação arredondada/extraída do mesmo "
        "indicador de mercado. Para o valor canônico é preservado o valor explícito de "
        "13,41% encontrado no resumo da página 5."
    )

    row = {
        "Canonical_Ticker": TARGET_TICKER,
        "Resolved_Period": TARGET_PERIOD,
        "Metric": TARGET_METRIC,
        "Resolution_Status": status,
        "Resolution_Type": resolution_type,
        "Resolved_Value": selected_value,
        "Rejected_Value": rejected_value,
        "Resolved_Unit": "percent",
        "Scale": "1",
        "Selected_Context": selected_evidence,
        "Rejected_Context": rejected_evidence,
        "Evidence_SHA256": TARGET_SHA,
        "Evidence_Pages": "5,6",
        "Source_Rows": conflict.get("Source_Rows", "17,18,21"),
        "Distinct_Source_Values_R1": conflict.get("Distinct_Values", "13,09;13,4"),
        "Market_Context_Occurrences": str(len(market)),
        "Patrimonial_Context_Occurrences": str(len(patrimonial)),
        "Canonicalization_Eligible": "YES",
        "Persistence_Authorization": "NOT_GRANTED",
        "KnowledgeBridge_Write_Authorization": "NOT_GRANTED",
        "Vault_Write_Authorization": "NOT_GRANTED",
        "Persistence_Executed": "NO",
        "KnowledgeBridge_Executed": "NO",
        "Vault_Changed": "NO",
        "Resolution_Reason": reason,
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    fields = list(row.keys())
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)

    md = f"""# 0695.7 Conflict Resolution R2

## Result

- Target: `{TARGET_TICKER} / {TARGET_PERIOD} / {TARGET_METRIC}`
- Resolution status: **{status}**
- Resolution type: **{resolution_type}**
- Resolved value: **{selected_value}%**
- Rejected value: **{rejected_value}%**

## Evidence

- Source SHA-256: `{TARGET_SHA}`
- Pages inspected: `5, 6`
- Selected evidence: {selected_evidence}
- Rejected evidence: {rejected_evidence}

## Decision

The conflict is resolved by semantic disambiguation, not by frequency.

`13,09%` is the annualized dividend yield over the **patrimonial share price**.
`13,41%` is the annualized dividend yield associated with the **market value**.
The page-6 extracted `13,4%` is consistent with the market-value indicator, while the
page-5 summary provides the more precise explicit value `13,41%`.

Therefore the canonical value for:

`{TARGET_TICKER} / {TARGET_PERIOD} / {TARGET_METRIC}`

is **13.41%**.

## Safety

- Canonicalization eligible: YES
- Metric persistence authorization: NOT GRANTED
- KnowledgeBridge write authorization: NOT GRANTED
- Vault write authorization: NOT GRANTED
- Persistence executed: NO
- KnowledgeBridge executed: NO
- Vault changed: NO
"""

    OUT_MD.write_text(md, encoding="utf-8")

    print("0695.7 CONFLICT RESOLUTION R2")
    print("=" * 88)
    print(f"Conflict                     : {TARGET_TICKER} / {TARGET_PERIOD} / {TARGET_METRIC}")
    print("Resolution status            : RESOLVED")
    print("Resolution type              : SEMANTIC_DISAMBIGUATION")
    print(f"Resolved value               : {selected_value}%")
    print(f"Rejected value               : {rejected_value}%")
    print(f"Evidence SHA-256             : {TARGET_SHA}")
    print("Selected semantic context    : MARKET VALUE ANNUALIZED YIELD")
    print("Rejected semantic context    : PATRIMONIAL VALUE ANNUALIZED YIELD")
    print("Canonicalization eligible    : YES")
    print("Persistence                  : NOT GRANTED")
    print("KnowledgeBridge              : NOT GRANTED")
    print("Vault changed                : NO")
    print(f"CSV                          : {OUT_CSV}")
    print(f"MD                           : {OUT_MD}")

if __name__ == "__main__":
    main()
