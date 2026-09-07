#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
0695.7 EVIDENCE INSPECTION R1

Read-only inspection of the original CVBI11 January/2024 management report.
Finds the textual occurrences of 13,40 / 13,4 and 13,09, records page/context,
and preserves the source SHA-256.

No persistence, KnowledgeBridge, or Vault writes are performed.
"""

from pathlib import Path
import csv, hashlib, re, sys

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
DATA = ROOT / "data"
EXPECTED_SHA = "A2E7F14687B7025AE81F056A7EC24D75C06D6057E7F5EB8A73128BF4AD2E8B90"
OUTPUT_CSV = REPORTS / "PCIP11_0695_7_EVIDENCE_INSPECTION_R1.csv"
OUTPUT_MD = REPORTS / "PCIP11_0695_7_EVIDENCE_INSPECTION_R1.md"

TARGETS = ("13,40", "13,4", "13,09")

def sha256_file(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1024*1024), b""):
            h.update(b)
    return h.hexdigest().upper()

def norm_text(s):
    return re.sub(r"\s+", " ", s or "").strip()

def find_pdf():
    candidates = []
    for p in DATA.rglob("*.pdf"):
        name = p.name.lower()
        if "cvbi11" in name and "janeiro 2024" in name and "relat" in name and "gest" in name:
            candidates.append(p)
    # Prefer exact SHA match.
    for p in candidates:
        try:
            if sha256_file(p) == EXPECTED_SHA:
                return p
        except Exception:
            pass
    # Fall back to any candidate only if its SHA cannot be checked.
    return None

def extract_with_pymupdf(pdf):
    import fitz
    rows = []
    doc = fitz.open(pdf)
    for page_no, page in enumerate(doc, 1):
        text = page.get_text("text") or ""
        compact = norm_text(text)
        for target in TARGETS:
            for m in re.finditer(re.escape(target), compact, flags=re.I):
                a = max(0, m.start()-180)
                b = min(len(compact), m.end()+220)
                rows.append({
                    "Page": page_no,
                    "Target": target,
                    "Context": compact[a:b],
                })
    return rows, len(doc)

def main():
    if not REPORTS.exists():
        REPORTS.mkdir(parents=True)

    pdf = find_pdf()
    if not pdf:
        print("0695.7 EVIDENCE INSPECTION R1")
        print("="*88)
        print("ERROR: exact PDF SHA-256 was not found under data\\.")
        print("Expected SHA:", EXPECTED_SHA)
        sys.exit(2)

    actual_sha = sha256_file(pdf)
    rows, page_count = extract_with_pymupdf(pdf)

    fields = ["Page","Target","Context","PDF","SHA256","Semantic_Hint"]
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            ctx = r["Context"]
            hint = ""
            if "DIVIDEND YIELD ANUALIZADO PELO VALOR DO MERCADO" in ctx.upper():
                hint = "MARKET_VALUE_ANNUALIZED_YIELD_CONTEXT"
            elif "DIVIDEND YIELD ANUALIZADO PELO VALOR PATRIMONIAL" in ctx.upper():
                hint = "NAV_ANNUALIZED_YIELD_CONTEXT"
            elif "DIVIDEND YIELD LTM" in ctx.upper():
                hint = "LTM_YIELD_CONTEXT"
            w.writerow({
                **r,
                "PDF": str(pdf),
                "SHA256": actual_sha,
                "Semantic_Hint": hint
            })

    counts = {}
    for r in rows:
        counts[r["Target"]] = counts.get(r["Target"], 0) + 1

    md = [
        "# 0695.7 Evidence Inspection R1",
        "",
        "Read-only inspection of the exact source PDF identified by SHA-256.",
        "",
        f"- PDF: `{pdf}`",
        f"- SHA-256: `{actual_sha}`",
        f"- SHA match: `{'YES' if actual_sha == EXPECTED_SHA else 'NO'}`",
        f"- Pages: `{page_count}`",
        "",
        "## Occurrence counts",
        "",
    ]
    for t in TARGETS:
        md.append(f"- `{t}`: {counts.get(t,0)} occurrence(s)")

    md += ["", "## Interpretation rule", "",
           "- This component does NOT select a value by frequency.",
           "- A value is only resolvable when its page context identifies the semantic metric.",
           "- If 13,40 is explicitly attached to the target metric and 13,09 is attached to a different metric, the conflict can be resolved.",
           "- If both values remain semantically equivalent in the same source context, the conflict remains UNRESOLVED.",
           "",
           "## Safety", "",
           "- Persistence executed: NO",
           "- KnowledgeBridge executed: NO",
           "- Vault changed: NO",
           "",
           "## Detailed occurrences", ""]
    for r in rows:
        md += [f"### Page {r['Page']} — `{r['Target']}`", "",
               r["Context"], ""]

    OUTPUT_MD.write_text("\n".join(md), encoding="utf-8")

    print("0695.7 EVIDENCE INSPECTION R1")
    print("="*88)
    print("PDF                         :", pdf)
    print("SHA-256                     :", actual_sha)
    print("SHA match                   :", "YES" if actual_sha == EXPECTED_SHA else "NO")
    print("Pages                       :", page_count)
    for t in TARGETS:
        print(f"{t:<27}:", counts.get(t,0), "occurrence(s)")
    print("CSV                         :", OUTPUT_CSV)
    print("MD                          :", OUTPUT_MD)
    print("")
    print("Persistence executed        : NO")
    print("KnowledgeBridge executed   : NO")
    print("Vault changed              : NO")

if __name__ == "__main__":
    try:
        main()
    except ImportError:
        print("ERRO: PyMuPDF (fitz) não está instalado.")
        print("Instale com: python -m pip install pymupdf")
        sys.exit(3)
