from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
TRIAGE = REPORTS / "PCIP11_MULTIFORMAT_TRIAGE_0695_2R3_FIXED.csv"
CANDIDATES = REPORTS / "PCIP11_METRIC_PROMOTION_CANDIDATES_0695_6R2.csv"

TARGET_SHA256 = "96EE96B5EE4177805CDC97B8FE5DFD1D5E007FDF977FE9038F76B24B17017DF3"

KEYWORDS = [
    "relatório gerencial",
    "data-base",
    "data base",
    "posição em",
    "referente a",
    "mês de",
    "mês",
    "janeiro de 2026",
    "fevereiro de 2026",
    "março de 2026",
    "abril de 2026",
    "maio de 2026",
    "junho de 2026",
    "julho de 2026",
    "agosto de 2026",
    "setembro de 2026",
    "outubro de 2026",
    "novembro de 2026",
    "dezembro de 2026",
    "jan-26",
    "fev-26",
    "mar-26",
    "abr-26",
    "mai-26",
    "jun-26",
    "jul-26",
    "ago-26",
    "set-26",
    "out-26",
    "nov-26",
    "dez-26",
]

MONTH_PT = {
    "janeiro": "01",
    "fevereiro": "02",
    "março": "03",
    "marco": "03",
    "abril": "04",
    "maio": "05",
    "junho": "06",
    "julho": "07",
    "agosto": "08",
    "setembro": "09",
    "outubro": "10",
    "novembro": "11",
    "dezembro": "12",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"Unable to decode {path}")


def get(row: dict[str, str], *names: str) -> str:
    normalized = {(k or "").strip().lstrip("\ufeff"): (v or "").strip()
                  for k, v in row.items()}
    for name in names:
        value = normalized.get(name)
        if value:
            return value
    return ""


def load_pdf_pages(pdf_path: Path) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "Biblioteca pypdf não instalada. Execute: python -m pip install pypdf"
        ) from exc

    reader = PdfReader(str(pdf_path))
    pages = []
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            pages.append(page.extract_text() or "")
        except Exception as exc:
            pages.append(f"[ERRO AO EXTRAIR PÁGINA {page_number}: {exc}]")
    return pages


def find_target_document() -> tuple[Path, dict[str, str], dict[str, str]]:
    triage_rows = read_csv(TRIAGE)
    candidate_rows = read_csv(CANDIDATES)

    triage_match = None
    for row in triage_rows:
        sha = get(row, "SHA256", "Sha256", "sha256").upper()
        if sha == TARGET_SHA256:
            triage_match = row
            break

    candidate_match = None
    for row in candidate_rows:
        sha = get(row, "SHA256", "Sha256", "sha256").upper()
        if sha == TARGET_SHA256:
            candidate_match = row
            break

    if triage_match is None:
        raise RuntimeError("SHA não encontrado no TRIAGE.")

    relative_path = get(
        triage_match,
        "FilePath",
        "RelativePath",
        "Path",
        "FullPath",
        "SourcePath",
        "File_Name",
    )

    # Known legacy column names / fallback.
    if not relative_path:
        for key in triage_match:
            if "path" in key.lower() and triage_match[key]:
                relative_path = triage_match[key].strip()
                break

    if relative_path:
        relative_path = relative_path.replace("/", "\\")
        candidate_path = ROOT / relative_path
        if candidate_path.exists():
            return candidate_path, triage_match, candidate_match or {}

    # Strong fallback from the previously established manifest/tree location.
    fallback = ROOT / "data" / "patria" / "PCIP11" / "2026" / "Relatório Gerencial.pdf"
    if fallback.exists():
        return fallback, triage_match, candidate_match or {}

    # Search by SHA-associated filename or exact basename as a last local read-only fallback.
    filename = get(triage_match, "FileName", "Filename", "file_name")
    matches = []
    for path in ROOT.glob("data/patria/PCIP11/**/*.pdf"):
        if filename and path.name.casefold() == filename.casefold():
            matches.append(path)
    if len(matches) == 1:
        return matches[0], triage_match, candidate_match or {}

    raise FileNotFoundError(
        "PDF alvo não encontrado localmente. SHA="
        + TARGET_SHA256
    )


def normalize_text(text: str) -> str:
    replacements = {
        "\xa0": " ",
        "\r": " ",
        "\n": " ",
        "\u2013": "-",
        "\u2014": "-",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text)


