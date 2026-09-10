#!/usr/bin/env python3
"""
D-OBSIDIAN-06.12 R4 — REVIEW FORENSIC CONSOLIDATION

READ-ONLY / NON-DESTRUCTIVE.

Scope:
  Only the 31 groups classified as GroupDecision=REVIEW in D-OBSIDIAN-06.10
  / D-OBSIDIAN-06.12 R1 are consolidated here.

Authoritative populations:
  - 31 REVIEW groups
  - 66 R1 forensic member rows
  - 64 D-OBSIDIAN-06.09 REVIEW-DUPLICATE rows belonging to those 31 hashes

The remaining 62 REVIEW-DUPLICATE rows belong to:
  - 53 HAS-CANONICAL hashes
  - 4 PROTECTED-GROUP hashes

They are explicitly OUT OF SCOPE for this forensic consolidation.

No deletion, move, rename, source modification, or Git operation.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
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

    d69 = repo / "reports" / "D-OBSIDIAN-06.9-R1"
    d610 = repo / "reports" / "D-OBSIDIAN-06.10-R4"
    d612 = repo / "reports" / "D-OBSIDIAN-06.12-R1"
    d612r3 = repo / "reports" / "D-OBSIDIAN-06.12-R3"
    out = repo / "reports" / "D-OBSIDIAN-06.12-R4"
    out.mkdir(parents=True, exist_ok=True)

    # Authoritative group universe from 06.10 R4.
    # Prefer the 06.12 R1 groups because they are the exact forensic scope,
    # while 06.10 R4 provides the original GroupDecision semantics.
    groups_file = latest(d612, "*REVIEW_GROUPS_*.csv")
    members_file = latest(d612, "*REVIEW_MEMBERS_*.csv")
    checks_file = latest(d612, "*CHECKS_*.csv")

    decision_file = latest(d69, "D-OBSIDIAN-06.9_R1_DECISION_MATRIX_*.csv")
    triage_file = latest(d612r3, "*GLOBAL_TRIANGULATION_*.csv")

    groups = read_csv(groups_file)
    members = read_csv(members_file)
    r1_checks = read_csv(checks_file)
    decisions = read_csv(decision_file)
    triangulation = read_csv(triage_file)

    group_hashes = {
        (r.get("Hash") or "").strip()
        for r in groups
        if (r.get("Hash") or "").strip()
    }

    review_authoritative = [
        r for r in decisions
        if (r.get("Decision") or "").strip() == "REVIEW-DUPLICATE"
        and (r.get("Hash") or "").strip() in group_hashes
    ]

    triage_by_hash = {
        (r.get("Hash") or "").strip(): r
        for r in triangulation
        if (r.get("Hash") or "").strip()
    }

    member_by_hash: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in members:
        h = (r.get("Hash") or "").strip()
        if h:
            member_by_hash[h].append(r)

    decision_by_hash: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in review_authoritative:
        decision_by_hash[(r.get("Hash") or "").strip()].append(r)

    consolidated = []

    for g in groups:
        h = (g.get("Hash") or "").strip()
        auth_rows = decision_by_hash.get(h, [])
        mem_rows = member_by_hash.get(h, [])
        triage = triage_by_hash.get(h, {})

        # Conservative forensic classification:
        # the group remains REVIEW-BLOCKED unless the R1 evidence itself
        # establishes a safe non-destructive conclusion.
        protected = bool((g.get("ProtectedPaths") or "").strip())
        canonical_existing = bool((g.get("CanonicalExistingPaths") or "").strip())
        existing = bool((g.get("ExistingPaths") or "").strip())

        if protected:
            forensic = "PRESERVE"
            reason = "Grupo contem caminho protegido."
        elif canonical_existing:
            forensic = "DUPLICATE-CONFIRMED"
            reason = "Canonical fisicamente existente confirmada."
        else:
            forensic = "REVIEW-BLOCKED"
            if existing:
                reason = "Membros existem, mas nao ha canonical fisicamente confirmada."
            else:
                reason = "Grupo requer revisao; ausencia fisica nao autoriza exclusao."

        consolidated.append({
            "Hash": h,
            "GroupSize": g.get("GroupSize", ""),
            "GroupDecision": g.get("GroupDecision", ""),
            "AuthoritativeReviewRows": str(len(auth_rows)),
            "R1ForensicMemberRows": str(len(mem_rows)),
            "R1DecisionRows": g.get("DecisionRows", ""),
            "TriangulationClassification": triage.get("Classification", ""),
            "ForensicDecision": forensic,
            "Reason": reason,
            "HumanApprovalRequired": "True",
            "DeletionAuthorized": "False",
            "Scope": "06.12_REVIEW_GROUPS_ONLY",
        })

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    matrix_out = out / f"D-OBSIDIAN-06.12_R4_REVIEW_FORENSIC_MATRIX_{stamp}.csv"
    checks_out = out / f"D-OBSIDIAN-06.12_R4_CHECKS_{stamp}.csv"
    summary_out = out / f"D-OBSIDIAN-06.12_R4_SUMMARY_{stamp}.txt"

    checks = []

    def check(name: str, expected: int, actual: int) -> None:
        checks.append({
            "Check": name,
            "Expected": expected,
            "Actual": actual,
            "Status": "PASS" if expected == actual else "FAIL",
        })

    check("REVIEW_GROUPS", 31, len(groups))
    check("R1_FORENSIC_MEMBERS", 66, len(members))
    check("REVIEW_HASHES", 31, len(group_hashes))
    check("SCOPED_REVIEW_ROWS", 64, len(review_authoritative))
    check(
        "SCOPED_REVIEW_HASH_COVERAGE",
        31,
        sum(h in decision_by_hash for h in group_hashes),
    )
    check(
        "SCOPED_MEMBER_HASH_COVERAGE",
        31,
        sum(h in member_by_hash for h in group_hashes),
    )
    check(
        "SCOPED_TRIANGULATION_COVERAGE",
        31,
        sum(h in triage_by_hash for h in group_hashes),
    )
    check(
        "GROUP_DECISION_REVIEW_ONLY",
        0,
        sum((g.get("GroupDecision") or "").strip() != "REVIEW" for g in groups),
    )
    check(
        "NO_APPROVAL_BYPASS",
        0,
        sum(x["HumanApprovalRequired"] != "True" for x in consolidated),
    )
    check(
        "NO_DELETION_AUTHORIZATION",
        0,
        sum(x["DeletionAuthorized"] != "False" for x in consolidated),
    )

    # Every scoped authoritative row must be represented by one of the 31 hashes.
    scoped_from_groups = sum(
        len(decision_by_hash.get(h, [])) for h in group_hashes
    )
    check("SCOPED_ROW_RECONCILIATION", 64, scoped_from_groups)

    counts = Counter(x["ForensicDecision"] for x in consolidated)

    gate = all(x["Status"] == "PASS" for x in checks)

    write_csv(matrix_out, consolidated)
    write_csv(checks_out, checks)

    summary = [
        "D-OBSIDIAN-06.12 R4 - REVIEW FORENSIC CONSOLIDATION",
        "",
        "READ-ONLY / NON-DESTRUCTIVE",
        "",
        "SCOPE",
        "  Only GroupDecision=REVIEW groups are consolidated.",
        "  HAS-CANONICAL and PROTECTED-GROUP are explicitly out of scope.",
        "",
        "POPULATIONS",
        f"  REVIEW groups: {len(groups)}",
        f"  R1 forensic members: {len(members)}",
        f"  Scoped authoritative REVIEW-DUPLICATE rows: {len(review_authoritative)}",
        "",
        "FORENSIC DECISIONS",
    ]
    for key in ("PRESERVE", "DUPLICATE-CONFIRMED", "REVIEW-BLOCKED"):
        summary.append(f"  {key}: {counts.get(key, 0)}")

    summary += ["", "CHECKS"]
    for c in checks:
        summary.append(
            f"[{c['Status']}] {c['Check']} "
            f"Expected={c['Expected']} Actual={c['Actual']}"
        )

    summary += [
        "",
        "POLICY",
        "  HumanApprovalRequired=True for all groups.",
        "  DeletionAuthorized=False for all groups.",
        "",
        "SAFETY",
        "  No deletion.",
        "  No move.",
        "  No rename.",
        "  No source modification.",
        "  No Git operation.",
        "",
        "FORENSIC CONSOLIDATION GATE: " + ("PASS" if gate else "FAIL"),
        f"Matrix: {matrix_out}",
        f"Checks: {checks_out}",
    ]

    summary_out.write_text("\n".join(summary) + "\n", encoding="utf-8")

    print("=" * 88)
    print("D-OBSIDIAN-06.12 R4 - REVIEW FORENSIC CONSOLIDATION")
    print("=" * 88)
    print("READ-ONLY / NON-DESTRUCTIVE")
    print()
    print("SCOPE")
    print("  Only GroupDecision=REVIEW groups.")
    print("  HAS-CANONICAL / PROTECTED-GROUP explicitly out of scope.")
    print()
    print("POPULATIONS")
    print(f"  REVIEW groups                 : {len(groups)}")
    print(f"  R1 forensic members           : {len(members)}")
    print(f"  Scoped authoritative rows     : {len(review_authoritative)}")
    print()
    print("FORENSIC DECISIONS")
    print(f"  PRESERVE             : {counts.get('PRESERVE', 0)}")
    print(f"  DUPLICATE-CONFIRMED  : {counts.get('DUPLICATE-CONFIRMED', 0)}")
    print(f"  REVIEW-BLOCKED       : {counts.get('REVIEW-BLOCKED', 0)}")
    print()
    for c in checks:
        print(
            f"[{c['Status']}] {c['Check']} "
            f"Expected={c['Expected']} Actual={c['Actual']}"
        )
    print()
    print("=" * 88)
    print("FORENSIC CONSOLIDATION GATE: " + ("PASS" if gate else "FAIL"))
    print("=" * 88)
    print()
    print("READ-ONLY: nenhuma acao destrutiva foi executada.")
    print(f"Reports: {out}")

    return 0 if gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
