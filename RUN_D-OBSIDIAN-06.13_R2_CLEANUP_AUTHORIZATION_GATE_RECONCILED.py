#!/usr/bin/env python3
"""
D-OBSIDIAN-06.13 R2 — CLEANUP AUTHORIZATION GATE / SOURCE RECONCILIATION

READ-ONLY / NON-DESTRUCTIVE.

R1 exposed two source-discovery defects:
  - the historical 06.09 D-candidate CSV was not found by the filename glob;
  - the 06.11 forensic member CSV was not found by the filename heuristic.

R2 resolves this by discovering CSVs by HEADER SCHEMA, not fragile filenames.

No deletion, move, rename, source modification, or Git operation.
"""

from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def header(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return set(next(csv.reader(f), []))


def discover_by_headers(
    directory: Path,
    required: set[str],
    forbidden: set[str] | None = None,
) -> list[Path]:
    forbidden = forbidden or set()
    result = []
    for path in directory.glob("*.csv"):
        try:
            h = header(path)
        except Exception:
            continue
        if required.issubset(h) and not (forbidden & h):
            result.append(path)
    return sorted(result, key=lambda p: p.stat().st_mtime, reverse=True)


def discover_decision_file(directory: Path) -> Path:
    candidates = discover_by_headers(
        directory,
        {"Hash", "GroupSize", "Class", "Type", "Policy", "Decision", "Path"},
    )
    if not candidates:
        raise FileNotFoundError("Decision Matrix nao encontrada por schema.")
    return candidates[0]


def discover_duplicate_file(directory: Path) -> Path:
    candidates = discover_by_headers(
        directory,
        {
            "Hash", "GroupSize", "Protected", "Keep",
            "KeepArchive", "ReviewDuplicate", "RemoveCandidate",
            "GroupDecision",
        },
    )
    if not candidates:
        raise FileNotFoundError("Duplicate Groups nao encontrado por schema.")
    return candidates[0]


def discover_candidate_file(directory: Path) -> Path:
    candidates = discover_by_headers(
        directory,
        {"Class", "Type", "Path", "SizeBytes", "References",
         "DuplicateRows", "Policy", "Decision", "Reason"},
    )
    if not candidates:
        raise FileNotFoundError("D Candidates nao encontrado por schema.")
    return candidates[0]


def discover_611_members(directory: Path) -> Path | None:
    # 06.11 member evidence schema can vary slightly between runs.
    # Prefer files whose header contains Hash + path-like forensic fields.
    all_csv = []
    for path in directory.glob("*.csv"):
        try:
            h = header(path)
        except Exception:
            continue
        if "Hash" in h and (
            "Path" in h or "MemberPath" in h or "FilePath" in h
        ):
            all_csv.append(path)

    if not all_csv:
        return None

    # Exclude checks/summary-like files when their schemas expose Status only.
    preferred = [
        p for p in all_csv
        if "CHECK" not in p.name.upper()
        and "SUMMARY" not in p.name.upper()
        and "GROUP" not in p.name.upper()
    ]
    return max(preferred or all_csv, key=lambda p: p.stat().st_mtime)


def latest_by_headers(directory: Path, required: set[str], pattern: str = "*.csv") -> Path:
    candidates = []
    for path in directory.glob(pattern):
        try:
            if required.issubset(header(path)):
                candidates.append(path)
        except Exception:
            pass
    if not candidates:
        raise FileNotFoundError(
            f"Fonte por schema nao encontrada em {directory}: {sorted(required)}"
        )
    return max(candidates, key=lambda p: p.stat().st_mtime)


def main() -> int:
    repo = Path.cwd().resolve()

    d609 = repo / "reports" / "D-OBSIDIAN-06.9-R1"
    d611 = repo / "reports" / "D-OBSIDIAN-06.11-R1"
    d612 = repo / "reports" / "D-OBSIDIAN-06.12-R4"
    out = repo / "reports" / "D-OBSIDIAN-06.13-R2"
    out.mkdir(parents=True, exist_ok=True)

    decision_file = discover_decision_file(d609)
    duplicate_file = discover_duplicate_file(d609)
    candidate_file = discover_candidate_file(d609)
    member_file = discover_611_members(d611)

    matrix612 = latest_by_headers(
        d612,
        {
            "Hash", "GroupSize", "GroupDecision",
            "AuthoritativeReviewRows", "R1ForensicMemberRows",
            "ForensicDecision", "HumanApprovalRequired",
            "DeletionAuthorized",
        },
    )

    decisions = csv_rows(decision_file)
    duplicate_groups = csv_rows(duplicate_file)
    candidates = csv_rows(candidate_file)
    matrix_rows = csv_rows(matrix612)
    member_rows = csv_rows(member_file) if member_file else []

    group_counts = Counter(
        (r.get("GroupDecision") or "").strip() for r in duplicate_groups
    )

    remove_candidates = [
        r for r in candidates
        if (r.get("Class") or "").strip() == "REMOVE-CANDIDATE"
    ]

    # If 06.11 member evidence is available, verify it contains the expected
    # 66 forensic members. Do not infer missing evidence as zero.
    member_status = "FOUND" if member_file else "NOT_FOUND"

    manifest = []

    for g in duplicate_groups:
        gd = (g.get("GroupDecision") or "").strip()

        if gd == "HAS-CANONICAL":
            final = "KEEP"
            rationale = "HAS-CANONICAL; sem autorizacao de limpeza."
        elif gd == "PROTECTED-GROUP":
            final = "PROTECTED"
            rationale = "PROTECTED-GROUP; sem autorizacao de limpeza."
        elif gd == "REVIEW":
            final = "REVIEW-BLOCKED"
            rationale = "06.12 fechado como REVIEW-BLOCKED."
        else:
            final = "KEEP"
            rationale = f"GroupDecision={gd!r}; preservado por seguranca."

        manifest.append({
            "Scope": "DUPLICATE_GROUP",
            "Hash": (g.get("Hash") or "").strip(),
            "FinalClassification": final,
            "DeletionAuthorized": "False",
            "HumanApprovalRequired": "True",
            "Rationale": rationale,
        })

    for c in remove_candidates:
        manifest.append({
            "Scope": "HISTORICAL_D_CANDIDATE",
            "Hash": "",
            "FinalClassification": "PRESERVE",
            "DeletionAuthorized": "False",
            "HumanApprovalRequired": "True",
            "Rationale": "Historico de candidato; nao autorizar exclusao.",
        })

    for r in matrix_rows:
        manifest.append({
            "Scope": "06.12_REVIEW_GROUP",
            "Hash": (r.get("Hash") or "").strip(),
            "FinalClassification": (
                "REVIEW-BLOCKED"
                if (r.get("ForensicDecision") or "").strip() == "REVIEW-BLOCKED"
                else "PRESERVE"
            ),
            "DeletionAuthorized": "False",
            "HumanApprovalRequired": "True",
            "Rationale": r.get("Reason", ""),
        })

    checks = []

    def check(name: str, expected: int, actual: int) -> None:
        checks.append({
            "Check": name,
            "Expected": expected,
            "Actual": actual,
            "Status": "PASS" if expected == actual else "FAIL",
        })

    check("D609_DECISION_ROWS", 910, len(decisions))
    check("D609_DUPLICATE_GROUPS", 430, len(duplicate_groups))
    check("D609_HAS_CANONICAL_GROUPS", 63, group_counts["HAS-CANONICAL"])
    check("D609_PROTECTED_GROUPS", 336, group_counts["PROTECTED-GROUP"])
    check("D609_REVIEW_GROUPS", 31, group_counts["REVIEW"])
    check("D609_REMOVE_CANDIDATES", 2, len(remove_candidates))
    check("D612_REVIEW_GROUPS", 31, len(matrix_rows))
    check(
        "D612_REVIEW_BLOCKED",
        31,
        sum(
            (r.get("ForensicDecision") or "").strip() == "REVIEW-BLOCKED"
            for r in matrix_rows
        ),
    )
    check(
        "D611_FORENSIC_MEMBERS",
        66,
        len(member_rows),
    )
    check(
        "REMOVE_CANDIDATES_PRESERVED",
        2,
        sum(
            r["Scope"] == "HISTORICAL_D_CANDIDATE"
            and r["FinalClassification"] == "PRESERVE"
            for r in manifest
        ),
    )
    check(
        "NO_DELETION_AUTHORIZATION",
        0,
        sum(r["DeletionAuthorized"] != "False" for r in manifest),
    )
    check(
        "NO_APPROVAL_BYPASS",
        0,
        sum(r["HumanApprovalRequired"] != "True" for r in manifest),
    )
    check(
        "DUPLICATE_GROUP_MANIFEST_COVERAGE",
        430,
        sum(r["Scope"] == "DUPLICATE_GROUP" for r in manifest),
    )
    check(
        "D612_REVIEW_MANIFEST_COVERAGE",
        31,
        sum(r["Scope"] == "06.12_REVIEW_GROUP" for r in manifest),
    )

    gate = all(c["Status"] == "PASS" for c in checks)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    manifest_file = out / f"D-OBSIDIAN-06.13_R2_MANIFEST_{stamp}.csv"
    checks_file = out / f"D-OBSIDIAN-06.13_R2_CHECKS_{stamp}.csv"
    summary_file = out / f"D-OBSIDIAN-06.13_R2_SUMMARY_{stamp}.txt"

    write_csv(manifest_file, manifest)
    write_csv(checks_file, checks)

    summary = [
        "D-OBSIDIAN-06.13 R2 - CLEANUP AUTHORIZATION GATE",
        "",
        "READ-ONLY / NON-DESTRUCTIVE",
        "",
        "SOURCE DISCOVERY",
        f"  Decision Matrix : {decision_file.name}",
        f"  Duplicate Groups: {duplicate_file.name}",
        f"  D Candidates    : {candidate_file.name}",
        f"  06.11 Members   : {member_file.name if member_file else 'NOT FOUND'}",
        f"  06.12 Matrix    : {matrix612.name}",
        "",
        "NOTE",
        "  R2 discovers sources by CSV schema rather than fragile filenames.",
        "  Missing 06.11 evidence is a FAIL, never silently treated as zero.",
        "",
        "CHECKS",
    ]
    for c in checks:
        summary.append(
            f"[{c['Status']}] {c['Check']} "
            f"Expected={c['Expected']} Actual={c['Actual']}"
        )

    summary += [
        "",
        "POLICY",
        "  DeletionAuthorized=False for every row.",
        "  HumanApprovalRequired=True for every row.",
        "",
        "SAFETY",
        "  No deletion.",
        "  No move.",
        "  No rename.",
        "  No source modification.",
        "  No Git operation.",
        "",
        "CLEANUP AUTHORIZATION GATE: " + ("PASS" if gate else "FAIL"),
    ]
    summary_file.write_text("\n".join(summary) + "\n", encoding="utf-8")

    print("=" * 88)
    print("D-OBSIDIAN-06.13 R2 - CLEANUP AUTHORIZATION GATE")
    print("=" * 88)
    print("READ-ONLY / NON-DESTRUCTIVE")
    print()
    print("SOURCE DISCOVERY")
    print(f"  Decision Matrix : {decision_file.name}")
    print(f"  Duplicate Groups: {duplicate_file.name}")
    print(f"  D Candidates    : {candidate_file.name}")
    print(f"  06.11 Members   : {member_file.name if member_file else 'NOT FOUND'}")
    print(f"  06.12 Matrix    : {matrix612.name}")
    print()
    print("POPULATIONS")
    print(f"  Decision rows                 : {len(decisions)}")
    print(f"  Duplicate groups              : {len(duplicate_groups)}")
    print(f"  HAS-CANONICAL groups          : {group_counts['HAS-CANONICAL']}")
    print(f"  PROTECTED-GROUP groups        : {group_counts['PROTECTED-GROUP']}")
    print(f"  REVIEW groups                 : {group_counts['REVIEW']}")
    print(f"  Historical REMOVE-CANDIDATES  : {len(remove_candidates)}")
    print(f"  06.11 forensic members        : {len(member_rows)}")
    print(f"  06.12 REVIEW groups           : {len(matrix_rows)}")
    print()
    for c in checks:
        print(
            f"[{c['Status']}] {c['Check']} "
            f"Expected={c['Expected']} Actual={c['Actual']}"
        )
    print()
    print("=" * 88)
    print("CLEANUP AUTHORIZATION GATE: " + ("PASS" if gate else "FAIL"))
    print("=" * 88)
    print()
    print("READ-ONLY: nenhuma acao destrutiva foi executada.")
    print(f"Reports: {out}")

    return 0 if gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
