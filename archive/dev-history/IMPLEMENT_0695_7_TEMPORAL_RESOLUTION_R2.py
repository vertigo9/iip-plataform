from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

CANDIDATES_FILE = REPORTS / "PCIP11_METRIC_PROMOTION_CANDIDATES_0695_6R2.csv"
TRIAGE_FILE = REPORTS / "PCIP11_MULTIFORMAT_TRIAGE_0695_2R3_FIXED.csv"

OUTPUT_CSV = REPORTS / "PCIP11_0695_7_TEMPORAL_RESOLUTION_R2.csv"
OUTPUT_MD = REPORTS / "PCIP11_0695_7_TEMPORAL_RESOLUTION_R2.md"

MONTHS_PT = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

MONTHS_ABBR = {
    "jan": 1,
    "fev": 2,
    "mar": 3,
    "abr": 4,
    "mai": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "set": 9,
    "out": 10,
    "nov": 11,
    "dez": 12,
}

ARCHIVE_YEARS = set(range(2019, 2027))
KNOWN_FALSE_POSITIVES = {"2003-12": "legacy legal/reference contamination"}


def configure_utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def read_csv(path: Path) -> list[dict[str, str]]:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"Não foi possível ler CSV: {path}")


def get(row: dict[str, str], *names: str) -> str:
    normalized = {
        (key or "").strip().lstrip("\ufeff"): (value or "").strip()
        for key, value in row.items()
    }
    for name in names:
        value = normalized.get(name)
        if value:
            return value
    return ""


def normalize_text(text: str) -> str:
    replacements = {
        "\xa0": " ",
        "\r": " ",
        "\n": " ",
        "\u2013": "-",
        "\u2014": "-",
        "\ufeff": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip()


def valid_ymd(year: int, month: int, day: int) -> bool:
    try:
        date(year, month, day)
        return True
    except ValueError:
        return False


def month_year_pairs(text: str) -> list[str]:
    text = normalize_text(text)
    result: set[str] = set()

    for month_name, month_number in MONTHS_PT.items():
        pattern = rf"\b{re.escape(month_name)}\s+(?:de\s+)?((?:19|20)\d{{2}})\b"
        for match in re.finditer(pattern, text, re.IGNORECASE):
            result.add(f"{int(match.group(1)):04d}-{month_number:02d}")

    for abbr, month_number in MONTHS_ABBR.items():
        pattern = rf"\b{abbr}[./-](\d{{2}})\b"
        for match in re.finditer(pattern, text.casefold()):
            yy = int(match.group(1))
            year = 2000 + yy if yy <= 49 else 1900 + yy
            result.add(f"{year:04d}-{month_number:02d}")

    return sorted(result)


def explicit_dates(text: str) -> list[str]:
    text = normalize_text(text)
    result: set[str] = set()

    # dd/mm/yyyy
    for day, month, year in re.findall(
        r"\b([0-3]?\d)/([01]?\d)/((?:19|20)\d{2})\b",
        text,
    ):
        y, m, d = int(year), int(month), int(day)
        if valid_ymd(y, m, d):
            result.add(f"{y:04d}-{m:02d}-{d:02d}")

    # yyyy-mm-dd
    for year, month, day in re.findall(
        r"\b((?:19|20)\d{2})[-/]([01]\d)[-/]([0-3]\d)\b",
        text,
    ):
        y, m, d = int(year), int(month), int(day)
        if valid_ymd(y, m, d):
            result.add(f"{y:04d}-{m:02d}-{d:02d}")

    return sorted(result)


def extract_pdf_pages(pdf_path: Path, max_pages: int = 4) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "pypdf não está instalado. Execute: python -m pip install pypdf"
        ) from exc

    reader = PdfReader(str(pdf_path))
    pages: list[str] = []
    for page in reader.pages[:max_pages]:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return pages


def find_path_candidates(triage_row: dict[str, str]) -> list[Path]:
    candidates: list[Path] = []

    possible_fields = (
        "FilePath",
        "RelativePath",
        "Path",
        "FullPath",
        "SourcePath",
        "File_Name",
    )

    for field in possible_fields:
        raw = get(triage_row, field)
        if raw:
            value = raw.replace("/", "\\")
            path = ROOT / value
            candidates.append(path)

    for key, value in triage_row.items():
        if not value:
            continue
        if "path" in (key or "").lower():
            candidates.append(ROOT / value.replace("/", "\\"))

    filename = get(triage_row, "FileName", "Filename", "file_name")
    if filename:
        for path in ROOT.glob("data/patria/PCIP11/**/*.pdf"):
            if path.name.casefold() == filename.casefold():
                candidates.append(path)

    return candidates


