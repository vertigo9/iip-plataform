#!/usr/bin/env python3
"""
D-OBSIDIAN-06.12 R1 — REVIEW GROUP FORENSIC TRIAGE

READ-ONLY / NON-DESTRUCTIVE.

Source:
  reports/D-OBSIDIAN-06.9-R1/

Target:
  the 31 DuplicateGroups with GroupDecision == REVIEW.

The script does NOT delete, move, rename or modify repository files.
It does NOT execute Git commands.

It produces a decision-grade forensic inventory for each REVIEW group,
including:
  - hash/group size
  - all canonicalization members
  - current filesystem existence
  - current SHA-256 where available
  - protection classification
  - CanonicalPath / CanonicalStatus
  - DecisionMatrix matches
  - textual reference evidence
  - structural classification

No automatic deletion authorization is produced.
"""

from __future__ import annotations

import csv
import hashlib
import os
from collections import Counter
from datetime import datetime
from pathlib import Path


EXPECTED = {
    "decision_total": 910,
    "canonical_total": 910,
    "duplicate_total": 430,
    "review_groups": 31,
    "review_rows": 126,
    "has_canonical_groups": 63,
}

TEXT_EXTENSIONS = {
    ".py", ".ps1", ".psm1", ".psd1", ".txt", ".md", ".rst",
    ".json", ".jsonl", ".csv", ".yaml", ".yml", ".toml", ".ini",
    ".cfg", ".conf", ".xml", ".html", ".htm", ".sql", ".sh",
    ".bat", ".cmd", ".gitignore", ".base",
}

SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "node_modules",
}

PROTECTED_EXACT = {
    "src/iip/intelligence/metric_identity.py",
    "src/iip/intelligence/metric_persistence.py",
    "src/iip/intelligence/metric_persistence_adapter.py",
}

PROTECTED_PREFIXES = (
    "data/",
    "vault/",
    "archive/",
    "tests/intelligence/",
    "tests/integration/",
)


def latest_file(directory: Path, pattern: str) -> Path:
    files = list(directory.glob(pattern))
    if not files:
        raise FileNotFoundError(f"Fonte nao encontrada: {pattern}")
    return max(files, key=lambda p: p.stat().st_mtime)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def get_value(row: dict[str, str], *names: str) -> str:
    values = {str(k).lower(): (v or "").strip() for k, v in row.items()}
    for name in names:
        value = values.get(name.lower(), "")
        if value:
            return value
    return ""


def norm_path(value: str, repo: Path) -> str:
    if not value:
        return ""

    p = value.strip().replace("\\", "/")
    repo_norm = str(repo).replace("\\", "/").rstrip("/")

    if p.lower().startswith(repo_norm.lower()):
        p = p[len(repo_norm):]

    p = p.lstrip("/")
    if p.startswith("./"):
        p = p[2:]

    return p


def repo_path(value: str, repo: Path) -> Path | None:
    rel = norm_path(value, repo)
    if not rel:
        return None
    return repo / Path(rel)


def classify_protection(value: str, repo: Path) -> str:
    p = norm_path(value, repo).lower()

    if p in PROTECTED_EXACT:
        return "PROTECTED-CRITICAL"

    if p.startswith(PROTECTED_PREFIXES):
        return "PROTECTED"

    return "NORMAL"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)

    return digest.hexdigest()


def iter_text_files(repo: Path):
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for name in files:
            path = Path(root) / name
            rel = path.relative_to(repo).as_posix()

            # Do not scan the current forensic output.
            if rel.startswith("reports/D-OBSIDIAN-06.12-R1/"):
                continue

            if path.suffix.lower() in TEXT_EXTENSIONS or name.lower() == ".gitignore":
                yield path


