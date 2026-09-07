from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

CANDIDATES_FILE = REPORTS / "PCIP11_METRIC_PROMOTION_CANDIDATES_0695_6R2.csv"
TRIAGE_FILE = REPORTS / "PCIP11_MULTIFORMAT_TRIAGE_0695_2R3_FIXED.csv"

OUTPUT_CSV = REPORTS / "PCIP11_0695_7_TEMPORAL_RESOLUTION_R1.csv"
OUTPUT_MD = REPORTS / "PCIP11_0695_7_TEMPORAL_RESOLUTION_R1.md"

# Evidence from the source UI shown during the investigation:
# available archive years are 2019..2026.
ARCHIVE_YEARS = set(range(2019, 2027))

MONTHS_PT = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "março": 3,
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

BANNED_REFERENCE_PERIODS = {
    "2003-12": "known legal/reference false-positive pattern observed in 0695 legacy extraction"
}


def read_csv(path: Path) -> list[dict[str, str]]:
    last_error = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError as exc:
            last_error = exc
    raise last_error or RuntimeError(f"Unable to read {path}")


def normalize_key(value: str) -> str:
    return (value or "").strip().lstrip("\ufeff")


def row_get(row: dict[str, str], *names: str) -> str:
    normalized = {normalize_key(k): (v or "").strip() for k, v in row.items()}
    for name in names:
        value = normalized.get(name)
        if value:
            return value
    return ""


def first_int_year(text: str) -> int | None:
    match = re.search(r"\b((?:19|20)\d{2})\b", text or "")
    if not match:
        return None
    return int(match.group(1))


def valid_date_ymd(value: str) -> bool:
    try:
        y, m, d = [int(x) for x in value.split("-")]
        date(y, m, d)
        return True
    except Exception:
        return False


def parse_dates(value: str) -> list[str]:
    if not value:
        return []
    found = re.findall(r"\b((?:19|20)\d{2}-\d{2}-\d{2})\b", value)
    return sorted({v for v in found if valid_date_ymd(v)})


def parse_months(value: str) -> list[str]:
    if not value:
        return []
    found = re.findall(r"\b((?:19|20)\d{2}-\d{2})\b", value)
    result = []
    for period in found:
        try:
            y, m = [int(x) for x in period.split("-")]
            if 1 <= m <= 12:
                result.append(period)
        except Exception:
            pass
    return sorted(set(result))


def parse_periods_field(value: str) -> list[str]:
    months = parse_months(value)
    dates = parse_dates(value)
    return sorted(set(months + [d[:7] for d in dates]))


def filename_periods(filename: str) -> list[str]:
    if not filename:
        return []

    periods: set[str] = set()

    # Portuguese month + year, e.g. "Agosto 2024".
    lower = filename.casefold()
    for month_name, month_number in MONTHS_PT.items():
        pattern = rf"\b{re.escape(month_name)}\s+((?:19|20)\d{{2}})\b"
        for match in re.finditer(pattern, lower, re.IGNORECASE):
            periods.add(f"{int(match.group(1)):04d}-{month_number:02d}")

    # Encoded reports such as REL30012026V01.
    for value in re.findall(r"(?:REL|ACE|FRV)(\d{8})V\d+", filename.upper()):
        try:
            day = int(value[0:2])
            month = int(value[2:4])
            year = int(value[4:8])
            date(year, month, day)
            periods.add(f"{year:04d}-{month:02d}")
        except Exception:
            pass

    # Generic YYYY-MM in filename.
    periods.update(parse_months(filename))
    return sorted(periods)


def extract_manifest_years(triage_row: dict[str, str]) -> tuple[str, str, str]:
    document_year = row_get(
        triage_row,
        "Document_Year",
        "Document Year",
        "Manifest_Year",
        "Manifest Year",
    )
    storage_year = row_get(
        triage_row,
        "Storage_Year",
        "Storage Year",
        "StorageYear",
    )
    document_period_manifest = row_get(
        triage_row,
        "Document_Period_Manifest",
        "Document Period Manifest",
        "Document_Period",
    )
    return document_year, storage_year, document_period_manifest


