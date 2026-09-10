import csv
from pathlib import Path
from collections import defaultdict, Counter

REPORT = Path(r"reports\0695_GENERIC_METRIC_PERSISTENCE_DRY_RUN_R1.csv")
OUT_MD = Path(r"reports\0695_GENERIC_METRIC_PERSISTENCE_DRY_RUN_INSPECTION_R2.md")

def clean(v):
    return (v or "").strip()

def first_existing(headers, *names):
    for name in names:
        if name in headers:
            return name
    return None

def group_rows(rows, key_func):
    groups = defaultdict(list)
    for r in rows:
        key = key_func(r)
        if key:
            groups[key].append(r)
    return {k: v for k, v in groups.items() if len(v) > 1}

def short_row(r, cols):
    ticker = clean(r.get(cols["ticker"], "")) if cols["ticker"] else ""
    metric = clean(r.get(cols["metric"], "")) if cols["metric"] else ""
    period = clean(r.get(cols["period"], "")) if cols["period"] else ""
    file_name = clean(r.get(cols["file"], "")) if cols["file"] else ""
    sha = clean(r.get(cols["sha"], "")) if cols["sha"] else ""
    value = clean(r.get(cols["value"], "")) if cols["value"] else ""
    unit = clean(r.get(cols["unit"], "")) if cols["unit"] else ""
    return (
        f"ticker={ticker}; metric={metric}; period={period}; "
        f"value={value}; unit={unit}; file={file_name}; sha={sha[:16]}"
    )