def extract_temporal_patterns(text: str) -> dict[str, list[str]]:
    normalized = normalize_text(text)
    months = []

    for month, number in MONTH_PT.items():
        for match in re.finditer(
            rf"\b{month}\s+(?:de\s+)?((?:19|20)\d{{2}})\b",
            normalized,
            flags=re.IGNORECASE,
        ):
            months.append(f"{match.group(1)}-{number}")

    encoded_dates = sorted(set(
        re.findall(
            r"\b((?:19|20)\d{2})[-/]([01]\d)[-/]([0-3]\d)\b",
            normalized
        )
    ))
    encoded = [f"{y}-{m}-{d}" for y, m, d in encoded_dates]

    slash_dates = sorted(set(
        re.findall(
            r"\b([0-3]?\d)/([01]?\d)/((?:19|20)\d{2})\b",
            normalized
        )
    ))
    slash = [f"{y:04d}-{int(m):02d}-{int(d):02d}" for d, m, y in slash_dates]

    short_months = {
        "jan": "01", "fev": "02", "mar": "03", "abr": "04",
        "mai": "05", "jun": "06", "jul": "07", "ago": "08",
        "set": "09", "out": "10", "nov": "11", "dez": "12",
    }

    abbreviated = []
    for short, number in short_months.items():
        for match in re.finditer(
            rf"\b{short}[./-]?(\d{{2}})\b",
            normalized.casefold(),
        ):
            yy = int(match.group(1))
            year = 2000 + yy if yy <= 49 else 1900 + yy
            abbreviated.append(f"{year:04d}-{number}")

    return {
        "month_year": sorted(set(months)),
        "iso_dates": encoded + slash,
        "abbreviated_months": sorted(set(abbreviated)),
    }


def print_contexts(text: str, keyword: str, radius: int = 220) -> int:
    normalized = normalize_text(text)
    lower = normalized.casefold()
    needle = keyword.casefold()

    positions = [m.start() for m in re.finditer(re.escape(needle), lower)]
    for position in positions[:20]:
        start = max(0, position - radius)
        end = min(len(normalized), position + len(keyword) + radius)
        print(f"  CONTEXTO: ...{normalized[start:end]}...")
    return len(positions)


def main() -> None:
    pdf_path, triage_row, candidate_row = find_target_document()
    pages = load_pdf_pages(pdf_path)
    full_text = "\n".join(pages)

    print("0695.7 TARGET TEMPORAL DIAGNOSTIC R1")
    print("=" * 110)
    print(f"Target SHA256       : {TARGET_SHA256}")
    print(f"PDF                 : {pdf_path}")
    print(f"PDF exists          : {pdf_path.exists()}")
    print(f"Pages extracted     : {len(pages)}")
    print(f"Extracted chars     : {len(full_text):,}")
    print()

    print("TRIAGE METADATA")
    print("-" * 110)
    for key in ("SHA256", "FileName", "Document_Year", "Storage_Year",
                "Document_Period", "Content_Periods", "Content_Dates",
                "Content_Months", "Content_Quarters"):
        value = get(triage_row, key, key.replace("_", " "))
        if value:
            print(f"{key:22}: {value}")

    print()
    print("CANDIDATE SAMPLE")
    print("-" * 110)
    for key in ("Metric", "Value", "Original_Unit", "Resolved_Unit", "Period"):
        value = get(candidate_row, key, key.replace("_", " "))
        if value:
            print(f"{key:22}: {value}")

    patterns = extract_temporal_patterns(full_text)

    print()
    print("TEMPORAL PATTERNS FOUND IN RAW PDF")
    print("-" * 110)
    for name, values in patterns.items():
        print(f"{name:22}: {values}")

    print()
    print("KEYWORD CONTEXTS")
    print("-" * 110)
    total_contexts = 0
    seen = set()

    for keyword in KEYWORDS:
        count = print_contexts(full_text, keyword)
        if count:
            print(f"\nKEYWORD '{keyword}' -> {count} occurrence(s)")
            total_contexts += min(count, 20)
        if keyword.casefold() not in seen:
            seen.add(keyword.casefold())

    print()
    print("PAGE-LEVEL MONTH/YEAR SIGNALS")
    print("-" * 110)
    for page_number, page_text in enumerate(pages, start=1):
        normalized = normalize_text(page_text)
        found = []

        for month, number in MONTH_PT.items():
            if re.search(
                rf"\b{month}\s+(?:de\s+)?((?:19|20)\d{{2}})\b",
                normalized,
                re.IGNORECASE,
            ):
                found.append(f"{month}+year")

        for short in ("jan", "fev", "mar", "abr", "mai", "jun",
                      "jul", "ago", "set", "out", "nov", "dez"):
            if re.search(rf"\b{short}[./-]\d{{2}}\b", normalized.casefold()):
                found.append(f"{short}/yy")

        if found:
            print(f"Page {page_number:03d}: {sorted(set(found))}")

    print()
    print("=" * 110)
    print("DIAGNOSTIC CONCLUSION")
    print(f"Keyword context groups shown : {total_contexts}")
    print("Vault changed                 : NO")
    print("Metric promoted               : NO")
    print("Raw PDF modified              : NO")


if __name__ == "__main__":
    # UTF-8 on Windows consoles.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
