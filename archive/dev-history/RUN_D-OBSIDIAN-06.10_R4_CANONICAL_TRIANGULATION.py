#!/usr/bin/env python3
"""
D-OBSIDIAN-06.10 R4 — CANONICAL TRIANGULATION AUDIT

READ-ONLY / NON-DESTRUCTIVE.

Triangulates the 63 HAS-CANONICAL groups using:
  1. Canonicalization
  2. DuplicateGroups
  3. DecisionMatrix

No files are removed, moved, renamed or modified.
No Git commands are executed.

R4 deliberately does NOT assume a specific CanonicalStatus value.
The authoritative canonical-group population is:
    DuplicateGroups.GroupDecision == "HAS-CANONICAL"

Outputs are written only to:
    reports/D-OBSIDIAN-06.10-R4/
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from datetime import datetime
from pathlib import Path


EXPECTED = {
    "decision_total": 910,
    "canonical_total": 910,
    "duplicate_groups_total": 430,
    "remove_candidate": 2,
    "review_duplicate": 126,
    "has_canonical_groups": 63,
}


def latest_file(directory: Path, pattern: str) -> Path:
    files = list(directory.glob(pattern))
    if not files:
        raise FileNotFoundError(f"Fonte nao encontrada: {pattern}")
    return max(files, key=lambda p: p.stat().st_mtime)


def read_csv(path: Path) -> list[dict[str, str]]:
    # utf-8-sig handles UTF-8 files with or without BOM safely.
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def get_value(row: dict[str, str], *names: str) -> str:
    lowered = {str(k).lower(): (v or "").strip() for k, v in row.items()}
    for name in names:
        value = lowered.get(name.lower(), "")
        if value:
            return value
    return ""


def normalize_path(value: str, repo: Path) -> str:
    if not value:
        return ""

    p = value.strip().replace("\\", "/")
    repo_norm = str(repo).replace("\\", "/").rstrip("/")

    if p.lower().startswith(repo_norm.lower()):
        p = p[len(repo_norm):]

    return p.lstrip("./").lstrip("/")


def resolve_file(path_value: str, repo: Path) -> Path | None:
    rel = normalize_path(path_value, repo)
    if not rel:
        return None

    candidate = repo / Path(rel)
    if candidate.is_file():
        return candidate
    return None


def protection(path_value: str, repo: Path) -> str:
    p = normalize_path(path_value, repo).lower()

    exact = {
        "src/iip/intelligence/metric_identity.py",
        "src/iip/intelligence/metric_persistence.py",
        "src/iip/intelligence/metric_persistence_adapter.py",
    }

    prefixes = (
        "data/",
        "vault/",
        "archive/",
        "tests/intelligence/",
        "tests/integration/",
    )

    if p in exact:
        return "PROTECTED-CRITICAL"

    if p.startswith(prefixes):
        return "PROTECTED"

    return "NORMAL"


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def add_check(checks: list[dict], name: str, expected: int, actual: int) -> None:
    checks.append(
        {
            "Check": name,
            "Expected": expected,
            "Actual": actual,
            "Status": "PASS" if expected == actual else "FAIL",
        }
    )


def main() -> int:
    repo = Path.cwd().resolve()
    source_dir = repo / "reports" / "D-OBSIDIAN-06.9-R1"
    out_dir = repo / "reports" / "D-OBSIDIAN-06.10-R4"
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
    candidate_file = latest_file(
        source_dir, "D-OBSIDIAN-06.9_R1_D_CANDIDATES_*.csv"
    )

    decision_rows = read_csv(decision_file)
    canonical_rows = read_csv(canonical_file)
    duplicate_rows = read_csv(duplicate_file)
    candidate_rows = read_csv(candidate_file)

    print()
    print("=" * 80)
    print("D-OBSIDIAN-06.10 R4 - CANONICAL TRIANGULATION AUDIT")
    print("=" * 80)
    print(f"Repository : {repo}")
    print(f"Output     : {out_dir}")
    print()
    print("READ-ONLY / NON-DESTRUCTIVE")
    print()
    print("INPUT")
    print(f"  Decision       : {len(decision_rows)}")
    print(f"  Canonical      : {len(canonical_rows)}")
    print(f"  Duplicate      : {len(duplicate_rows)}")
    print(f"  Candidates     : {len(candidate_rows)}")

    # ------------------------------------------------------------------
    # DISTINCT CanonicalStatus
    # ------------------------------------------------------------------
    status_counter = Counter(
        get_value(row, "CanonicalStatus")
        for row in canonical_rows
        if get_value(row, "CanonicalStatus")
    )

    print()
    print("DISTINCT CanonicalStatus VALUES")
    for value in sorted(status_counter):
        print(f"  [{status_counter[value]}] {value}")

    # ------------------------------------------------------------------
    # DISTINCT GroupDecision
    # ------------------------------------------------------------------
    group_decision_counter = Counter(
        get_value(row, "GroupDecision")
        for row in duplicate_rows
        if get_value(row, "GroupDecision")
    )

    print()
    print("DISTINCT GroupDecision VALUES")
    for value in sorted(group_decision_counter):
        print(f"  [{group_decision_counter[value]}] {value}")

    # ------------------------------------------------------------------
    # AUTHORITATIVE CANONICAL GROUPS
    # ------------------------------------------------------------------
    canonical_groups = [
        row
        for row in duplicate_rows
        if get_value(row, "GroupDecision") == "HAS-CANONICAL"
    ]

    canonical_hashes = sorted(
        {
            get_value(row, "Hash")
            for row in canonical_groups
            if get_value(row, "Hash")
        }
    )

    print()
    print("GROUP CLASSIFICATION")
    print(f"  HAS-CANONICAL rows   : {len(canonical_groups)}")
    print(f"  HAS-CANONICAL hashes : {len(canonical_hashes)}")

    # ------------------------------------------------------------------
    # Index source rows by hash
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # TRIANGULATION
    # ------------------------------------------------------------------
    triangulation: list[dict] = []

    for group in canonical_groups:
        h = get_value(group, "Hash")

        matching_canonical = canonical_by_hash.get(h, [])
        matching_decision = decision_by_hash.get(h, [])

        statuses = sorted(
            {
                get_value(row, "CanonicalStatus")
                for row in matching_canonical
                if get_value(row, "CanonicalStatus")
            }
        )

        canonical_paths = sorted(
            {
                normalize_path(get_value(row, "CanonicalPath"), repo)
                for row in matching_canonical
                if normalize_path(get_value(row, "CanonicalPath"), repo)
            }
        )

        paths = sorted(
            {
                normalize_path(get_value(row, "Path"), repo)
                for row in matching_canonical
                if normalize_path(get_value(row, "Path"), repo)
            }
        )

        existing_paths = [
            p for p in paths if resolve_file(p, repo) is not None
        ]

        protected_paths = [
            p for p in paths if protection(p, repo) != "NORMAL"
        ]

        status_text = " | ".join(statuses)
        canonical_path_text = " | ".join(canonical_paths)

        status_has_canonical = bool(
            re.search("CANONICAL", status_text, flags=re.IGNORECASE)
        )
        canonical_path_present = bool(canonical_paths)

        evidence_consistent = (
            bool(matching_canonical)
            and (status_has_canonical or canonical_path_present)
            and bool(matching_decision)
        )

        triangulation.append(
            {
                "Hash": h,
                "GroupSize": get_value(group, "GroupSize"),
                "GroupDecision": get_value(group, "GroupDecision"),
                "CanonicalRows": len(matching_canonical),
                "CanonicalStatus": status_text,
                "CanonicalPath": canonical_path_text,
                "Paths": " || ".join(paths),
                "ExistingPaths": " || ".join(existing_paths),
                "ProtectedPaths": " || ".join(protected_paths),
                "DecisionRows": len(matching_decision),
                "CanonicalStatusHasWord": status_has_canonical,
                "CanonicalPathPresent": canonical_path_present,
                "EvidenceConsistent": evidence_consistent,
            }
        )

    # ------------------------------------------------------------------
    # CHECKS
    # ------------------------------------------------------------------
    checks: list[dict] = []

    remove_count = sum(
        get_value(row, "Decision") == "REMOVE-CANDIDATE"
        for row in decision_rows
    )

    review_count = sum(
        get_value(row, "Decision") == "REVIEW-DUPLICATE"
        for row in decision_rows
    )

    evidence_failures = sum(
        row["EvidenceConsistent"] is False for row in triangulation
    )

    triangulated_hashes = {
        row["Hash"] for row in triangulation if row["Hash"]
    }

    coverage_failures = sum(
        h not in triangulated_hashes for h in canonical_hashes
    )

    invalid_group_decisions = sum(
        row["GroupDecision"] != "HAS-CANONICAL"
        for row in triangulation
    )

    add_check(checks, "DECISION_TOTAL", EXPECTED["decision_total"], len(decision_rows))
    add_check(
        checks,
        "CANONICALIZATION_TOTAL",
        EXPECTED["canonical_total"],
        len(canonical_rows),
    )
    add_check(
        checks,
        "DUPLICATE_GROUPS_TOTAL",
        EXPECTED["duplicate_groups_total"],
        len(duplicate_rows),
    )
    add_check(
        checks,
        "REMOVE_CANDIDATE",
        EXPECTED["remove_candidate"],
        remove_count,
    )
    add_check(
        checks,
        "REVIEW_DUPLICATE",
        EXPECTED["review_duplicate"],
        review_count,
    )
    add_check(
        checks,
        "HAS_CANONICAL_GROUPS",
        EXPECTED["has_canonical_groups"],
        len(canonical_hashes),
    )
    add_check(
        checks,
        "CANONICAL_TRIANGULATION_EVIDENCE",
        0,
        evidence_failures,
    )
    add_check(
        checks,
        "CANONICAL_GROUP_COVERAGE",
        0,
        coverage_failures,
    )
    add_check(
        checks,
        "TRIANGULATION_GROUP_DECISION_GUARD",
        0,
        invalid_group_decisions,
    )

    # ------------------------------------------------------------------
    # PROTECTION
    # ------------------------------------------------------------------
    critical_files = (
        "src/iip/intelligence/metric_identity.py",
        "src/iip/intelligence/metric_persistence.py",
        "src/iip/intelligence/metric_persistence_adapter.py",
    )

    for critical in critical_files:
        actual = int(resolve_file(critical, repo) is not None)
        add_check(checks, f"CRITICAL_EXISTS::{critical}", 1, actual)

    protected_trees = (
        "data",
        "vault",
        "archive",
        "tests/intelligence",
        "tests/integration",
    )

    for tree in protected_trees:
        actual = int((repo / tree).is_dir())
        add_check(checks, f"PROTECTED_TREE::{tree}", 1, actual)

    # ------------------------------------------------------------------
    # OUTPUTS
    # ------------------------------------------------------------------
    status_rows = [
        {"Value": value, "Count": count}
        for value, count in sorted(status_counter.items())
    ]

    group_decision_rows = [
        {"Value": value, "Count": count}
        for value, count in sorted(group_decision_counter.items())
    ]

    status_out = out_dir / f"D-OBSIDIAN-06.10_R4_STATUS_VALUES_{timestamp}.csv"
    group_decision_out = (
        out_dir / f"D-OBSIDIAN-06.10_R4_GROUP_DECISION_VALUES_{timestamp}.csv"
    )
    triangulation_out = (
        out_dir / f"D-OBSIDIAN-06.10_R4_CANONICAL_TRIANGULATION_{timestamp}.csv"
    )
    checks_out = out_dir / f"D-OBSIDIAN-06.10_R4_COMPLETENESS_{timestamp}.csv"
    summary_out = out_dir / f"D-OBSIDIAN-06.10_R4_SUMMARY_{timestamp}.txt"

    write_csv(status_out, status_rows)
    write_csv(group_decision_out, group_decision_rows)
    write_csv(triangulation_out, triangulation)
    write_csv(checks_out, checks)

    failures = [c for c in checks if c["Status"] == "FAIL"]
    gate = len(failures) == 0

    summary: list[str] = []
    summary.append("D-OBSIDIAN-06.10 R4 - CANONICAL TRIANGULATION AUDIT")
    summary.append("")
    summary.append("READ-ONLY / NON-DESTRUCTIVE")
    summary.append("")
    summary.append("INPUT")
    summary.append(f"Decision rows: {len(decision_rows)}")
    summary.append(f"Canonical rows: {len(canonical_rows)}")
    summary.append(f"Duplicate groups: {len(duplicate_rows)}")
    summary.append(f"Candidates: {len(candidate_rows)}")
    summary.append("")
    summary.append("OBSERVED CanonicalStatus VALUES")
    for row in status_rows:
        summary.append(f"  [{row['Count']}] {row['Value']}")
    summary.append("")
    summary.append("OBSERVED GroupDecision VALUES")
    for row in group_decision_rows:
        summary.append(f"  [{row['Count']}] {row['Value']}")
    summary.append("")
    summary.append("CANONICAL POPULATION")
    summary.append("Expected HAS-CANONICAL groups: 63")
    summary.append(f"Detected HAS-CANONICAL groups: {len(canonical_hashes)}")
    summary.append("")
    summary.append("TRIANGULATION")
    summary.append(f"Triangulated groups: {len(triangulation)}")
    summary.append(f"Evidence failures: {evidence_failures}")
    summary.append(f"Canonical groups without triangulation: {coverage_failures}")
    summary.append("")
    summary.append("CHECKS")
    for check in checks:
        summary.append(
            f"[{check['Status']}] {check['Check']} "
            f"Expected={check['Expected']} Actual={check['Actual']}"
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
    summary.append("")
    summary.append(
        "FORENSIC COMPLETENESS GATE: "
        + ("PASS" if gate else "FAIL")
    )

    summary_out.write_text("\n".join(summary) + "\n", encoding="utf-8")

    # ------------------------------------------------------------------
    # CONSOLE
    # ------------------------------------------------------------------
    print()
    print("=" * 80)
    print("D-OBSIDIAN-06.10 R4 - RESULTADO")
    print("=" * 80)
    print()
    print("OBSERVED CanonicalStatus VALUES")
    for row in status_rows:
        print(f"  [{row['Count']}] {row['Value']}")

    print()
    print("OBSERVED GroupDecision VALUES")
    for row in group_decision_rows:
        print(f"  [{row['Count']}] {row['Value']}")

    print()
    print("CANONICAL POPULATION")
    print("  Expected HAS-CANONICAL groups : 63")
    print(f"  Detected HAS-CANONICAL groups : {len(canonical_hashes)}")
    print()

    for check in checks:
        print(
            f"[{check['Status']}] {check['Check']} "
            f"Expected={check['Expected']} Actual={check['Actual']}"
        )

    print()
    print("=" * 80)
    print(
        "FORENSIC COMPLETENESS GATE: "
        + ("PASS" if gate else "FAIL")
    )
    print("=" * 80)
    print()
    print("D-OBSIDIAN-06.10 R4 concluido em modo READ-ONLY.")
    print()
    print(f"Reports: {out_dir}")

    return 0 if gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
