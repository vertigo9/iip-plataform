import csv
from pathlib import Path
from collections import defaultdict, Counter

REPORT = Path(r"reports\0695_GENERIC_METRIC_PERSISTENCE_DRY_RUN_R1.csv")
OUT_MD = Path(r"reports\0695_GENERIC_METRIC_PERSISTENCE_DRY_RUN_INSPECTION_R1.md")

def clean(v):
    return (v or "").strip()

def main():
    print("0695 GENERIC METRIC PERSISTENCE DRY-RUN INSPECTION R1")
    print("=" * 100)

    if not REPORT.exists():
        print(f"ERRO: arquivo não encontrado: {REPORT.resolve()}")
        print("Execute primeiro: python .\\GENERIC_METRIC_PERSISTENCE_DRY_RUN_R1.py")
        return

    with REPORT.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    print(f"Rows loaded                : {len(rows)}")

    # Detect likely column names without inventing schema.
    def col(*names):
        for name in names:
            if name in rows[0]:
                return name
        return None

    status_col = col("Status", "Persistence_Status", "Result")
    metric_id_col = col("Metric_Evidence_ID", "Metric_ID")
    knowledge_id_col = col("Knowledge_Evidence_ID", "Knowledge_ID")
    sha_col = col("SHA256", "Document_Hash")
    metric_col = col("Metric")
    period_col = col("Resolved_Period", "Period")
    ticker_col = col("Canonical_Ticker", "Ticker", "Original_Identity")
    reason_col = col("Reason", "Block_Reason", "Validation_Reason")
    file_col = col("FileName", "Source_File")

    print("\nColumns detected:")
    for label, value in [
        ("status", status_col),
        ("metric_id", metric_id_col),
        ("knowledge_id", knowledge_id_col),
        ("sha", sha_col),
        ("metric", metric_col),
        ("period", period_col),
        ("ticker", ticker_col),
        ("reason", reason_col),
        ("file", file_col),
    ]:
        print(f"  {label:16}: {value}")

    blocked = []
    ready = []
    for r in rows:
        status = clean(r.get(status_col, "")) if status_col else ""
        if status.upper() == "BLOCKED":
            blocked.append(r)
        elif status.upper() == "READY":
            ready.append(r)

    print(f"\nREADY rows                 : {len(ready)}")
    print(f"BLOCKED rows               : {len(blocked)}")

    # Duplicate groups.
    def groups_for(key_func):
        d = defaultdict(list)
        for r in rows:
            key = key_func(r)
            if key:
                d[key].append(r)
        return {k: v for k, v in d.items() if len(v) > 1}

    metric_dups = groups_for(lambda r: clean(r.get(metric_id_col, "")) if metric_id_col else "")
    knowledge_dups = groups_for(lambda r: clean(r.get(knowledge_id_col, "")) if knowledge_id_col else "")
    sha_metric_period_dups = groups_for(
        lambda r: "||".join([
            clean(r.get(sha_col, "")) if sha_col else "",
            clean(r.get(metric_col, "")) if metric_col else "",
            clean(r.get(period_col, "")) if period_col else "",
        ]) if (sha_col and metric_col and period_col) else ""
    )

    def print_groups(title, groups):
        print(f"\n{title}: {len(groups)} group(s)")
        if not groups:
            print("  None")
            return
        for idx, (key, items) in enumerate(groups.items(), 1):
            print(f"\n  GROUP {idx} ({len(items)} rows)")
            print(f"  Key: {key}")
            for r in items:
                print(
                    "   - "
                    f"status={clean(r.get(status_col, '')) if status_col else ''}; "
                    f"ticker={clean(r.get(ticker_col, '')) if ticker_col else ''}; "
                    f"metric={clean(r.get(metric_col, '')) if metric_col else ''}; "
                    f"period={clean(r.get(period_col, '')) if period_col else ''}; "
                    f"file={clean(r.get(file_col, '')) if file_col else ''}; "
                    f"sha={clean(r.get(sha_col, ''))[:16] if sha_col else ''}"
                )

    print_groups("Duplicate Metric IDs", metric_dups)
    print_groups("Duplicate Knowledge IDs", knowledge_dups)
    print_groups("Duplicate SHA+metric+period", sha_metric_period_dups)

    print("\nBLOCKED DETAIL")
    print("-" * 100)
    if not blocked:
        print("No blocked rows.")
    else:
        for i, r in enumerate(blocked, 1):
            print(
                f"{i:02d}. "
                f"ticker={clean(r.get(ticker_col, '')) if ticker_col else ''} | "
                f"metric={clean(r.get(metric_col, '')) if metric_col else ''} | "
                f"period={clean(r.get(period_col, '')) if period_col else ''} | "
                f"file={clean(r.get(file_col, '')) if file_col else ''} | "
                f"reason={clean(r.get(reason_col, '')) if reason_col else '(reason column not found)'}"
            )

    # Write a compact markdown inspection report.
    lines = []
    lines.append("# 0695 Generic Metric Persistence — Dry-Run Inspection R1")
    lines.append("")
    lines.append(f"- Rows loaded: **{len(rows)}**")
    lines.append(f"- READY: **{len(ready)}**")
    lines.append(f"- BLOCKED: **{len(blocked)}**")
    lines.append(f"- Duplicate Metric IDs: **{len(metric_dups)}**")
    lines.append(f"- Duplicate Knowledge IDs: **{len(knowledge_dups)}**")
    lines.append(f"- Duplicate SHA+metric+period: **{len(sha_metric_period_dups)}**")
    lines.append("")
    lines.append("## BLOCKED")
    if blocked:
        for r in blocked:
            lines.append(
                "- "
                f"ticker=`{clean(r.get(ticker_col, '')) if ticker_col else ''}`; "
                f"metric=`{clean(r.get(metric_col, '')) if metric_col else ''}`; "
                f"period=`{clean(r.get(period_col, '')) if period_col else ''}`; "
                f"reason=`{clean(r.get(reason_col, '')) if reason_col else ''}`; "
                f"file=`{clean(r.get(file_col, '')) if file_col else ''}`"
            )
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## DUPLICATE METRIC IDS")
    if metric_dups:
        for k, items in metric_dups.items():
            lines.append(f"### `{k}`")
            for r in items:
                lines.append(
                    "- "
                    f"ticker=`{clean(r.get(ticker_col, '')) if ticker_col else ''}`; "
                    f"metric=`{clean(r.get(metric_col, '')) if metric_col else ''}`; "
                    f"period=`{clean(r.get(period_col, '')) if period_col else ''}`; "
                    f"file=`{clean(r.get(file_col, '')) if file_col else ''}`"
                )
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## DUPLICATE KNOWLEDGE IDS")
    if knowledge_dups:
        for k, items in knowledge_dups.items():
            lines.append(f"### `{k}`")
            for r in items:
                lines.append(
                    "- "
                    f"ticker=`{clean(r.get(ticker_col, '')) if ticker_col else ''}`; "
                    f"metric=`{clean(r.get(metric_col, '')) if metric_col else ''}`; "
                    f"period=`{clean(r.get(period_col, '')) if period_col else ''}`; "
                    f"file=`{clean(r.get(file_col, '')) if file_col else ''}`"
                )
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## DUPLICATE SHA + METRIC + PERIOD")
    if sha_metric_period_dups:
        for k, items in sha_metric_period_dups.items():
            lines.append(f"### `{k}`")
            for r in items:
                lines.append(
                    "- "
                    f"ticker=`{clean(r.get(ticker_col, '')) if ticker_col else ''}`; "
                    f"metric=`{clean(r.get(metric_col, '')) if metric_col else ''}`; "
                    f"period=`{clean(r.get(period_col, '')) if period_col else ''}`; "
                    f"file=`{clean(r.get(file_col, '')) if file_col else ''}`"
                )
    else:
        lines.append("- None")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nMD inspection             : {OUT_MD.resolve()}")
    print("Persistence executed      : NO")
    print("KnowledgeBridge executed  : NO")
    print("Vault changed             : NO")

if __name__ == "__main__":
    main()
