#!/usr/bin/env python3
"""
D-OBSIDIAN-06.13 R4 — CLEANUP AUTHORIZATION GATE / FINAL SOURCE CONTRACT

READ-ONLY / NON-DESTRUCTIVE.

Corrected source contract after D-OBSIDIAN-06.13 R3 inventory:

06.09 D_CANDIDATES is a 35-row classification inventory:
  - 30 REMOVE-CANDIDATE
  - 3 KEEP-REFERENCED
  - 2 REVIEW-DUPLICATE

The "2 historical REMOVE-CANDIDATES" investigated by 06.11 are NOT the
30 D_CANDIDATES rows. They are the 2 rows from the 06.10/06.11 forensic
candidate artifact. Therefore 06.13 must use:
  - 06.09 D_CANDIDATES for the global D-class inventory;
  - 06.11 REMOVE_CANDIDATES for the 2 specifically forensically reviewed
    candidates;
  - 06.12 R4 REVIEW_FORENSIC_MATRIX for the 31 REVIEW groups.

There is no separate 66-row 06.11 member CSV in the actual R3 inventory.
The 66 figure is the sum of DecisionRows across the 31 REVIEW_GROUP rows:
  28*2 + 2*3 + 1*4 = 66.
It is therefore an aggregate member count, not a separate source file.

This script:
  - validates those contracts;
  - produces a non-authorizing cleanup manifest;
  - never deletes, moves, renames, modifies source files, or runs Git.
"""