def locate_pdf(
    triage_row: dict[str, str],
    sha256: str,
) -> Path | None:
    for path in find_path_candidates(triage_row):
        if path.exists() and path.is_file() and path.suffix.casefold() == ".pdf":
            return path

    # Known file tree fallback for the investigated 0695 set.
    filename = get(triage_row, "FileName", "Filename", "file_name")
    if filename:
        matches = [
            p for p in ROOT.glob("data/patria/PCIP11/**/*.pdf")
            if p.name.casefold() == filename.casefold()
        ]
        if len(matches) == 1:
            return matches[0]

    # Last resort: filename is often "Relatório Gerencial.pdf" in year folders.
    # Try the folder represented by storage/document year metadata.
    for year_field in ("Document_Year", "Storage_Year"):
        year_raw = get(triage_row, year_field, year_field.replace("_", " "))
        if year_raw.isdigit():
            year = year_raw
            if filename:
                candidate = (
                    ROOT / "data" / "patria" / "PCIP11" / year / filename
                )
                if candidate.exists():
                    return candidate

    return None


def match_month(text: str, pattern: str) -> str:
    match = re.search(pattern, normalize_text(text), flags=re.IGNORECASE)
    if not match:
        return ""
    month_name = match.group(1).casefold()
    year = int(match.group(2))
    month = MONTHS_PT.get(month_name)
    if month is None:
        return ""
    return f"{year:04d}-{month:02d}"


def detect_header_period(text: str) -> tuple[str, str]:
    normalized = normalize_text(text)

    # Strongest: title/header with report + month/year.
    title_patterns = [
        r"(?:relat[oó]rio\s+gerencial).*?\b("
        + "|".join(MONTHS_PT.keys())
        + r")\s+(?:de\s+)?((?:19|20)\d{2})\b",
        r"(?:relat[oó]rio\s+mensal).*?\b("
        + "|".join(MONTHS_PT.keys())
        + r")\s+(?:de\s+)?((?:19|20)\d{2})\b",
        r"\b("
        + "|".join(MONTHS_PT.keys())
        + r")\s+((?:19|20)\d{2})\b",
    ]

    for pattern in title_patterns:
        period = match_month(normalized, pattern)
        if period and int(period[:4]) in ARCHIVE_YEARS:
            return period, "TITLE_OR_HEADER_MONTH_YEAR"

    # Strong: "PANORAMA DE JANEIRO/26", "PANORAMA DE JANEIRO 2026".
    panorama = re.search(
        r"\bPANORAMA\s+DE\s+("
        + "|".join(MONTHS_PT.keys())
        + r")(?:/|\s+)((?:19|20)?\d{2})\b",
        normalized,
        flags=re.IGNORECASE,
    )
    if panorama:
        month_name = panorama.group(1).casefold()
        year_token = panorama.group(2)
        if len(year_token) == 2:
            year = 2000 + int(year_token)
        else:
            year = int(year_token)
        month = MONTHS_PT[month_name]
        period = f"{year:04d}-{month:02d}"
        if year in ARCHIVE_YEARS:
            return period, "PANORAMA_PERIOD"

    return "", ""


def detect_base_date_period(text: str) -> tuple[str, str]:
    normalized = normalize_text(text)

    patterns = [
        r"\bdata\s*[- ]?base\s*(?:de\s*)?([0-3]?\d)/([01]?\d)(?:/|/?)((?:19|20)\d{2})",
        r"\bdata\s*[- ]?base\s*(?:de\s*)?([0-3]?\d)/([01]?\d)/((?:19|20)\d{2})",
    ]

    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if not match:
            continue
        day, month, year = map(int, match.groups())
        if valid_ymd(year, month, day):
            period = f"{year:04d}-{month:02d}"
            if year in ARCHIVE_YEARS:
                return period, "DATA_BASE_EXPLICIT"

    return "", ""


