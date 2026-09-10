#!/usr/bin/env python3
"""
D-OBSIDIAN-06.12 R3 — REVIEW DECISION CONSOLIDATION / ROW TRIANGULATION

READ-ONLY / NON-DESTRUCTIVE.

Fix for 06.12 R2:
- The R1 REVIEW_MEMBERS CSV contains 66 forensic members.
- The authoritative 06.09 decision matrix contains 126 REVIEW-DUPLICATE
  decision rows.
- These are different populations and must not be conflated.

R3 therefore:
1. Keeps the 31 R1 REVIEW groups as the forensic group population.
2. Uses the latest D-OBSIDIAN-06.09 decision matrix as the authoritative
   source for REVIEW-DUPLICATE row counts.
3. Triangulates those 126 rows by Hash against the 31 R1 groups.
4. Preserves the 66 R1 forensic member rows as evidence, but does not use
   them as the REVIEW_ROWS denominator.
5. Keeps HumanApprovalRequired=True and DeletionAuthorized=False.
6. Performs no deletion, move, rename, Git operation, or source modification.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

EXPECTED_REVIEW_GROUPS = 31
EXPECTED_REVIEW_ROWS = 126
EXPECTED_R1_FORENSIC_MEMBERS = 66


def latest_file(directory: Path, pattern: str) -> Path:
    files = list(directory.glob(pattern))
    if not files:
        raise FileNotFoundError(f"Fonte nao encontrada: {directory}\\{pattern}")
    return max(files, key=lambda p: p.stat().st_mtime)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def safe_int(value: str | None) -> int:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return 0


def main() -> int:
    repo = Path.cwd().resolve()
    r1_dir = repo / "reports" / "D-OBSIDIAN-06.12-R1"
    d609_dir = repo / "reports" / "D-OBSIDIAN-06.9-R1"
    out_dir = repo / "reports" / "D-OBSIDIAN-06.12-R2"
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    groups_file = latest_file(
        r1_dir, "D-OBSIDIAN-06.12_R1_REVIEW_GROUPS_*.csv"
    )
    members_file = latest_file(
        r1_dir, "D-OBSIDIAN-06.12_R1_REVIEW_MEMBERS_*.csv"
    )
    checks_file = latest_file(
        r1_dir, "D-OBSIDIAN-06.12_R1_CHECKS_*.csv"
    )

    # Authoritative REVIEW-DUPLICATE population from 06.09.
    decision_file = latest_file(
        d609_dir, "D-OBSIDIAN-06.9_R1_DECISION_MATRIX_*.csv"
    )

    groups = read_csv(groups_file)
    members = read_csv(members_file)
    r1_checks = read_csv(checks_file)
    decision_rows = read_csv(decision_file)

    review_rows = [
        row for row in decision_rows
        if (row.get("Decision") or "").strip() == "REVIEW-DUPLICATE"
    ]

    review_by_hash: dict[str, list[dict[str, str]]] = {}
    for row in review_rows:
        h = (row.get("Hash") or "").strip()
        if h:
            review_by_hash.setdefault(h, []).append(row)

    members_by_hash: dict[str, list[dict[str, str]]] = {}
    for row in members:
        h = (row.get("Hash") or "").strip()
        if h:
            members_by_hash.setdefault(h, []).append(row)

    group_hashes = {
        (row.get("Hash") or "").strip()
        for row in groups
        if (row.get("Hash") or "").strip()
    }

    review_hashes = set(review_by_hash)
    missing_group_hashes = sorted(review_hashes - group_hashes)
    unexpected_group_hashes = sorted(group_hashes - review_hashes)

    decisions: list[dict] = []

    for group in groups:
        h = (group.get("Hash") or "").strip()
        gm = members_by_hash.get(h, [])
        authoritative_rows = review_by_hash.get(h, [])

        protected_paths = [
            x for x in (group.get("ProtectedPaths") or "").split(" || ")
            if x
        ]
        existing_paths = [
            x for x in (group.get("ExistingPaths") or "").split(" || ")
            if x
        ]
        canonical_existing_paths = [
            x for x in (group.get("CanonicalExistingPaths") or "").split(" || ")
            if x
        ]

        strong_refs = safe_int(group.get("StrongTextReferences"))
        weak_refs = safe_int(group.get("WeakBasenameReferences"))

        if protected_paths:
            forensic_decision = "PRESERVE"
            reason = "Grupo contem membro protegido; fora do escopo de limpeza."
            risk = "HIGH"
        elif canonical_existing_paths:
            forensic_decision = "DUPLICATE-CONFIRMED"
            reason = (
                "Canonical fisicamente existente foi confirmada; "
                "duplicidade permanece sem autorizacao de exclusao."
            )
            risk = "MEDIUM"
        elif existing_paths and strong_refs > 0:
            forensic_decision = "REVIEW-BLOCKED"
            reason = (
                "Membros existentes possuem referencias textuais fortes; "
                "nao ha canonical fisicamente confirmada."
            )
            risk = "HIGH"
        elif existing_paths:
            forensic_decision = "REVIEW-BLOCKED"
            reason = (
                "Membros existem, mas nao ha canonical fisicamente confirmada; "
                "ausencia de referencia nao autoriza exclusao."
            )
            risk = "HIGH"
        else:
            forensic_decision = "REVIEW-BLOCKED"
            reason = (
                "Nenhum membro existe fisicamente na varredura atual; "
                "manter registro para reconciliacao/historico."
            )
            risk = "MEDIUM"

        decisions.append({
            "Hash": h,
            "GroupSize": group.get("GroupSize", ""),
            "OriginalGroupDecision": group.get("GroupDecision", ""),
            "AuthoritativeDecisionRows": len(authoritative_rows),
            "R1ForensicMemberRows": len(gm),
            "R1ReportedDecisionRows": safe_int(group.get("DecisionRows")),
            "CanonicalRows": group.get("CanonicalRows", ""),
            "CanonicalStatus": group.get("CanonicalStatus", ""),
            "Paths": group.get("Paths", ""),
            "ExistingPaths": group.get("ExistingPaths", ""),
            "ProtectedPaths": group.get("ProtectedPaths", ""),
            "CanonicalPaths": group.get("CanonicalPaths", ""),
            "CanonicalExistingPaths": group.get("CanonicalExistingPaths", ""),
            "StrongTextReferences": strong_refs,
            "WeakBasenameReferences": weak_refs,
            "ForensicDecision": forensic_decision,
            "Risk": risk,
            "Reason": reason,
            "HumanApprovalRequired": True,
            "DeletionAuthorized": False,
        })

    checks: list[dict] = []

    def check(name: str, expected: int, actual: int) -> None:
        checks.append({
            "Check": name,
            "Expected": expected,
            "Actual": actual,
            "Status": "PASS" if expected == actual else "FAIL",
        })

    check("REVIEW_GROUPS", EXPECTED_REVIEW_GROUPS, len(groups))
    check("AUTHORITATIVE_REVIEW_ROWS", EXPECTED_REVIEW_ROWS, len(review_rows))
    check("R1_FORENSIC_MEMBERS", EXPECTED_R1_FORENSIC_MEMBERS, len(members))

    # Triangulate every authoritative REVIEW-DUPLICATE row by Hash.
    check(
        "REVIEW_HASH_GROUP_COVERAGE",
        len(review_hashes),
        len(review_hashes & group_hashes),
    )
    check("REVIEW_HASHES_WITHOUT_GROUP", 0, len(missing_group_hashes))
    check("GROUP_HASHES_WITHOUT_REVIEW_ROWS", 0, len(unexpected_group_hashes))

    authoritative_total_from_groups = sum(
        len(review_by_hash.get((g.get("Hash") or "").strip(), []))
        for g in groups
    )
    check(
        "GROUP_RECONCILIATION_REVIEW_ROWS",
        EXPECTED_REVIEW_ROWS,
        authoritative_total_from_groups,
    )

    decision_hashes = {row["Hash"] for row in decisions if row["Hash"]}
    check("DECISION_HASH_COVERAGE", len(group_hashes), len(decision_hashes))

    approval_violations = sum(
        row["HumanApprovalRequired"] is not True for row in decisions
    )
    deletion_violations = sum(
        row["DeletionAuthorized"] is not False for row in decisions
    )
    check("NO_APPROVAL_BYPASS", 0, approval_violations)
    check("NO_DELETION_AUTHORIZATION", 0, deletion_violations)

    preserve = sum(x["ForensicDecision"] == "PRESERVE" for x in decisions)
    duplicate_confirmed = sum(
        x["ForensicDecision"] == "DUPLICATE-CONFIRMED" for x in decisions
    )
    blocked = sum(x["ForensicDecision"] == "REVIEW-BLOCKED" for x in decisions)

    matrix_out = out_dir / (
        f"D-OBSIDIAN-06.12_R2_REVIEW_DECISION_MATRIX_{timestamp}.csv"
    )
    checks_out = out_dir / (
        f"D-OBSIDIAN-06.12_R2_CHECKS_{timestamp}.csv"
    )
    reconciliation_out = out_dir / (
        f"D-OBSIDIAN-06.12_R2_ROW_RECONCILIATION_{timestamp}.csv"
    )
    summary_out = out_dir / (
        f"D-OBSIDIAN-06.12_R2_SUMMARY_{timestamp}.txt"
    )

    write_csv(matrix_out, decisions)
    write_csv(checks_out, checks)

    reconciliation = []
    for h in sorted(group_hashes):
        r1_group = next(g for g in groups if (g.get("Hash") or "").strip() == h)
        reconciliation.append({
            "Hash": h,
            "AuthoritativeReviewRows": len(review_by_hash.get(h, [])),
            "R1ReportedDecisionRows": safe_int(r1_group.get("DecisionRows")),
            "R1ForensicMemberRows": len(members_by_hash.get(h, [])),
            "DeltaAuthoritativeVsR1Reported": (
                len(review_by_hash.get(h, []))
                - safe_int(r1_group.get("DecisionRows"))
            ),
            "DeltaAuthoritativeVsForensicMembers": (
                len(review_by_hash.get(h, []))
                - len(members_by_hash.get(h, []))
            ),
        })
    write_csv(reconciliation_out, reconciliation)

    failures = [x for x in checks if x["Status"] == "FAIL"]
    gate = not failures

    summary = [
        "D-OBSIDIAN-06.12 R2 - REVIEW DECISION CONSOLIDATION",
        "",
        "READ-ONLY / NON-DESTRUCTIVE",
        "",
        "SOURCE POPULATIONS",
        f"  R1 REVIEW groups: {len(groups)}",
        f"  R1 forensic members: {len(members)}",
        f"  06.09 authoritative REVIEW-DUPLICATE rows: {len(review_rows)}",
        "",
        "FORENSIC DECISION DISTRIBUTION",
        f"  PRESERVE: {preserve}",
        f"  DUPLICATE-CONFIRMED: {duplicate_confirmed}",
        f"  REVIEW-BLOCKED: {blocked}",
        "",
        "POLICY",
        "  HumanApprovalRequired=True for every group.",
        "  DeletionAuthorized=False for every group.",
        "",
        "CHECKS",
    ]
    for c in checks:
        summary.append(
            f"[{c['Status']}] {c['Check']} "
            f"Expected={c['Expected']} Actual={c['Actual']}"
        )

    summary.extend([
        "",
        "NOTE",
        "  REVIEW_ROWS is sourced from the authoritative 06.09 decision matrix.",
        "  R1 forensic member rows are evidence and are not the REVIEW_ROWS denominator.",
        "",
        "SAFETY",
        "No files removed.",
        "No files moved.",
        "No files renamed.",
        "No source contents modified.",
        "No git commands executed.",
        "",
        "FORENSIC DECISION GATE: " + ("PASS" if gate else "FAIL"),
    ])

    summary_out.write_text("\n".join(summary) + "\n", encoding="utf-8")

    print()
    print("=" * 88)
    print("D-OBSIDIAN-06.12 R2 - RESULTADO")
    print("=" * 88)
    print()
    print("SOURCE POPULATIONS")
    print(f"  R1 REVIEW groups                 : {len(groups)}")
    print(f"  R1 forensic members              : {len(members)}")
    print(f"  06.09 REVIEW-DUPLICATE rows      : {len(review_rows)}")
    print()
    print("FORENSIC DECISION DISTRIBUTION")
    print(f"  PRESERVE             : {preserve}")
    print(f"  DUPLICATE-CONFIRMED  : {duplicate_confirmed}")
    print(f"  REVIEW-BLOCKED       : {blocked}")
    print()
    for c in checks:
        print(
            f"[{c['Status']}] {c['Check']} "
            f"Expected={c['Expected']} Actual={c['Actual']}"
        )
    print()
    print("=" * 88)
    print("FORENSIC DECISION GATE: " + ("PASS" if gate else "FAIL"))
    print("=" * 88)
    print()
    print("READ-ONLY: nenhuma acao destrutiva foi executada.")
    print(f"Reports: {out_dir}")

    return 0 if gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