def main():
    print("0695 GENERIC METRIC PERSISTENCE DRY-RUN INSPECTION R2")
    print("=" * 110)
    print(f"Input: {REPORT.resolve()}")

    if not REPORT.exists():
        print(f"ERRO: arquivo não encontrado: {REPORT.resolve()}")
        print("Execute primeiro:")
        print("  python .\\GENERIC_METRIC_PERSISTENCE_DRY_RUN_R1.py")
        return

    with REPORT.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        headers = reader.fieldnames or []

    print(f"\nRows loaded: {len(rows)}")
    print("\nCSV HEADERS")
    print("-" * 110)
    for i, h in enumerate(headers, 1):
        print(f"{i:02d}. {h}")

    if not rows:
        print("\nNenhuma linha de dados.")
        return

    cols = {
        "status": first_existing(
            headers,
            "Status",
            "Persistence_Status",
            "Dry_Run_Status",
            "Validation_Status",
            "Result",
            "Decision",
            "Readiness",
            "Persistence_Decision",
        ),
        "metric_id": first_existing(headers, "Metric_Evidence_ID", "Metric_ID"),
        "knowledge_id": first_existing(headers, "Knowledge_Evidence_ID", "Knowledge_ID"),
        "sha": first_existing(headers, "SHA256", "Document_Hash"),
        "metric": first_existing(headers, "Metric"),
        "period": first_existing(headers, "Resolved_Period", "Period"),
        "ticker": first_existing(headers, "Canonical_Ticker", "Ticker", "Original_Ticker"),
        "value": first_existing(headers, "Value", "Metric_Value"),
        "unit": first_existing(headers, "Resolved_Unit", "Unit", "Original_Unit"),
        "file": first_existing(headers, "FileName", "Source_File"),
        "reason": first_existing(
            headers,
            "Validation_Reason",
            "Reason",
            "Block_Reason",
            "Persistence_Reason",
            "Decision_Reason",
        ),
    }

    print("\nDETECTED COLUMNS")
    print("-" * 110)
    for key, value in cols.items():
        print(f"{key:18}: {value}")

    # Show distinct values for columns that look like state/status fields.
    state_candidates = [
        h for h in headers
        if any(token in h.lower() for token in (
            "status", "state", "decision", "result", "action", "ready", "block"
        ))
    ]

    print("\nSTATE / DECISION COLUMNS")
    print("-" * 110)
    if not state_candidates:
        print("Nenhuma coluna candidata encontrada.")
    else:
        for h in state_candidates:
            values = Counter(clean(r.get(h, "")) for r in rows)
            print(f"\n[{h}]")
            for value, count in values.most_common():
                print(f"  {repr(value)} -> {count}")

    ready = []
    blocked = []
    unresolved_status = []

    if cols["status"]:
        for r in rows:
            s = clean(r.get(cols["status"], "")).upper()
            if s == "READY":
                ready.append(r)
            elif s == "BLOCKED":
                blocked.append(r)
            else:
                unresolved_status.append(r)

    print("\nSTATUS SUMMARY")
    print("-" * 110)
    if cols["status"]:
        print(f"Status column: {cols['status']}")
        print(f"READY        : {len(ready)}")
        print(f"BLOCKED      : {len(blocked)}")
        print(f"OTHER/EMPTY  : {len(unresolved_status)}")
    else:
        print("Nenhuma coluna de status padrão foi identificada.")
        print("Não vou inventar READY/BLOCKED a partir de outras colunas.")

    # Duplicate groups.
    metric_dups = group_rows(
        rows,
        lambda r: clean(r.get(cols["metric_id"], "")) if cols["metric_id"] else "",
    )
    knowledge_dups = group_rows(
        rows,
        lambda r: clean(r.get(cols["knowledge_id"], "")) if cols["knowledge_id"] else "",
    )
    sha_metric_period_dups = group_rows(
        rows,
        lambda r: "||".join([
            clean(r.get(cols["sha"], "")) if cols["sha"] else "",
            clean(r.get(cols["metric"], "")) if cols["metric"] else "",
            clean(r.get(cols["period"], "")) if cols["period"] else "",
        ]) if (cols["sha"] and cols["metric"] and cols["period"]) else "",
    )

    def print_groups(title, groups):
        print(f"\n{title}: {len(groups)} group(s)")
        print("-" * 110)
        if not groups:
            print("None")
            return

        for idx, (key, items) in enumerate(groups.items(), 1):
            print(f"\nGROUP {idx} ({len(items)} rows)")
            print(f"KEY: {key}")
            for r in items:
                print("  - " + short_row(r, cols))

    print_groups("DUPLICATE METRIC IDs", metric_dups)
    print_groups("DUPLICATE KNOWLEDGE IDs", knowledge_dups)
    print_groups("DUPLICATE SHA + METRIC + PERIOD", sha_metric_period_dups)

    # Full input distribution.
    if cols["ticker"]:
        ticker_counts = Counter(clean(r.get(cols["ticker"], "")) for r in rows)
        print("\nTICKERS REPRESENTED")
        print("-" * 110)
        for ticker, count in ticker_counts.most_common():
            print(f"{repr(ticker)} -> {count}")

    # Write inspection report.
    md = []
    md.append("# 0695 Generic Metric Persistence — Dry-Run Inspection R2")
    md.append("")
    md.append(f"- Input: `{REPORT}`")
    md.append(f"- Rows loaded: **{len(rows)}**")
    md.append("")
    md.append("## Detected columns")
    for key, value in cols.items():
        md.append(f"- `{key}`: `{value}`")
    md.append("")
    md.append("## State / decision columns")
    if state_candidates:
        for h in state_candidates:
            vals = Counter(clean(r.get(h, "")) for r in rows)
            md.append(f"### `{h}`")
            for value, count in vals.most_common():
                md.append(f"- `{value}`: **{count}**")
    else:
        md.append("- No state/decision column detected.")
    md.append("")
    md.append("## Status interpretation")
    if cols["status"]:
        md.append(f"- Status column: `{cols['status']}`")
        md.append(f"- READY: **{len(ready)}**")
        md.append(f"- BLOCKED: **{len(blocked)}**")
        md.append(f"- OTHER/EMPTY: **{len(unresolved_status)}**")
    else:
        md.append("- No standard status column detected; READY/BLOCKED was not inferred.")
    md.append("")

    for title, groups in (
        ("Duplicate Metric IDs", metric_dups),
        ("Duplicate Knowledge IDs", knowledge_dups),
        ("Duplicate SHA + Metric + Period", sha_metric_period_dups),
    ):
        md.append(f"## {title}")
        if not groups:
            md.append("- None")
        else:
            for key, items in groups.items():
                md.append(f"### `{key}`")
                for r in items:
                    md.append("- " + short_row(r, cols))
        md.append("")

    if cols["ticker"]:
        md.append("## Tickers represented")
        ticker_counts = Counter(clean(r.get(cols["ticker"], "")) for r in rows)
        for ticker, count in ticker_counts.most_common():
            md.append(f"- `{ticker}`: **{count}**")
        md.append("")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    print(f"\nMD inspection: {OUT_MD.resolve()}")
    print("Persistence executed     : NO")
    print("KnowledgeBridge executed : NO")
    print("Vault changed             : NO")

if __name__ == "__main__":
    main()
