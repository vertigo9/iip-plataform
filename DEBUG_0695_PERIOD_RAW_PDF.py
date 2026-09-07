from __future__ import annotations

import re
from pathlib import Path

PDF = Path(r"data\patria\PCIP11\2025\Relatório Gerencial.pdf")

MONTHS = {
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


def extract_text(path: Path) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    except ImportError:
        pass

    try:
        import fitz

        doc = fitz.open(str(path))
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return text

    except ImportError:
        raise SystemExit(
            "Nenhum extrator PDF disponível. "
            "Instale pypdf com: python -m pip install pypdf"
        )


def main() -> None:
    print("0695 RAW PDF PERIOD DEBUG")
    print("=" * 80)

    if not PDF.exists():
        raise SystemExit(f"PDF não encontrado: {PDF}")

    print(f"PDF: {PDF}")
    print()

    text = extract_text(PDF)

    print(f"Extracted characters: {len(text)}")
    print()

    matches = []

    for month, number in MONTHS.items():
        pattern = month + r".{0,30}?((?:19|20)\d{2})"

        for match in re.finditer(pattern, text, re.IGNORECASE):
            year = match.group(1)
            detected = year + "-" + number

            if detected != "2003-12":
                continue

            start = max(0, match.start() - 150)
            end = min(len(text), match.end() + 150)

            matches.append(
                (
                    month,
                    detected,
                    match.group(0),
                    text[start:end],
                )
            )

    print(f"Matches generating 2003-12: {len(matches)}")
    print()

    for index, (month, detected, matched, context) in enumerate(
        matches[:20],
        start=1,
    ):
        print("-" * 80)
        print(f"MATCH #{index}")
        print(f"Month     : {month}")
        print(f"Detected  : {detected}")
        print(f"Matched   : {repr(matched)}")
        print()
        print("CONTEXT:")
        print(context)
        print()

    print("=" * 80)
    print("DEBUG COMPLETE")
    print("Vault changed: NO")
    print("Metric promoted: NO")


if __name__ == "__main__":
    main()