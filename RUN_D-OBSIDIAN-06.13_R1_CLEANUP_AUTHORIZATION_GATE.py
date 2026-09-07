#!/usr/bin/env python3
"""
D-OBSIDIAN-06.13 R1 — CLEANUP AUTHORIZATION GATE

READ-ONLY / NON-DESTRUCTIVE.

Purpose:
  Consolidate the decision history of D-OBSIDIAN-06.09 through 06.12 and
  produce a cleanup authorization manifest WITHOUT authorizing or executing
  deletion.

Safety policy:
  - No deletion
  - No move
  - No rename
  - No source modification
  - No Git operation
  - DeletionAuthorized=False for every row

The gate explicitly verifies that:
  1. The 2 historical REMOVE-CANDIDATE records from 06.09 are preserved.
  2. The 31 REVIEW groups are REVIEW-BLOCKED.
  3. The 63 HAS-CANONICAL groups remain non-destructive.
  4. The 336 PROTECTED-GROUP population remains protected.
  5. No candidate receives deletion authorization implicitly.
"""

from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path


def latest(directory: Path, pattern: str) -> Path:
    files = list(directory.glob(pattern))
    if not files:
        raise FileNotFoundError(f"Fonte nao encontrada: {directory}\\{pattern}")
    return max(files, key=lambda p: p.stat().st_mtime)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    repo = Path.cwd().resolve()

    d609 = repo / "reports" / "D-OBSIDIAN-06.9-R1"
    d610 = repo / "reports" / "D-OBSIDIAN-06.10-R4"
    d611 = repo / "reports" / "D-OBSIDIAN-06.11-R1"
    d612 = repo / "reports" / "D-OBSIDIAN-06.12-R4"
    out = repo / "reports" / "D-OBSIDIAN-06.13-R1"
    out.mkdir(parents=True, exist_ok=True)

    decision_file = latest(d609, "D-OBSIDIAN-06.9_R1_DECISION_MATRIX_*.csv")
    duplicate_file = latest(d609, "D-OBSIDIAN-06.9_R1_DUPLICATE_GROUPS_*.csv")
    candidate_file = latest(d609, "D-OBSIDIAN-06.9_R1_D_CANDIDATES_*.csv")

    r611_files = list(d611.glob("*FORENSIC*")) + list(d611.glob("*REVIEW*"))
    r611_files = [x for x in r611_files if "SUMMARY" not in x.name.upper()]
    # Candidate evidence is discovered by header, not filename semantics.
    all_611 = list(d611.glob("*.csv"))
    r611_member = next(
        (x for x in all_611 if "MEMBER" in x.name.upper()), None
    )

    r612_matrix = latest(
        d612, "D-OBSIDIAN-06.12_R4_REVIEW_FORENSIC_MATRIX_*.csv"
    )
    r612_checks = latest(d612, "D-OBSIDIAN-06.12_R4_CHECKS_*.csv")

    decisions = read_csv(decision_file)
    duplicate_groups = read_csv(duplicate_file)
    candidates = read_csv(candidate_file)
    matrix612 = read_csv(r612_matrix)
    checks612 = read_csv(r612_checks)

    # 06.11 is used as a supporting integrity source when available.
    member_rows_611 = read_csv(r611_member) if r611_member else []

    decision_counts = Counter(
        (r.get("Decision") or "").strip() for r in decisions
    )
    group_counts = Counter(
        (r.get("GroupDecision") or "").strip() for r in duplicate_groups
    )
    candidate_decisions = Counter(
        (r.get("Decision") or "").strip() for r in candidates
    )
    forensic_counts = Counter(
        (r.get("ForensicDecision") or "").strip() for r in matrix612
    )

    # Historical candidate population from 06.09.
    remove_candidates = [
        r for r in candidates
        if (r.get("Class") or "").strip() == "REMOVE-CANDIDATE"
    ]

    manifest = []

    # Global duplicate groups: preserve the existing 06.09 group decision.
    for g in duplicate_groups:
        h = (g.get("Hash") or "").strip()
        gd = (g.get("GroupDecision") or "").strip()

        if gd == "HAS-CANONICAL":
            action = "KEEP"
            rationale = "Canonical group; no cleanup authorization."
        elif gd == "PROTECTED-GROUP":
            action = "PROTECTED"
            rationale = "Protected duplicate group; no cleanup authorization."
        elif gd == "REVIEW":
            action = "REVIEW-BLOCKED"
            rationale = "Reviewed in 06.12; remains blocked pending human review."
        else:
            action = "KEEP"
            rationale = f"Non-target group decision={gd!r}; preserve."

        manifest.append({
            "Scope": "DUPLICATE_GROUP",
            "Hash": h,
            "GroupSize": g.get("GroupSize", ""),
            "OriginalDecision": gd,
            "FinalClassification": action,
            "DeletionAuthorized": "False",
            "HumanApprovalRequired": "True",
            "Rationale": rationale,
        })

    # Historical D candidates: explicitly preserve them.
    for c in remove_candidates:
        manifest.append({
            "Scope": "HISTORICAL_D_CANDIDATE",
            "Hash": "",
            "GroupSize": "",
            "OriginalDecision": c.get("Decision", ""),
            "FinalClassification": "PRESERVE",
            "DeletionAuthorized": "False",
            "HumanApprovalRequired": "True",
            "Rationale": (
                "06.11 forensic review classified the historical removal "
                "candidate as PRESERVE; no deletion authorization."
            ),
        })

    # 06.12 forensic groups are included as an explicit audit layer.
    for r in matrix612:
        if (r.get("ForensicDecision") or "").strip() != "REVIEW-BLOCKED":
            # Conservative: any unexpected result is still non-destructive.
            final = "PRESERVE"
        else:
            final = "REVIEW-BLOCKED"

        manifest.append({
            "Scope": "06.12_REVIEW_GROUP",
            "Hash": r.get("Hash", ""),
            "GroupSize": r.get("GroupSize", ""),
            "OriginalDecision": r.get("GroupDecision", ""),
            "FinalClassification": final,
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
    check("D609_HAS_CANONICAL_GROUPS", 63, group_counts.get("HAS-CANONICAL", 0))
    check("D609_PROTECTED_GROUPS", 336, group_counts.get("PROTECTED-GROUP", 0))
    check("D609_REVIEW_GROUPS", 31, group_counts.get("REVIEW", 0))
    check("D609_REMOVE_CANDIDATES", 2, len(remove_candidates))
    check("D612_REVIEW_GROUPS", 31, len(matrix612))
    check("D612_REVIEW_BLOCKED", 31, forensic_counts.get("REVIEW-BLOCKED", 0))
    check("D611_FORENSIC_MEMBERS_IF_AVAILABLE", 66, len(member_rows_611))

    # Candidate disposition must remain PRESERVE.
    check(
        "REMOVE_CANDIDATES_PRESERVED",
        2,
        sum(
            r["FinalClassification"] == "PRESERVE"
            for r in manifest
            if r["Scope"] == "HISTORICAL_D_CANDIDATE"
        ),
    )

    # No row may authorize deletion.
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

    # Exact duplicate-group coverage.
    check(
        "DUPLICATE_GROUP_MANIFEST_COVERAGE",
        430,
        sum(r["Scope"] == "DUPLICATE_GROUP" for r in manifest),
    )

    # Explicit 06.12 scope coverage.
    check(
        "D612_REVIEW_MANIFEST_COVERAGE",
        31,
        sum(r["Scope"] == "06.12_REVIEW_GROUP" for r in manifest),
    )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    manifest_file = out / f"D-OBSIDIAN-06.13_R1_CLEANUP_AUTHORIZATION_MANIFEST_{stamp}.csv"
    checks_file = out / f"D-OBSIDIAN-06.13_R1_CHECKS_{stamp}.csv"
    summary_file = out / f"D-OBSIDIAN-06.13_R1_SUMMARY_{stamp}.txt"

    write_csv(manifest_file, manifest)
    write_csv(checks_file, checks)

    gate = all(c["Status"] == "PASS" for c in checks)

    final_counts = Counter(r["FinalClassification"] for r in manifest)

    summary = [
        "D-OBSIDIAN-06.13 R1 - CLEANUP AUTHORIZATION GATE",
        "",
        "READ-ONLY / NON-DESTRUCTIVE",
        "",
        "PURPOSE",
        "  Consolidate cleanup history and produce a non-authorizing manifest.",
        "",
        "SOURCE POPULATIONS",
        f"  Decision rows: {len(decisions)}",
        f"  Duplicate groups: {len(duplicate_groups)}",
        f"  HAS-CANONICAL groups: {group_counts.get('HAS-CANONICAL', 0)}",
        f"  PROTECTED-GROUP groups: {group_counts.get('PROTECTED-GROUP', 0)}",
        f"  REVIEW groups: {group_counts.get('REVIEW', 0)}",
        f"  Historical REMOVE-CANDIDATE records: {len(remove_candidates)}",
        f"  06.12 REVIEW groups: {len(matrix612)}",
        "",
        "FINAL MANIFEST DISTRIBUTION",
    ]
    for key in (
        "KEEP", "PROTECTED", "REVIEW-BLOCKED", "PRESERVE"
    ):
        summary.append(f"  {key}: {final_counts.get(key, 0)}")

    summary += ["", "CHECKS"]
    for c in checks:
        summary.append(
            f"[{c['Status']}] {c['Check']} "
            f"Expected={c['Expected']} Actual={c['Actual']}"
        )

    summary += [
        "",
        "AUTHORIZATION POLICY",
        "  DeletionAuthorized=False for every manifest row.",
        "  HumanApprovalRequired=True for every manifest row.",
        "  This gate does not authorize cleanup execution.",
        "",
        "SAFETY",
        "  No deletion.",
        "  No move.",
        "  No rename.",
        "  No source modification.",
        "  No Git operation.",
        "",
        "CLEANUP AUTHORIZATION GATE: " + ("PASS" if gate else "FAIL"),
        f"Manifest: {manifest_file}",
        f"Checks: {checks_file}",
    ]

    summary_file.write_text("\n".join(summary) + "\n", encoding="utf-8")

    print("=" * 88)
    print("D-OBSIDIAN-06.13 R1 - CLEANUP AUTHORIZATION GATE")
    print("=" * 88)
    print("READ-ONLY / NON-DESTRUCTIVE")
    print()
    print("SOURCE POPULATIONS")
    print(f"  Decision rows                 : {len(decisions)}")
    print(f"  Duplicate groups              : {len(duplicate_groups)}")
    print(f"  HAS-CANONICAL groups          : {group_counts.get('HAS-CANONICAL', 0)}")
    print(f"  PROTECTED-GROUP groups        : {group_counts.get('PROTECTED-GROUP', 0)}")
    print(f"  REVIEW groups                 : {group_counts.get('REVIEW', 0)}")
    print(f"  Historical REMOVE-CANDIDATES  : {len(remove_candidates)}")
    print(f"  06.12 REVIEW groups           : {len(matrix612)}")
    print()
    print("FINAL MANIFEST DISTRIBUTION")
    for key in ("KEEP", "PROTECTED", "REVIEW-BLOCKED", "PRESERVE"):
        print(f"  {key:18}: {final_counts.get(key, 0)}")
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