from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def header(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return set(next(csv.reader(f), []))


def latest_schema(directory: Path, required: set[str]) -> Path:
    candidates = []
    for path in directory.glob("*.csv"):
        try:
            if required.issubset(header(path)):
                candidates.append(path)
        except Exception:
            continue
    if not candidates:
        raise FileNotFoundError(
            f"Nenhum CSV com schema {sorted(required)} em {directory}"
        )
    return max(candidates, key=lambda p: p.stat().st_mtime)


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    repo = Path.cwd().resolve()

    d609 = repo / "reports" / "D-OBSIDIAN-06.9-R1"
    d611 = repo / "reports" / "D-OBSIDIAN-06.11-R1"
    d612 = repo / "reports" / "D-OBSIDIAN-06.12-R4"
    out = repo / "reports" / "D-OBSIDIAN-06.13-R4"
    out.mkdir(parents=True, exist_ok=True)

    decision_file = latest_schema(
        d609, {"Hash", "GroupSize", "Class", "Type", "Policy", "Decision", "Path"}
    )
    duplicate_file = latest_schema(
        d609,
        {
            "Hash", "GroupSize", "Protected", "Keep",
            "KeepArchive", "ReviewDuplicate", "RemoveCandidate",
            "GroupDecision",
        },
    )
    d_candidates_file = latest_schema(
        d609,
        {
            "Class", "Type", "Path", "SizeBytes", "References",
            "DuplicateRows", "Policy", "Decision", "Reason",
        },
    )
    forensic_candidates_file = latest_schema(
        d611,
        {
            "Hash", "Path", "ExistsNow", "SizeBytesNow", "CurrentSHA256",
            "Protection", "SourceReferences", "CurrentTextReferences",
            "ReferenceEvidence", "DuplicateRows", "CanonicalPath",
            "CanonicalExistsNow", "Policy", "SourceReason",
            "ForensicClassification", "ForensicRationale",
            "DeletionAuthorized",
        },
    )
    review_matrix_file = latest_schema(
        d612,
        {
            "Hash", "GroupSize", "GroupDecision",
            "AuthoritativeReviewRows", "R1ForensicMemberRows",
            "ForensicDecision", "HumanApprovalRequired",
            "DeletionAuthorized",
        },
    )

    decisions = read_csv(decision_file)
    duplicate_groups = read_csv(duplicate_file)
    d_candidates = read_csv(d_candidates_file)
    forensic_candidates = read_csv(forensic_candidates_file)
    review_matrix = read_csv(review_matrix_file)

    decision_counts = Counter(
        (r.get("Decision") or "").strip() for r in decisions
    )
    group_counts = Counter(
        (r.get("GroupDecision") or "").strip() for r in duplicate_groups
    )
    d_candidate_counts = Counter(
        (r.get("Decision") or "").strip() for r in d_candidates
    )
    forensic_counts = Counter(
        (r.get("ForensicClassification") or "").strip()
        for r in forensic_candidates
    )

    d_remove = [
        r for r in d_candidates
        if (r.get("Decision") or "").strip() == "REMOVE-CANDIDATE"
    ]
    d_review = [
        r for r in d_candidates
        if (r.get("Decision") or "").strip() == "REVIEW-DUPLICATE"
    ]
    d_keep = [
        r for r in d_candidates
        if (r.get("Decision") or "").strip() == "KEEP-REFERENCED"
    ]

    manifest: list[dict[str, str]] = []

    # Global duplicate-group contract.
    for g in duplicate_groups:
        gd = (g.get("GroupDecision") or "").strip()
        if gd == "HAS-CANONICAL":
            final = "KEEP"
            rationale = "HAS-CANONICAL; nenhuma limpeza autorizada."
        elif gd == "PROTECTED-GROUP":
            final = "PROTECTED"
            rationale = "PROTECTED-GROUP; nenhuma limpeza autorizada."
        elif gd == "REVIEW":
            final = "REVIEW-BLOCKED"
            rationale = "06.12 R4 consolidou o grupo como REVIEW-BLOCKED."
        else:
            final = "KEEP"
            rationale = f"GroupDecision inesperado={gd!r}; preservado."

        manifest.append({
            "Scope": "DUPLICATE_GROUP",
            "Hash": (g.get("Hash") or "").strip(),
            "FinalClassification": final,
            "DeletionAuthorized": "False",
            "HumanApprovalRequired": "True",
            "Rationale": rationale,
        })

    # 06.09 D inventory: 30 historical candidates are not automatically
    # deletable. They are kept as inventory until separately forensically
    # approved. The two REVIEW-DUPLICATE D rows are represented as review.
    for c in d_candidates:
        decision = (c.get("Decision") or "").strip()
        if decision == "KEEP-REFERENCED":
            final = "KEEP"
        elif decision == "REVIEW-DUPLICATE":
            final = "REVIEW-BLOCKED"
        elif decision == "REMOVE-CANDIDATE":
            final = "PRESERVE-PENDING-AUTHORIZATION"
        else:
            final = "PRESERVE"

        manifest.append({
            "Scope": "D609_D_CLASSIFICATION",
            "Hash": "",
            "FinalClassification": final,
            "DeletionAuthorized": "False",
            "HumanApprovalRequired": "True",
            "Rationale": (
                "D-class inventory; no deletion authorization exists in 06.13."
            ),
        })

    # The 06.11 forensic artifact is authoritative for the two specifically
    # investigated candidates.
    for r in forensic_candidates:
        manifest.append({
            "Scope": "D611_FORENSIC_CANDIDATE",
            "Hash": (r.get("Hash") or "").strip(),
            "FinalClassification": (
                r.get("ForensicClassification") or "REVIEW-BLOCKED"
            ).strip(),
            "DeletionAuthorized": (
                r.get("DeletionAuthorized") or "False"
            ).strip(),
            "HumanApprovalRequired": "True",
            "Rationale": r.get("ForensicRationale", ""),
        })

    # 06.12 forensic review layer.
    for r in review_matrix:
        manifest.append({
            "Scope": "D612_REVIEW_GROUP",
            "Hash": (r.get("Hash") or "").strip(),
            "FinalClassification": (
                r.get("ForensicDecision") or "REVIEW-BLOCKED"
            ).strip(),
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

    check("D609_D_CLASSIFICATION_ROWS", 35, len(d_candidates))
    check("D609_D_REMOVE_CANDIDATES", 30, len(d_remove))
    check("D609_D_REVIEW_DUPLICATE", 2, len(d_review))
    check("D609_D_KEEP_REFERENCED", 3, len(d_keep))

    check("D611_FORENSIC_CANDIDATES", 2, len(forensic_candidates))
    check(
        "D611_FORENSIC_PRESERVE",
        2,
        sum(
            (r.get("ForensicClassification") or "").strip() == "PRESERVE"
            for r in forensic_candidates
        ),
    )
    check(
        "D611_FORENSIC_DELETION_AUTHORIZED",
        0,
        sum(
            (r.get("DeletionAuthorized") or "").strip().lower() == "true"
            for r in forensic_candidates
        ),
    )

    check("D612_REVIEW_GROUPS", 31, len(review_matrix))
    check(
        "D612_REVIEW_BLOCKED",
        31,
        sum(
            (r.get("ForensicDecision") or "").strip() == "REVIEW-BLOCKED"
            for r in review_matrix
        ),
    )

    # The 66-member figure is validated as an aggregate from the 31 group rows.
    member_aggregate = sum(
        int((r.get("R1ForensicMemberRows") or "0").strip() or "0")
        for r in review_matrix
    )
    check("D612_FORENSIC_MEMBER_AGGREGATE", 66, member_aggregate)

    check(
        "NO_DELETION_AUTHORIZATION_MANIFEST",
        0,
        sum(r["DeletionAuthorized"].lower() == "true" for r in manifest),
    )
    check(
        "NO_APPROVAL_BYPASS_MANIFEST",
        0,
        sum(r["HumanApprovalRequired"].lower() != "true" for r in manifest),
    )

    check(
        "DUPLICATE_GROUP_MANIFEST_COVERAGE",
        430,
        sum(r["Scope"] == "DUPLICATE_GROUP" for r in manifest),
    )
    check(
        "D609_D_MANIFEST_COVERAGE",
        35,
        sum(r["Scope"] == "D609_D_CLASSIFICATION" for r in manifest),
    )
    check(
        "D611_FORENSIC_MANIFEST_COVERAGE",
        2,
        sum(r["Scope"] == "D611_FORENSIC_CANDIDATE" for r in manifest),
    )
    check(
        "D612_REVIEW_MANIFEST_COVERAGE",
        31,
        sum(r["Scope"] == "D612_REVIEW_GROUP" for r in manifest),
    )

    gate = all(c["Status"] == "PASS" for c in checks)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    manifest_file = out / f"D-OBSIDIAN-06.13_R4_MANIFEST_{stamp}.csv"
    checks_file = out / f"D-OBSIDIAN-06.13_R4_CHECKS_{stamp}.csv"
    summary_file = out / f"D-OBSIDIAN-06.13_R4_SUMMARY_{stamp}.txt"

    write_csv(manifest_file, manifest)
    write_csv(checks_file, checks)

    final_counts = Counter(r["FinalClassification"] for r in manifest)

    summary = [
        "D-OBSIDIAN-06.13 R4 - CLEANUP AUTHORIZATION GATE",
        "",
        "READ-ONLY / NON-DESTRUCTIVE",
        "",
        "SOURCE CONTRACT",
        f"  D609 D-classification rows: {len(d_candidates)}",
        f"  D609 REMOVE-CANDIDATE rows: {len(d_remove)}",
        f"  D609 REVIEW-DUPLICATE D rows: {len(d_review)}",
        f"  D609 KEEP-REFERENCED rows: {len(d_keep)}",
        f"  D611 forensic candidate rows: {len(forensic_candidates)}",
        f"  D612 REVIEW groups: {len(review_matrix)}",
        f"  D612 forensic member aggregate: {member_aggregate}",
        "",
        "FINAL CLASSIFICATION DISTRIBUTION",
    ]
    for key, value in sorted(final_counts.items()):
        summary.append(f"  {key}: {value}")

    summary += ["", "CHECKS"]
    for c in checks:
        summary.append(
            f"[{c['Status']}] {c['Check']} "
            f"Expected={c['Expected']} Actual={c['Actual']}"
        )

    summary += [
        "",
        "AUTHORIZATION POLICY",
        "  This is a gate, not cleanup execution.",
        "  DeletionAuthorized=False for every manifest row.",
        "  HumanApprovalRequired=True for every manifest row.",
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
    print("D-OBSIDIAN-06.13 R4 - CLEANUP AUTHORIZATION GATE")
    print("=" * 88)
    print("READ-ONLY / NON-DESTRUCTIVE")
    print()
    print("SOURCE CONTRACT")
    print(f"  D609 D-classification rows      : {len(d_candidates)}")
    print(f"  D609 REMOVE-CANDIDATE rows      : {len(d_remove)}")
    print(f"  D609 REVIEW-DUPLICATE D rows    : {len(d_review)}")
    print(f"  D609 KEEP-REFERENCED rows       : {len(d_keep)}")
    print(f"  D611 forensic candidate rows    : {len(forensic_candidates)}")
    print(f"  D612 REVIEW groups              : {len(review_matrix)}")
    print(f"  D612 forensic member aggregate  : {member_aggregate}")
    print()
    print("FINAL CLASSIFICATION DISTRIBUTION")
    for key, value in sorted(final_counts.items()):
        print(f"  {key:30}: {value}")
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
