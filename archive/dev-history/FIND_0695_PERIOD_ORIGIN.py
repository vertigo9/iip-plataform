from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()

TERMS = [
    "Period",
    "period",
    "2003-12",
    "0695_6",
    "0695.6",
]


def main() -> None:
    print("0695 PERIOD ORIGIN SEARCH")
    print("=" * 80)
    print(f"Root: {ROOT}")
    print()

    extensions = {
        ".py",
        ".ps1",
        ".csv",
        ".md",
        ".json",
        ".yaml",
        ".yml",
        ".txt",
    }

    excluded = {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".venv",
        "venv",
        "node_modules",
    }

    matches = []

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue

        if path.suffix.lower() not in extensions:
            continue

        if any(part in excluded for part in path.parts):
            continue

        try:
            text = path.read_text(
                encoding="utf-8-sig",
                errors="ignore",
            )
        except Exception:
            continue

        found_terms = [
            term
            for term in TERMS
            if term in text
        ]

        if found_terms:
            matches.append(
                (
                    path,
                    found_terms,
                )
            )

    print(f"Files with matches: {len(matches)}")
    print()

    for path, found_terms in matches:
        print(path.relative_to(ROOT))
        print(f"  Terms: {', '.join(found_terms)}")

    print()
    print("SEARCH COMPLETE")
    print("Vault changed: NO")
    print("Metric promoted: NO")


if __name__ == "__main__":
    main()