def score_candidate(
    filename: str,
    current_period: str,
    content_dates: list[str],
    content_months: list[str],
    content_periods: list[str],
    document_year: str,
    storage_year: str,
    document_period_manifest: str,
) -> dict[str, str]:
    # Build candidate observations.
    strong_dates = [d for d in content_dates if int(d[:4]) in ARCHIVE_YEARS]
    strong_date_months = sorted({d[:7] for d in strong_dates})

    filename_candidates = [
        p for p in filename_periods(filename) if int(p[:4]) in ARCHIVE_YEARS
    ]

    manifest_candidates = parse_periods_field(document_period_manifest)
    manifest_candidates = [p for p in manifest_candidates if int(p[:4]) in ARCHIVE_YEARS]

    triage_month_candidates = [
        p for p in set(content_months + content_periods)
        if int(p[:4]) in ARCHIVE_YEARS and p != "2003-12"
    ]
    triage_month_candidates = sorted(set(triage_month_candidates))

    archive_year_candidates = set()
    for raw in (document_year, storage_year):
        y = first_int_year(raw)
        if y in ARCHIVE_YEARS:
            archive_year_candidates.add(y)

    scores: Counter[str] = Counter()
    reasons: defaultdict[str, list[str]] = defaultdict(list)

    for period in strong_date_months:
        scores[period] += 100
        reasons[period].append("explicit_content_date")

    for period in filename_candidates:
        scores[period] += 50
        reasons[period].append("filename_period")

    for period in manifest_candidates:
        scores[period] += 40
        reasons[period].append("manifest_period")

    for period in triage_month_candidates:
        scores[period] += 10
        reasons[period].append("content_month")

    # Archive/storage year is supporting evidence only.
    for period in list(scores):
        if int(period[:4]) in archive_year_candidates:
            scores[period] += 15
            reasons[period].append("archive_or_storage_year_alignment")

    # Explicit dates are the strongest temporal signal available in the
    # legacy artifacts. When several dates exist, use the latest date that
    # falls inside the publisher archive range. Older dates are treated as
    # historical references unless another stronger signal contradicts it.
    if strong_dates:
        latest_date = max(strong_dates)
        latest_month = latest_date[:7]
        return {
            "resolved_period": latest_month,
            "status": "RESOLVED",
            "confidence": "HIGH",
            "reason": "latest_explicit_date_within_archive_range",
            "excluded_current_period": (
                "known_false_positive_2003-12"
                if current_period in BANNED_REFERENCE_PERIODS
                else ""
            ),
        }

    if not scores:
        return {
            "resolved_period": "",
            "status": "REVIEW",
            "confidence": "LOW",
            "reason": "no_usable_temporal_signal_in_archive_range",
            "excluded_current_period": "",
        }

    ranked = scores.most_common()
    best_period, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else None

    # Strong, unambiguous filename/manifest evidence can resolve when no date exists.
    best_reasons = set(reasons[best_period])

    if second_score is None and (
        "filename_period" in best_reasons
        or "manifest_period" in best_reasons
    ):
        return {
            "resolved_period": best_period,
            "status": "RESOLVED",
            "confidence": "HIGH",
            "reason": "+".join(sorted(best_reasons)),
            "excluded_current_period": (
                "known_false_positive_2003-12"
                if current_period in BANNED_REFERENCE_PERIODS
                else ""
            ),
        }

    if second_score is not None and best_score == second_score:
        return {
            "resolved_period": best_period,
            "status": "REVIEW",
            "confidence": "MEDIUM",
            "reason": "multiple_temporal_candidates_same_strength",
            "excluded_current_period": (
                "known_false_positive_2003-12"
                if current_period in BANNED_REFERENCE_PERIODS
                else ""
            ),
        }

    return {
        "resolved_period": best_period,
        "status": "REVIEW",
        "confidence": "MEDIUM",
        "reason": "best_temporal_signal_is_heuristic_not_explicit_enough",
        "excluded_current_period": (
            "known_false_positive_2003-12"
            if current_period in BANNED_REFERENCE_PERIODS
            else ""
        ),
    }


