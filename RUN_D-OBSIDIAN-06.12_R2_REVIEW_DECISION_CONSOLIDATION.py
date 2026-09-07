#!/usr/bin/env python3
"""
D-OBSIDIAN-06.12 R2 — REVIEW DECISION CONSOLIDATION

READ-ONLY / NON-DESTRUCTIVE.

Consumes the latest D-OBSIDIAN-06.12 R1 forensic CSVs and consolidates
the 31 REVIEW groups into a decision-grade matrix.

Important:
  - No deletion/move/rename.
  - No Git commands.
  - No automatic cleanup.
  - Existing evidence is preserved; this stage only classifies it.

Decision model:
  PRESERVE:
      any protected member.

  DUPLICATE-CONFIRMED:
      canonical path exists physically and group is not protected.

  REVIEW-BLOCKED:
      no physical canonical exists, or evidence is insufficient.

The script also reports whether any REVIEW group can be promoted
without human approval. By design, no deletion is authorized.
"""

from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path


EXPECTED_REVIEW_GROUPS = 31
EXPECTED_REVIEW_ROWS = 126


def latest_file(directory: Path, pattern: str) -> Path:
    files = list(directory.glob(pattern))
    if not files:
        raise FileNotFoundError(f"Fonte nao encontrada: {pattern}")
    return max(files, key=lambda p: p.stat().st_mtime)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def as_bool(value: str) -> bool:
    return str(value).strip().lower() in {
        "true", "1", "yes", "sim"
    }


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
    source_dir = repo / "reports" / "D-OBSIDIAN-06.12-R1"
    out_dir = repo / "reports" / "D-OBSIDIAN-06.12-R2"
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    groups_file = latest_file(
        source_dir, "D-OBSIDIAN-06.12_R1_REVIEW_GROUPS_*.csv"
    )
    members_file = latest_file(
        source_dir, "D-OBSIDIAN-06.12_R1_REVIEW_MEMBERS_*.csv"
    )
    checks_file = latest_file(
        source_dir, "D-OBSIDIAN-06.12_R1_CHECKS_*.csv"
    )

    groups = read_csv(groups_file)
    members = read_csv(members_file)
    r1_checks = read_csv(checks_file)

    print()
    print("=" * 88)
    print("D-OBSIDIAN-06.12 R2 - REVIEW DECISION CONSOLIDATION")
    print("=" * 88)
    print(f"Repository : {repo}")
    print(f"Output     : {out_dir}")
    print()
    print("READ-ONLY / NON-DESTRUCTIVE")
    print()
    print("INPUT")
    print(f"  R1 groups  : {len(groups)}")
    print(f"  R1 members : {len(members)}")
    print(f"  R1 checks  : {len(r1_checks)}")

    # ------------------------------------------------------------------
    # Index members by hash
    # ------------------------------------------------------------------
    members_by_hash: dict[str, list[dict[str, str]]] = {}

    for row in members:
        h = (row.get("Hash") or "").strip()
        if h:
            members_by_hash.setdefault(h, []).append(row)

    # ------------------------------------------------------------------
    # Consolidate each REVIEW group
    # ------------------------------------------------------------------
    decisions: list[dict] = []

    for group in groups:
        h = (group.get("Hash") or "").strip()
        gm = members_by_hash.get(h, [])

        protected_paths = [
            x for x in (group.get("ProtectedPaths") or "").split(" || ")
            if x
        ]

        existing_paths = [
            x for x in (group.get("ExistingPaths") or "").split(" || ")
            if x
        ]

        canonical_existing_paths = [
            x for x in (
                group.get("CanonicalExistingPaths") or ""
            ).split(" || ")
            if x
        ]

        strong_refs = int(group.get("StrongTextReferences") or 0)
        weak_refs = int(group.get("WeakBasenameReferences") or 0)

        if protected_paths:
            decision = "PRESERVE"
            reason = (
                "Grupo contem membro protegido; fora do escopo de limpeza."
            )
            risk = "HIGH"

        elif canonical_existing_paths:
            decision = "DUPLICATE-CONFIRMED"
            reason = (
                "Canonical fisicamente existente foi confirmada; "
                "duplicidade estrutural permanece sem autorizacao de exclusao."
            )
            risk = "MEDIUM"

        elif existing_paths and strong_refs > 0:
            decision = "REVIEW-BLOCKED"
            reason = (
                "Membros existentes possuem referencias textuais fortes; "
                "nao ha canonical fisicamente confirmada."
            )
            risk = "HIGH"

        elif existing_paths:
            decision = "REVIEW-BLOCKED"
            reason = (
                "Membros existem, mas nao ha canonical fisicamente confirmada; "
                "ausencia de referencia nao autoriza exclusao."
            )
            risk = "HIGH"

        else:
            decision = "REVIEW-BLOCKED"
            reason = (
                "Nenhum membro existe fisicamente na varredura atual; "
                "manter registro para reconciliacao/historico."
            )
            risk = "MEDIUM"

        decisions.append({
            "Hash": h,
            "GroupSize": group.get("GroupSize", ""),
            "OriginalGroupDecision": group.get("GroupDecision", ""),
            "DecisionRows": group.get("DecisionRows", ""),
            "CanonicalRows": group.get("CanonicalRows", ""),
            "CanonicalStatus": group.get("CanonicalStatus", ""),
            "Paths": group.get("Paths", ""),
            "ExistingPaths": group.get("ExistingPaths", ""),
            "ProtectedPaths": group.get("ProtectedPaths", ""),
            "CanonicalPaths": group.get("CanonicalPaths", ""),
            "CanonicalExistingPaths": group.get("CanonicalExistingPaths", ""),
            "StrongTextReferences": strong_refs,
            "WeakBasenameReferences": weak_refs,
            "ForensicDecision": decision,
            "Risk": risk,
            "Reason": reason,
            "HumanApprovalRequired": True,
            "DeletionAuthorized": False,
        })

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------
    checks: list[dict] = []

    def check(name: str, expected: int, actual: int):
        checks.append({
            "Check": name,
            "Expected": expected,
            "Actual": actual,
            "Status": "PASS" if expected == actual else "FAIL",
        })

    check("REVIEW_GROUPS", EXPECTED_REVIEW_GROUPS, len(groups))

    review_rows = sum(
        int(row.get("DecisionRows") or 0)
        for row in groups
    )
    # The group report contains 31 groups whose DecisionRows collectively
    # represent the 126 REVIEW-DUPLICATE records.
    check("REVIEW_ROWS", EXPECTED_REVIEW_ROWS, review_rows)

    decision_hashes = {
        row["Hash"] for row in decisions if row["Hash"]
    }
    group_hashes = {
        row["Hash"] for row in groups if row.get("Hash")
    }
    check(
        "GROUP_HASH_COVERAGE",
        len(group_hashes),
        len(decision_hashes),
    )

    duplicate_confirmed = sum(
        row["ForensicDecision"] == "DUPLICATE-CONFIRMED"
        for row in decisions
    )
    preserve = sum(
        row["ForensicDecision"] == "PRESERVE"
        for row in decisions
    )
    blocked = sum(
        row["ForensicDecision"] == "REVIEW-BLOCKED"
        for row in decisions
    )

    # Every item requires explicit human approval.
    approval_violations = sum(
        row["HumanApprovalRequired"] is not True
        for row in decisions
    )
    deletion_violations = sum(
        row["DeletionAuthorized"] is not False
        for row in decisions
    )

    check("NO_APPROVAL_BYPASS", 0, approval_violations)
    check("NO_DELETION_AUTHORIZATION", 0, deletion_violations)

    # ------------------------------------------------------------------
    # Outputs
    # ------------------------------------------------------------------
    matrix_out = out_dir / (
        f"D-OBSIDIAN-06.12_R2_REVIEW_DECISION_MATRIX_{timestamp}.csv"
    )
    summary_out = out_dir / (
        f"D-OBSIDIAN-06.12_R2_SUMMARY_{timestamp}.txt"
    )
    checks_out = out_dir / (
        f"D-OBSIDIAN-06.12_R2_CHECKS_{timestamp}.csv"
    )

    write_csv(matrix_out, decisions)
    write_csv(checks_out, checks)

    failures = [x for x in checks if x["Status"] == "FAIL"]
    gate = not failures

    summary = [
        "D-OBSIDIAN-06.12 R2 - REVIEW DECISION CONSOLIDATION",
        "",
        "READ-ONLY / NON-DESTRUCTIVE",
        "",
        f"REVIEW groups: {len(groups)}",
        f"REVIEW rows: {review_rows}",
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
        "SAFETY",
        "No files removed.",
        "No files moved.",
        "No files renamed.",
        "No source contents modified.",
        "No git commands executed.",
        "",
        "FORENSIC DECISION GATE: " + ("PASS" if gate else "FAIL"),
    ])

    summary_out.write_text(
        "\n".join(summary) + "\n",
        encoding="utf-8",
    )

    # ------------------------------------------------------------------
    # Console
    # ------------------------------------------------------------------
    print()
    print("=" * 88)
    print("D-OBSIDIAN-06.12 R2 - RESULTADO")
    print("=" * 88)
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