def scan_exact_references(repo: Path, target: str) -> tuple[int, int, list[str]]:
    """
    Returns:
      strong_count, weak_basename_count, evidence list.

    Strong = exact relative path with either slash convention.
    Weak   = basename occurrence without exact path.

    This is intentionally evidence-only.
    """
    rel = norm_path(target, repo)
    if not rel:
        return 0, 0, []

    variants = {
        rel,
        rel.replace("/", "\\"),
    }
    basename = Path(rel).name

    strong: set[str] = set()
    weak: set[str] = set()

    for source in iter_text_files(repo):
        try:
            raw = source.read_bytes()
        except OSError:
            continue

        if b"\x00" in raw[:8192]:
            continue

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                continue

        source_rel = source.relative_to(repo).as_posix()

        if any(v in text for v in variants):
            strong.add(source_rel)
        elif basename and basename in text:
            weak.add(source_rel)

    evidence = [f"STRONG::{p}" for p in sorted(strong)]
    evidence += [f"WEAK-BASENAME::{p}" for p in sorted(weak)]

    return len(strong), len(weak), evidence


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fields = list(rows[0].keys())

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    repo = Path.cwd().resolve()
    source_dir = repo / "reports" / "D-OBSIDIAN-06.9-R1"
    out_dir = repo / "reports" / "D-OBSIDIAN-06.12-R1"
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    decision_file = latest_file(
        source_dir, "D-OBSIDIAN-06.9_R1_DECISION_MATRIX_*.csv"
    )
    canonical_file = latest_file(
        source_dir, "D-OBSIDIAN-06.9_R1_CANONICALIZATION_*.csv"
    )
    duplicate_file = latest_file(
        source_dir, "D-OBSIDIAN-06.9_R1_DUPLICATE_GROUPS_*.csv"
    )

    decision_rows = read_csv(decision_file)
    canonical_rows = read_csv(canonical_file)
    duplicate_rows = read_csv(duplicate_file)

    # Index by hash.
    canonical_by_hash: dict[str, list[dict[str, str]]] = {}
    decision_by_hash: dict[str, list[dict[str, str]]] = {}

    for row in canonical_rows:
        h = get_value(row, "Hash")
        if h:
            canonical_by_hash.setdefault(h, []).append(row)

    for row in decision_rows:
        h = get_value(row, "Hash")
        if h:
            decision_by_hash.setdefault(h, []).append(row)

    review_groups = [
        row for row in duplicate_rows
        if get_value(row, "GroupDecision") == "REVIEW"
    ]

    review_hashes = sorted({
        get_value(row, "Hash")
        for row in review_groups
        if get_value(row, "Hash")
    })

    # Detailed member-level evidence.
    member_rows: list[dict] = []
    group_rows: list[dict] = []

    for group in review_groups:
        h = get_value(group, "Hash")
        group_size = get_value(group, "GroupSize")

        members = canonical_by_hash.get(h, [])
        decisions = decision_by_hash.get(h, [])

        paths = sorted({
            norm_path(get_value(r, "Path"), repo)
            for r in members
            if get_value(r, "Path")
        })

        canonical_paths = sorted({
            norm_path(get_value(r, "CanonicalPath"), repo)
            for r in members
            if get_value(r, "CanonicalPath")
        })

        statuses = sorted({
            get_value(r, "CanonicalStatus")
            for r in members
            if get_value(r, "CanonicalStatus")
        })

        decision_values = sorted({
            get_value(r, "Decision")
            for r in decisions
            if get_value(r, "Decision")
        })

        existing = []
        protected = []
        current_hashes = []
        strong_total = 0
        weak_total = 0
        reference_evidence = []

        for rel in paths:
            fp = repo_path(rel, repo)
            exists = bool(fp and fp.is_file())
            current_hash = ""

            if exists:
                existing.append(rel)
                try:
                    current_hash = sha256_file(fp)
                    current_hashes.append(current_hash)
                except OSError:
                    pass

            prot = classify_protection(rel, repo)
            if prot != "NORMAL":
                protected.append(rel)

            strong, weak, refs = scan_exact_references(repo, rel)
            strong_total += strong
            weak_total += weak

            if refs:
                reference_evidence.append(
                    rel + " => " + " ; ".join(refs[:100])
                )

            member_rows.append({
                "Hash": h,
                "GroupSize": group_size,
                "Path": rel,
                "ExistsNow": exists,
                "SizeBytesNow": fp.stat().st_size if exists and fp else 0,
                "CurrentSHA256": current_hash,
                "Protection": prot,
                "CanonicalStatus": " | ".join(
                    sorted({
                        get_value(r, "CanonicalStatus")
                        for r in members
                        if norm_path(get_value(r, "Path"), repo) == rel
                        and get_value(r, "CanonicalStatus")
                    })
                ),
                "CanonicalPath": " | ".join(canonical_paths),
                "StrongTextReferences": strong,
                "WeakBasenameReferences": weak,
                "ReferenceEvidence": " || ".join(refs),
            })

        canonical_existing = [
            p for p in canonical_paths
            if (repo_path(p, repo) is not None and repo_path(p, repo).is_file())
        ]

        # Conservative structural classification.
        if protected:
            classification = "PRESERVE"
            rationale = "Grupo contem membro em area protegida."
        elif canonical_existing:
            classification = "DUPLICATE-CONFIRMED"
            rationale = (
                "Grupo REVIEW possui canonical fisicamente existente; "
                "nao autorizar remocao."
            )
        elif existing:
            classification = "REVIEW-BLOCKED"
            rationale = (
                "Membros existem, mas nao ha canonical fisicamente confirmada."
            )
        else:
            classification = "REVIEW-BLOCKED"
            rationale = (
                "Nenhum membro existe fisicamente; manter evidencia para "
                "reconciliacao e historico."
            )

        group_rows.append({
            "Hash": h,
            "GroupSize": group_size,
            "GroupDecision": get_value(group, "GroupDecision"),
            "CanonicalRows": len(members),
            "DecisionRows": len(decisions),
            "DecisionValues": " | ".join(decision_values),
            "CanonicalStatus": " | ".join(statuses),
            "Paths": " || ".join(paths),
            "ExistingPaths": " || ".join(existing),
            "ProtectedPaths": " || ".join(protected),
            "CanonicalPaths": " || ".join(canonical_paths),
            "CanonicalExistingPaths": " || ".join(canonical_existing),
            "CurrentSHA256Set": " | ".join(sorted(set(current_hashes))),
            "StrongTextReferences": strong_total,
            "WeakBasenameReferences": weak_total,
            "ReferenceEvidence": " || ".join(reference_evidence),
            "ForensicClassification": classification,
            "ForensicRationale": rationale,
            "DeletionAuthorized": False,
        })

    # ------------------------------------------------------------------
    # CHECKS
    # ------------------------------------------------------------------
    checks: list[dict] = []

    def add_check(name: str, expected: int, actual: int):
        checks.append({
            "Check": name,
            "Expected": expected,
            "Actual": actual,
            "Status": "PASS" if expected == actual else "FAIL",
        })

    review_rows = sum(
        get_value(r, "Decision") == "REVIEW-DUPLICATE"
        for r in decision_rows
    )

    has_canonical = len({
        get_value(r, "Hash")
        for r in duplicate_rows
        if get_value(r, "GroupDecision") == "HAS-CANONICAL"
        and get_value(r, "Hash")
    })

    add_check("DECISION_TOTAL", 910, len(decision_rows))
    add_check("CANONICAL_TOTAL", 910, len(canonical_rows))
    add_check("DUPLICATE_TOTAL", 430, len(duplicate_rows))
    add_check("REVIEW_ROWS", 126, review_rows)
    add_check("REVIEW_GROUPS", 31, len(review_groups))
    add_check("REVIEW_HASHES", 31, len(review_hashes))
    add_check("HAS_CANONICAL_GROUPS", 63, has_canonical)

    group_hash_set = {row["Hash"] for row in group_rows}
    missing_review_groups = sum(
        h not in group_hash_set for h in review_hashes
    )
    add_check("REVIEW_GROUP_COVERAGE", 0, missing_review_groups)

    member_group_hashes = {
        row["Hash"] for row in member_rows
    }
    missing_member_groups = sum(
        h not in member_group_hashes for h in review_hashes
    )
    add_check("REVIEW_MEMBER_COVERAGE", 0, missing_member_groups)

    unauthorized = sum(
        row["DeletionAuthorized"] is not False
        for row in group_rows
    )
    add_check("NO_DELETION_AUTHORIZATION", 0, unauthorized)

    for critical in sorted(PROTECTED_EXACT):
        add_check(
            f"CRITICAL_EXISTS::{critical}",
            1,
            int((repo / Path(critical)).is_file()),
        )

    for tree in (
        "data",
        "vault",
        "archive",
        "tests/intelligence",
        "tests/integration",
    ):
        add_check(
            f"PROTECTED_TREE::{tree}",
            1,
            int((repo / Path(tree)).is_dir()),
        )

    # ------------------------------------------------------------------
    # OUTPUT
    # ------------------------------------------------------------------
    groups_out = out_dir / (
        f"D-OBSIDIAN-06.12_R1_REVIEW_GROUPS_{timestamp}.csv"
    )
    members_out = out_dir / (
        f"D-OBSIDIAN-06.12_R1_REVIEW_MEMBERS_{timestamp}.csv"
    )
    checks_out = out_dir / (
        f"D-OBSIDIAN-06.12_R1_CHECKS_{timestamp}.csv"
    )
    summary_out = out_dir / (
        f"D-OBSIDIAN-06.12_R1_SUMMARY_{timestamp}.txt"
    )

    write_csv(groups_out, group_rows)
    write_csv(members_out, member_rows)
    write_csv(checks_out, checks)

    failures = [c for c in checks if c["Status"] == "FAIL"]
    gate = not failures

    classifications = Counter(
        row["ForensicClassification"]
        for row in group_rows
    )

    summary: list[str] = []
    summary.append("D-OBSIDIAN-06.12 R1 - REVIEW GROUP FORENSIC TRIAGE")
    summary.append("")
    summary.append("READ-ONLY / NON-DESTRUCTIVE")
    summary.append("")
    summary.append("INPUT")
    summary.append(f"Decision rows: {len(decision_rows)}")
    summary.append(f"Canonical rows: {len(canonical_rows)}")
    summary.append(f"Duplicate groups: {len(duplicate_rows)}")
    summary.append("")
    summary.append("TARGET")
    summary.append(f"REVIEW rows: {review_rows}")
    summary.append(f"REVIEW groups: {len(review_groups)}")
    summary.append(f"REVIEW hashes: {len(review_hashes)}")
    summary.append("")
    summary.append("FORENSIC CLASSIFICATION")
    for key in sorted(classifications):
        summary.append(f"  [{classifications[key]}] {key}")
    summary.append("")
    summary.append("CHECKS")
    for c in checks:
        summary.append(
            f"[{c['Status']}] {c['Check']} "
            f"Expected={c['Expected']} Actual={c['Actual']}"
        )
    summary.append("")
    summary.append("SAFETY")
    summary.append("No files removed.")
    summary.append("No files moved.")
    summary.append("No files renamed.")
    summary.append("No source contents modified.")
    summary.append("No git add.")
    summary.append("No git commit.")
    summary.append("No git restore.")
    summary.append("No git reset.")
    summary.append("No git clean.")
    summary.append("DeletionAuthorized=False for every REVIEW group.")
    summary.append("")
    summary.append(
        "FORENSIC TRIAGE GATE: " + ("PASS" if gate else "FAIL")
    )

    summary_out.write_text("\n".join(summary) + "\n", encoding="utf-8")

    # Console
    print()
    print("=" * 88)
    print("D-OBSIDIAN-06.12 R1 - RESULTADO")
    print("=" * 88)
    print()
    print("TARGET")
    print(f"  REVIEW rows   : {review_rows}")
    print(f"  REVIEW groups : {len(review_groups)}")
    print(f"  REVIEW hashes : {len(review_hashes)}")
    print()
    print("FORENSIC CLASSIFICATION")
    for key in sorted(classifications):
        print(f"  [{classifications[key]}] {key}")
    print()

    for c in checks:
        print(
            f"[{c['Status']}] {c['Check']} "
            f"Expected={c['Expected']} Actual={c['Actual']}"
        )

    print()
    print("=" * 88)
    print("FORENSIC TRIAGE GATE: " + ("PASS" if gate else "FAIL"))
    print("=" * 88)
    print()
    print("READ-ONLY: nenhuma acao destrutiva foi executada.")
    print(f"Reports: {out_dir}")

    return 0 if gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