def detect_competence_context(text: str) -> tuple[str, str]:
    normalized = normalize_text(text)

    strong_patterns = [
        r"\bresultado\s+(?:do|de)\s+("
        + "|".join(MONTHS_PT.keys())
        + r")\s+(?:de\s+)?((?:19|20)\d{2})\b",
        r"\b(?:encerramos|encerrou|encerrado|referente)\s+(?:o\s+)?m[eê]s\s+(?:de\s+)?("
        + "|".join(MONTHS_PT.keys())
        + r")\s+(?:de\s+)?((?:19|20)\d{2})\b",
    ]

    for pattern in strong_patterns:
        period = match_month(normalized, pattern)
        if period and int(period[:4]) in ARCHIVE_YEARS:
            return period, "COMPETENCE_CONTEXT"

    # "mês de janeiro" near "2026" is weaker; use only in first 2 pages.
    return "", ""


def triage_period_signals(triage_row: dict[str, str]) -> dict[str, str]:
    content_periods = get(
        triage_row, "Content_Periods", "Content Periods", "content_periods"
    )
    content_dates = get(
        triage_row, "Content_Dates", "Content Dates", "content_dates"
    )
    filename = get(triage_row, "FileName", "Filename", "file_name")

    months = month_year_pairs(content_periods + " " + content_dates)
    dates = explicit_dates(content_dates)
    filename_months = month_year_pairs(filename)

    return {
        "content_months": "|".join(months),
        "content_dates_parsed": "|".join(dates),
        "filename_periods": "|".join(filename_months),
    }


def resolve_document_period(
    *,
    pdf_text_first_pages: str,
    filename: str,
    triage_row: dict[str, str],
    legacy_period: str,
) -> dict[str, str]:
    title_period, title_reason = detect_header_period(pdf_text_first_pages)
    if title_period:
        return {
            "resolved_period": title_period,
            "status": "RESOLVED",
            "confidence": "HIGH",
            "reason": title_reason,
            "evidence": f"first_pages::{title_reason}",
        }

    base_period, base_reason = detect_base_date_period(pdf_text_first_pages)
    if base_period:
        return {
            "resolved_period": base_period,
            "status": "RESOLVED",
            "confidence": "HIGH",
            "reason": base_reason,
            "evidence": f"first_pages::{base_reason}",
        }

    competence_period, competence_reason = detect_competence_context(
        pdf_text_first_pages
    )
    if competence_period:
        return {
            "resolved_period": competence_period,
            "status": "RESOLVED",
            "confidence": "HIGH",
            "reason": competence_reason,
            "evidence": f"first_pages::{competence_reason}",
        }

    # Filename is useful only if it actually carries a month/year.
    file_periods = [
        p for p in month_year_pairs(filename)
        if int(p[:4]) in ARCHIVE_YEARS
    ]
    if len(file_periods) == 1:
        return {
            "resolved_period": file_periods[0],
            "status": "RESOLVED",
            "confidence": "MEDIUM",
            "reason": "FILENAME_MONTH_YEAR",
            "evidence": f"filename::{file_periods[0]}",
        }

    # Storage/document year is only an auxiliary year, not enough by itself
    # to invent a month.
    year_candidates = set()
    for field in ("Document_Year", "Storage_Year"):
        raw = get(triage_row, field, field.replace("_", " "))
        if raw.isdigit() and int(raw) in ARCHIVE_YEARS:
            year_candidates.add(int(raw))

    legacy_is_suspect = (
        legacy_period in KNOWN_FALSE_POSITIVES
        or (
            legacy_period
            and legacy_period[:4].isdigit()
            and int(legacy_period[:4]) not in ARCHIVE_YEARS
        )
    )

    if len(file_periods) > 1:
        reason = "MULTIPLE_FILENAME_PERIODS"
    elif year_candidates:
        reason = "YEAR_ONLY_AUXILIARY_SIGNAL"
    elif triage_period_signals(triage_row)["content_months"]:
        reason = "CONTENT_MONTHS_ONLY_NOT_DOCUMENT_PERIOD"
    else:
        reason = "NO_SEMANTIC_DOCUMENT_PERIOD_SIGNAL"

    return {
        "resolved_period": "",
        "status": "REVIEW",
        "confidence": "LOW",
        "reason": reason,
        "evidence": "manual_review_required",
        "legacy_period_suspect": "YES" if legacy_is_suspect else "NO",
    }