def main() -> None:
    if not CANDIDATES_FILE.exists():
        raise FileNotFoundError(CANDIDATES_FILE)
    if not TRIAGE_FILE.exists():
        raise FileNotFoundError(TRIAGE_FILE)

    candidates = read_csv(CANDIDATES_FILE)
    triage = read_csv(TRIAGE_FILE)

    triage_by_sha = {
        row_get(row, "SHA256", "Sha256", "sha256").upper(): row
        for row in triage
        if row_get(row, "SHA256", "Sha256", "sha256")
    }

    output_rows: list[dict[str, str]] = []

    for index, candidate in enumerate(candidates, start=1):
        sha = row_get(candidate, "SHA256", "Sha256", "sha256").upper()
        triage_row = triage_by_sha.get(sha, {})

        filename = row_get(candidate, "FileName", "Filename", "file_name")
        current_period = row_get(candidate, "Period", "Current Period", "period")

        if not filename:
            filename = row_get(triage_row, "FileName", "Filename", "file_name")

        document_year, storage_year, document_period_manifest = extract_manifest_years(
            triage_row
        )

        content_periods_raw = row_get(
            triage_row,
            "Content_Periods",
            "Content Periods",
            "content_periods",
        )
        content_dates_raw = row_get(
            triage_row,
            "Content_Dates",
            "Content Dates",
            "content_dates",
        )
        content_months_raw = row_get(
            triage_row,
            "Content_Months",
            "Content Months",
            "content_months",
        )
        content_quarters_raw = row_get(
            triage_row,
            "Content_Quarters",
            "Content Quarters",
            "content_quarters",
        )

        content_dates = sorted(set(
            parse_dates(content_dates_raw)
            + parse_dates(content_periods_raw)
        ))
        content_months = parse_months(content_months_raw)
        content_periods = parse_periods_field(content_periods_raw)

        resolution = score_candidate(
            filename=filename,
            current_period=current_period,
            content_dates=content_dates,
            content_months=content_months,
            content_periods=content_periods,
            document_year=document_year,
            storage_year=storage_year,
            document_period_manifest=document_period_manifest,
        )

        current_year = None
        try:
            current_year = int(current_period[:4])
        except Exception:
            pass
        current_period_is_suspect = (
            current_period == "2003-12"
            or (current_year is not None and current_year not in ARCHIVE_YEARS)
        )

        output_rows.append(
            {
                "Row": str(index),
                "SHA256": sha,
                "FileName": filename,
                "Original_Identity": row_get(
                    candidate, "Original_Identity", "Original Identity"
                ),
                "Current_Period_Legacy": current_period,
                "Resolved_Period": resolution["resolved_period"],
                "Temporal_Status": resolution["status"],
                "Temporal_Confidence": resolution["confidence"],
                "Temporal_Reason": resolution["reason"],
                "Current_Period_Suspect": "YES" if current_period_is_suspect else "NO",
                "Excluded_Current_Period": resolution["excluded_current_period"],
                "Document_Year": document_year,
                "Storage_Year": storage_year,
                "Document_Period_Manifest": document_period_manifest,
                "Content_Dates": "|".join(content_dates),
                "Content_Periods": content_periods_raw,
                "Content_Months": "|".join(content_months),
                "Content_Quarters": content_quarters_raw,
                "Archive_Years_Observed": ",".join(str(y) for y in sorted(ARCHIVE_YEARS)),
            }
        )

    REPORTS.mkdir(parents=True, exist_ok=True)

    fieldnames = list(output_rows[0].keys()) if output_rows else []
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    status_counts = Counter(row["Temporal_Status"] for row in output_rows)
    suspect_counts = Counter(row["Current_Period_Suspect"] for row in output_rows)
    resolved_periods = Counter(
        row["Resolved_Period"] for row in output_rows if row["Resolved_Period"]
    )

    with OUTPUT_MD.open("w", encoding="utf-8") as handle:
        handle.write("# 0695.7 Temporal Resolution R1\n\n")
        handle.write("## Purpose\n\n")
        handle.write(
            "Read-only temporal resolution layer for the 74 0695.7 metric candidates. "
            "It preserves the legacy period and derives a separate candidate canonical "
            "period without modifying the Vault or promoting metrics.\n\n"
        )
        handle.write("## Inputs\n\n")
        handle.write(f"- Candidates: `{CANDIDATES_FILE.name}` ({len(candidates)} rows)\n")
        handle.write(f"- Triage: `{TRIAGE_FILE.name}` ({len(triage)} rows)\n")
        handle.write("- Archive years used as auxiliary evidence: 2019..2026\n\n")

        handle.write("## Status summary\n\n")
        for key in ("RESOLVED", "REVIEW", "HOLD"):
            handle.write(f"- {key}: {status_counts.get(key, 0)}\n")

        handle.write(
            f"- Legacy Current_Period flagged as suspect: "
            f"{suspect_counts.get('YES', 0)}\n"
        )

        handle.write("\n## Resolved periods\n\n")
        for period, count in sorted(resolved_periods.items()):
            handle.write(f"- {period}: {count}\n")

        handle.write("\n## Important rule\n\n")
        handle.write(
            "The legacy `Current_Period` is never overwritten. `Resolved_Period` is a "
            "separate semantic result. No result from this script authorizes Vault writes "
            "or metric promotion.\n"
        )

    print("0695.7 TEMPORAL RESOLUTION R1")
    print("=" * 100)
    print(f"Candidates processed : {len(candidates)}")
    print(f"Triage rows          : {len(triage)}")
    print(f"RESOLVED             : {status_counts.get('RESOLVED', 0)}")
    print(f"REVIEW               : {status_counts.get('REVIEW', 0)}")
    print(f"HOLD                 : {status_counts.get('HOLD', 0)}")
    print(f"Legacy period suspect: {suspect_counts.get('YES', 0)}")
    print(f"CSV                  : {OUTPUT_CSV}")
    print(f"MD                   : {OUTPUT_MD}")
    print("Vault changed        : NO")
    print("Metric promoted      : NO")


if __name__ == "__main__":
    main()
