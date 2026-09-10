#!/usr/bin/env python3
"""
D-OBSIDIAN-06.12 R3 — GLOBAL REVIEW TRIANGULATION

READ-ONLY / NON-DESTRUCTIVE.

Purpose:
  Reconcile the 126 REVIEW-DUPLICATE decision rows from D-OBSIDIAN-06.09
  with the 430 duplicate groups and the 31 REVIEW groups used by D-OBSIDIAN-06.12.

Important:
  REVIEW-DUPLICATE (decision-row level) is NOT equivalent to
  GroupDecision=REVIEW (group level).

This script does not delete, move, rename, modify source files, or execute Git.
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
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    repo = Path.cwd().resolve()

    d69 = repo / "reports" / "D-OBSIDIAN-06.9-R1"
    d610 = repo / "reports" / "D-OBSIDIAN-06.10-R4"
    d612 = repo / "reports" / "D-OBSIDIAN-06.12-R1"
    out = repo / "reports" / "D-OBSIDIAN-06.12-R3"
    out.mkdir(parents=True, exist_ok=True)

    decision_file = latest(d69, "D-OBSIDIAN-06.9_R1_DECISION_MATRIX_*.csv")
    duplicate_file = latest(d69, "D-OBSIDIAN-06.9_R1_DUPLICATE_GROUPS_*.csv")

    # R4 canonical triangulation output from 06.10.
    canonical_files = list(d610.glob("*CANONICAL*"))
    canonical_file = max(canonical_files, key=lambda p: p.stat().st_mtime) if canonical_files else None

    # R1 group/member evidence from 06.12.
    group_file = latest(d612, "*REVIEW_GROUPS_*.csv")
    member_file = latest(d612, "*REVIEW_MEMBERS_*.csv")

    decisions = read_csv(decision_file)
    duplicate_groups = read_csv(duplicate_file)
    groups612 = read_csv(group_file)
    members612 = read_csv(member_file)

    review_rows = [
        r for r in decisions
        if (r.get("Decision") or "").strip() == "REVIEW-DUPLICATE"
    ]

    group_by_hash = {
        (r.get("Hash") or "").strip(): r
        for r in duplicate_groups
        if (r.get("Hash") or "").strip()
    }

    review_by_hash: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in review_rows:
        h = (r.get("Hash") or "").strip()
        if h:
            review_by_hash[h].append(r)

    review612_by_hash = {
        (r.get("Hash") or "").strip(): r
        for r in groups612
        if (r.get("Hash") or "").strip()
    }

    member612_by_hash: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in members612:
        h = (r.get("Hash") or "").strip()
        if h:
            member612_by_hash[h].append(r)

    # 06.10 canonical status source is optional for classification enrichment.
    canonical_by_hash: dict[str, list[dict[str, str]]] = defaultdict(list)
    if canonical_file:
        for r in read_csv(canonical_file):
            h = (r.get("Hash") or "").strip()
            if h:
                canonical_by_hash[h].append(r)

    rows = []
    class_counts = Counter()

    for h, rrows in sorted(review_by_hash.items()):
        dg = group_by_hash.get(h)
        g612 = review612_by_hash.get(h)
        crows = canonical_by_hash.get(h, [])

        if dg is None:
            classification = "NOT_RECONCILED"
            reason = "REVIEW-DUPLICATE hash has no duplicate-group record in 06.09."
        else:
            group_decision = (dg.get("GroupDecision") or "").strip()

            if group_decision == "REVIEW":
                classification = "REVIEW"
                reason = "Hash belongs to the 06.12 forensic REVIEW population."
            elif group_decision == "HAS-CANONICAL":
                classification = "HAS-CANONICAL"
                reason = "Hash belongs to a 06.09 HAS-CANONICAL duplicate group."
            elif group_decision == "PROTECTED-GROUP":
                classification = "PROTECTED-GROUP"
                reason = "Hash belongs to a protected duplicate group."
            else:
                classification = "OTHER-GROUP-DECISION"
                reason = f"Unexpected/non-target GroupDecision={group_decision!r}."

        class_counts[classification] += 1

        rows.append({
            "Hash": h,
            "AuthoritativeReviewRows": str(len(rrows)),
            "Six09GroupExists": str(dg is not None),
            "Six09GroupDecision": (dg.get("GroupDecision", "") if dg else ""),
            "Six10CanonicalRows": str(len(crows)),
            "Six12ReviewGroupExists": str(g612 is not None),
            "Six12ForensicMemberRows": str(len(member612_by_hash.get(h, []))),
            "Classification": classification,
            "Reason": reason,
        })

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    detail = out / f"D-OBSIDIAN-06.12_R3_GLOBAL_TRIANGULATION_{stamp}.csv"
    summary = out / f"D-OBSIDIAN-06.12_R3_SUMMARY_{stamp}.txt"

    write_csv(detail, rows)

    checks = [
        ("REVIEW_ROWS", 126, len(review_rows)),
        ("REVIEW_UNIQUE_HASHES", 88, len(review_by_hash)),
        ("DUPLICATE_GROUPS", 430, len(duplicate_groups)),
        ("REVIEW_GROUPS_06_12", 31, len(review612_by_hash)),
        ("REVIEW_HASHES_RECONCILED_TO_06_09_GROUPS", 88, sum(
            group_by_hash.get(h) is not None for h in review_by_hash
        )),
        ("REVIEW_HASHES_WITHOUT_06_09_GROUP", 0, sum(
            group_by_hash.get(h) is None for h in review_by_hash
        )),
        ("REVIEW_HASHES_MATCHING_06_12_REVIEW_GROUP", 31, sum(
            review612_by_hash.get(h) is not None for h in review_by_hash
        )),
        ("REVIEW_ROWS_IN_06_12_REVIEW_GROUPS", 64, sum(
            len(v) for h, v in review_by_hash.items() if review612_by_hash.get(h) is not None
        )),
    ]

    gate = all(actual == expected for _, expected, actual in checks)

    text = [
        "D-OBSIDIAN-06.12 R3 - GLOBAL REVIEW TRIANGULATION",
        "",
        "READ-ONLY / NON-DESTRUCTIVE",
        "",
        "CLASSIFICATION OF 88 UNIQUE REVIEW-DUPLICATE HASHES",
    ]
    for key in (
        "REVIEW", "HAS-CANONICAL", "PROTECTED-GROUP",
        "OTHER-GROUP-DECISION", "NOT_RECONCILED"
    ):
        text.append(f"  {key}: {class_counts.get(key, 0)}")

    text += ["", "CHECKS"]
    for name, expected, actual in checks:
        text.append(
            f"[{'PASS' if expected == actual else 'FAIL'}] "
            f"{name} Expected={expected} Actual={actual}"
        )

    text += [
        "",
        "INTERPRETATION",
        "  06.09 REVIEW-DUPLICATE is a decision-row population.",
        "  06.12 GroupDecision=REVIEW is a group population.",
        "  These populations are intentionally not forced to have equal size.",
        "",
        "SAFETY",
        "  No deletion.",
        "  No move.",
        "  No rename.",
        "  No source modification.",
        "  No Git operation.",
        "",
        "TRIANGULATION GATE: " + ("PASS" if gate else "FAIL"),
        f"Detail CSV: {detail}",
    ]
    summary.write_text("\n".join(text) + "\n", encoding="utf-8")

    print("=" * 88)
    print("D-OBSIDIAN-06.12 R3 - GLOBAL REVIEW TRIANGULATION")
    print("=" * 88)
    print("READ-ONLY / NON-DESTRUCTIVE")
    print()
    print(f"REVIEW rows (06.09)        : {len(review_rows)}")
    print(f"REVIEW unique hashes       : {len(review_by_hash)}")
    print(f"DUPLICATE groups (06.09)  : {len(duplicate_groups)}")
    print(f"REVIEW groups (06.12)      : {len(review612_by_hash)}")
    print()
    print("CLASSIFICATION OF 88 UNIQUE REVIEW-DUPLICATE HASHES")
    for key in (
        "REVIEW", "HAS-CANONICAL", "PROTECTED-GROUP",
        "OTHER-GROUP-DECISION", "NOT_RECONCILED"
    ):
        print(f"  {key:24}: {class_counts.get(key, 0)}")
    print()
    for name, expected, actual in checks:
        print(
            f"[{'PASS' if expected == actual else 'FAIL'}] "
            f"{name} Expected={expected} Actual={actual}"
        )
    print()
    print("=" * 88)
    print("TRIANGULATION GATE: " + ("PASS" if gate else "FAIL"))
    print("=" * 88)
    print()
    print("READ-ONLY: nenhuma acao destrutiva foi executada.")
    print(f"Reports: {out}")
    return 0 if gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