def main() -> None:
    if not CANDIDATES_FILE.exists():
        raise FileNotFoundError(CANDIDATES_FILE)
    if not TRIAGE_FILE.exists():
        raise FileNotFoundError(TRIAGE_FILE)

    candidates = read_csv(CANDIDATES_FILE)
    triage = read_csv(TRIAGE_FILE)

    triage_by_sha = {
        get(row, "SHA256", "Sha256", "sha256").upper(): row
        for row in triage
        if get(row, "SHA256", "Sha256", "sha256")
    }

    output_rows: list[dict[str, str]] = []
    pdf_cache: dict[str, tuple[str, str, str]] = {}

    for index, candidate in enumerate(candidates, start=1):
        sha = get(candidate, "SHA256", "Sha256", "sha256").upper()
        triage_row = triage_by_sha.get(sha, {})

        filename = get(candidate, "FileName", "Filename", "file_name")
        if not filename:
            filename = get(triage_row, "FileName", "Filename", "file_name")

        legacy_period = get(candidate, "Period", "Current Period", "period")
        pdf_path = locate_pdf(triage_row, sha)

        cache_key = str(pdf_path) if pdf_path else f"NOFILE::{sha}"
        if cache_key not in pdf_cache:
            if pdf_path:
                try:
                    pages = extract_pdf_pages(pdf_path, max_pages=4)
                    first_pages = "\n".join(pages)
                    pdf_cache[cache_key] = (
                        first_pages,
                        "YES",
                        str(pdf_path),
                    )
                except Exception as exc:
                    pdf_cache[cache_key] = (
                        f"[PDF_ERROR] {exc}",
                        "ERROR",
                        str(pdf_path),
                    )
            else:
                pdf_cache[cache_key] = ("", "NO", "")

        first_pages, pdf_status, resolved_path = pdf_cache[cache_key]

        resolution = resolve_document_period(
            pdf_text_first_pages=first_pages,
            filename=filename,
            triage_row=triage_row,
            legacy_period=legacy_period,
        )

        triage_signals = triage_period_signals(triage_row)
        current_year = None
        try:
            current_year = int(legacy_period[:4])
        except Exception:
            pass

        current_period_suspect = (
            legacy_period in KNOWN_FALSE_POSITIVES
            or (current_year is not None and current_year not in ARCHIVE_YEARS)
        )

        output_rows.append(
            {
                "Row": str(index),
                "SHA256": sha,
                "FileName": filename,
                "PDF_Path": resolved_path,
                "PDF_Status": pdf_status,
                "Original_Identity": get(
                    candidate,
                    "Original_Identity",
                    "Original Identity",
                ),
                "Metric": get(candidate, "Metric", "metric"),
                "Value": get(candidate, "Value", "value"),
                "Current_Period_Legacy": legacy_period,
                "Resolved_Period": resolution["resolved_period"],
                "Temporal_Status": resolution["status"],
                "Temporal_Confidence": resolution["confidence"],
                "Temporal_Reason": resolution["reason"],
                "Temporal_Evidence": resolution["evidence"],
                "Current_Period_Suspect": "YES" if current_period_suspect else "NO",
                "Content_Months": triage_signals["content_months"],
                "Content_Dates_Parsed": triage_signals["content_dates_parsed"],
                "Filename_Periods": triage_signals["filename_periods"],
                "Content_Periods_Raw": get(
                    triage_row,
                    "Content_Periods",
                    "Content Periods",
                    "content_periods",
                ),
                "Content_Dates_Raw": get(
                    triage_row,
                    "Content_Dates",
                    "Content Dates",
                    "content_dates",
                ),
                "Document_Year": get(
                    triage_row,
                    "Document_Year",
                    "Document Year",
                ),
                "Storage_Year": get(
                    triage_row,
                    "Storage_Year",
                    "Storage Year",
                ),
            }
        )

    REPORTS.mkdir(parents=True, exist_ok=True)

    fieldnames = list(output_rows[0].keys()) if output_rows else []
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    status_counts = Counter(row["Temporal_Status"] for row in output_rows)
    confidence_counts = Counter(
        row["Temporal_Confidence"] for row in output_rows
    )
    reason_counts = Counter(row["Temporal_Reason"] for row in output_rows)
    period_counts = Counter(
        row["Resolved_Period"] for row in output_rows
        if row["Resolved_Period"]
    )
    pdf_counts = Counter(row["PDF_Status"] for row in output_rows)

    review_rows = [
        row for row in output_rows if row["Temporal_Status"] == "REVIEW"
    ]

    # Detect contradictory resolved periods within the same physical document.
    by_sha: defaultdict[str, set[str]] = defaultdict(set)
    for row in output_rows:
        if row["Resolved_Period"]:
            by_sha[row["SHA256"]].add(row["Resolved_Period"])

    conflicts = {
        sha: sorted(periods)
        for sha, periods in by_sha.items()
        if len(periods) > 1
    }

    with OUTPUT_MD.open("w", encoding="utf-8") as handle:
        handle.write("# 0695.7 Temporal Resolution R2\n\n")
        handle.write(
            "Semantic temporal resolution using the first pages of the source PDF. "
            "Legacy `Current_Period` is preserved and never overwritten. "
            "No Vault write and no metric promotion are performed.\n\n"
        )

        handle.write("## Summary\n\n")
        handle.write(f"- Candidates: {len(candidates)}\n")
        handle.write(f"- RESOLVED: {status_counts.get('RESOLVED', 0)}\n")
        handle.write(f"- REVIEW: {status_counts.get('REVIEW', 0)}\n")
        handle.write(f"- HOLD: {status_counts.get('HOLD', 0)}\n")
        handle.write(
            f"- Legacy period suspect: "
            f"{sum(1 for row in output_rows if row['Current_Period_Suspect'] == 'YES')}\n"
        )
        handle.write(
            f"- Physical documents with contradictory resolved periods: "
            f"{len(conflicts)}\n"
        )
        handle.write(
            f"- PDF status: YES={pdf_counts.get('YES', 0)}, "
            f"NO={pdf_counts.get('NO', 0)}, "
            f"ERROR={pdf_counts.get('ERROR', 0)}\n\n"
        )

        handle.write("## Resolution priority\n\n")
        handle.write("1. Title/header month-year on the first pages.\n")
        handle.write("2. Explicit `Data-base` date.\n")
        handle.write("3. Explicit competence/result context on the first pages.\n")
        handle.write("4. Filename month-year when unique.\n")
        handle.write("5. Content-period lists are never sufficient on their own.\n")
        handle.write(
            "6. Storage/document year alone is auxiliary and cannot invent a month.\n\n"
        )

        handle.write("## Resolved periods\n\n")
        for period, count in sorted(period_counts.items()):
            handle.write(f"- {period}: {count}\n")

        handle.write("\n## Confidence\n\n")
        for confidence, count in sorted(confidence_counts.items()):
            handle.write(f"- {confidence}: {count}\n")

        handle.write("\n## Main reasons\n\n")
        for reason, count in reason_counts.most_common():
            handle.write(f"- {reason}: {count}\n")

        handle.write("\n## REVIEW rows\n\n")
        for row in review_rows:
            handle.write(
                f"- Row {row['Row']} | SHA {row['SHA256']} | "
                f"{row['FileName']} | reason={row['Temporal_Reason']} | "
                f"PDF={row['PDF_Status']}\n"
            )

        handle.write("\n## Safety\n\n")
        handle.write("- Vault changed: NO\n")
        handle.write("- Metric promoted: NO\n")
        handle.write("- Legacy artifacts modified: NO\n")

    print("0695.7 TEMPORAL RESOLUTION R2")
    print("=" * 100)
    print(f"Candidates processed   : {len(candidates)}")
    print(f"RESOLVED               : {status_counts.get('RESOLVED', 0)}")
    print(f"REVIEW                 : {status_counts.get('REVIEW', 0)}")
    print(f"HOLD                   : {status_counts.get('HOLD', 0)}")
    print(f"Legacy period suspect  : {sum(1 for row in output_rows if row['Current_Period_Suspect'] == 'YES')}")
    print(f"PDF extracted          : {pdf_counts.get('YES', 0)}")
    print(f"PDF missing            : {pdf_counts.get('NO', 0)}")
    print(f"PDF extraction errors  : {pdf_counts.get('ERROR', 0)}")
    print(f"Physical period conflicts: {len(conflicts)}")
    print(f"CSV                    : {OUTPUT_CSV}")
    print(f"MD                     : {OUTPUT_MD}")
    print("Vault changed          : NO")
    print("Metric promoted        : NO")


if __name__ == "__main__":
    configure_utf8()
    main()
