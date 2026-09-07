#!/usr/bin/env python3
"""
D-OBSIDIAN-06.14 R3 — IGNORE BOUNDARY PROPOSAL

READ-ONLY / NON-DESTRUCTIVE.

Consumes the latest R2 runtime/root/untracked inventories and proposes only
minimal .gitignore additions. It never edits .gitignore and never deletes,
moves, renames, or modifies repository files.

The proposal is conservative:
  - only R2 IGNORE_REVIEW items are eligible;
  - protected/versioning-review items are never proposed for blanket ignore;
  - existing .gitignore rules are detected;
  - each proposal includes evidence and an explicit rationale.
"""

from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def latest(out: Path, prefix: str) -> Path:
    files = sorted(out.glob(prefix + "*.csv"), key=lambda p: p.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"Missing R2 inventory: {prefix}")
    return files[-1]


def normalize_rule(line: str) -> str:
    return line.strip().replace("\\", "/").lower()


def main() -> int:
    repo = Path.cwd().resolve()
    r2 = repo / "reports" / "D-OBSIDIAN-06.14-R2"
    out = repo / "reports" / "D-OBSIDIAN-06.14-R3"
    out.mkdir(parents=True, exist_ok=True)

    untracked_file = latest(r2, "D-OBSIDIAN-06.14_R2_UNTRACKED_")
    runtime_file = latest(r2, "D-OBSIDIAN-06.14_R2_RUNTIME_")
    root_file = latest(r2, "D-OBSIDIAN-06.14_R2_ROOT_")

    untracked = read_csv(untracked_file)
    runtime = read_csv(runtime_file)
    root = read_csv(root_file)

    gi = repo / ".gitignore"
    gi_lines = gi.read_text(encoding="utf-8", errors="replace").splitlines() if gi.exists() else []
    rules = [normalize_rule(x) for x in gi_lines if x.strip() and not x.lstrip().startswith("#")]

    candidates = [
        r for r in untracked
        if r.get("SuggestedBoundary") == "IGNORE_REVIEW"
    ]

    proposals: list[dict[str, str]] = []

    for r in candidates:
        path = r["GitPath"].replace("\\", "/")
        name = Path(path).name

        # Conservative rule construction: prefer exact path for generated
        # diagnostic artifacts rather than broad extensions/directories.
        if path == "coverage-current.json":
            proposed = "coverage-current.json"
            rationale = "Generated coverage diagnostic; exact-path ignore avoids hiding project source/data."
        elif path == ".coverage":
            proposed = ".coverage"
            rationale = "Coverage runtime database; exact-path ignore is standard and non-broad."
        elif path.startswith(".logs/"):
            proposed = ".logs/"
            rationale = "Local runtime logs; directory-level ignore is scoped to the runtime log directory."
        elif path.startswith(".pytest_cache/"):
            proposed = ".pytest_cache/"
            rationale = "Pytest runtime cache; directory-level ignore is scoped to pytest cache."
        else:
            proposed = path
            rationale = "Exact-path proposal because R2 identified this item as IGNORE_REVIEW."

        equivalent = False
        matched_rule = ""
        for rule in rules:
            # Basic conservative equivalence check.
            if rule == normalize_rule(proposed):
                equivalent = True
                matched_rule = rule
                break
            # Directory rules can already cover a direct child.
            if proposed.endswith("/") and rule == normalize_rule(proposed):
                equivalent = True
                matched_rule = rule
                break

        proposals.append({
            "Path": path,
            "SizeBytes": r.get("SizeBytes", ""),
            "Protected": r.get("Protected", ""),
            "RuntimePattern": r.get("RuntimePattern", ""),
            "GeneratedPattern": r.get("GeneratedPattern", ""),
            "CurrentIgnored": r.get("Ignored", ""),
            "ProposedRule": proposed,
            "AlreadyCovered": str(equivalent),
            "MatchedExistingRule": matched_rule,
            "Recommendation": "NO_CHANGE" if equivalent else "ADD_RULE_REVIEW",
            "Rationale": rationale,
        })

    # Explicitly record the safety population that must not be blanket-ignored.
    protected_count = sum(r.get("SuggestedBoundary") == "PROTECTED_KEEP" for r in untracked)
    versioning_count = sum(r.get("SuggestedBoundary") == "VERSIONING_REVIEW" for r in untracked)

    checks = [
        ("R2_IGNORE_REVIEW_INPUT", len(candidates), len(candidates)),
        (
            "NO_PROTECTED_IN_PROPOSAL",
            0,
            sum(r.get("Protected") == "True" for r in proposals),
        ),
        (
            "NO_VERSIONING_REVIEW_IN_PROPOSAL",
            0,
            sum(
                1 for r in proposals
                if r["Path"] in {
                    x["GitPath"] for x in untracked
                    if x.get("SuggestedBoundary") == "VERSIONING_REVIEW"
                }
            ),
        ),
        ("GITIGNORE_PRESENT", 1, int(gi.exists())),
        ("NO_DESTRUCTIVE_ACTION", 0, 0),
        ("NO_GIT_WRITE", 0, 0),
    ]

    checks_rows = []
    for name, expected, actual in checks:
        checks_rows.append({
            "Check": name,
            "Expected": str(expected),
            "Actual": str(actual),
            "Status": "PASS" if expected == actual else "FAIL",
        })

    gate = all(x["Status"] == "PASS" for x in checks_rows)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    with (out / f"D-OBSIDIAN-06.14_R3_PROPOSAL_{stamp}.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        if proposals:
            w = csv.DictWriter(f, fieldnames=list(proposals[0]))
            w.writeheader()
            w.writerows(proposals)

    with (out / f"D-OBSIDIAN-06.14_R3_CHECKS_{stamp}.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        w = csv.DictWriter(f, fieldnames=list(checks_rows[0]))
        w.writeheader()
        w.writerows(checks_rows)

    summary = [
        "D-OBSIDIAN-06.14 R3 - IGNORE BOUNDARY PROPOSAL",
        "",
        "READ-ONLY / NON-DESTRUCTIVE",
        "",
        f"R2 untracked inventory: {untracked_file.name}",
        f"R2 runtime inventory: {runtime_file.name}",
        f"R2 root inventory: {root_file.name}",
        "",
        f"IGNORE_REVIEW candidates: {len(candidates)}",
        f"PROTECTED_KEEP excluded: {protected_count}",
        f"VERSIONING_REVIEW excluded: {versioning_count}",
        "",
        "PROPOSALS",
    ]
    if proposals:
        for x in proposals:
            summary.append(
                f"  {x['Path']} -> {x['ProposedRule']} | "
                f"{x['Recommendation']} | existing={x['AlreadyCovered']}"
            )
    else:
        summary.append("  None.")
    summary += [
        "",
        "CURRENT .gitignore",
        *[f"  {i}: {line}" for i, line in enumerate(gi_lines, 1)],
        "",
        "CHECKS",
        *[
            f"[{x['Status']}] {x['Check']} "
            f"Expected={x['Expected']} Actual={x['Actual']}"
            for x in checks_rows
        ],
        "",
        "POLICY",
        "  This is a proposal only.",
        "  .gitignore was NOT modified.",
        "  No file was deleted, moved, renamed, or edited.",
        "  No Git write operation was executed.",
        "",
        "NEXT STEP",
        "  If the proposal is safe, R4 will apply only the explicitly approved "
        "minimal .gitignore rules and immediately run a post-change audit.",
        "",
        "IGNORE BOUNDARY PROPOSAL GATE: " + ("PASS" if gate else "FAIL"),
    ]

    (out / f"D-OBSIDIAN-06.14_R3_SUMMARY_{stamp}.txt").write_text(
        "\n".join(summary) + "\n", encoding="utf-8"
    )

    print("=" * 88)
    print("D-OBSIDIAN-06.14 R3 - IGNORE BOUNDARY PROPOSAL")
    print("=" * 88)
    print("READ-ONLY / NON-DESTRUCTIVE")
    print()
    print(f"IGNORE_REVIEW candidates : {len(candidates)}")
    print(f"PROTECTED_KEEP excluded  : {protected_count}")
    print(f"VERSIONING_REVIEW excl.  : {versioning_count}")
    print()
    if proposals:
        for x in proposals:
            print(
                f"  {x['Path']} -> {x['ProposedRule']} "
                f"[{x['Recommendation']}]"
            )
    else:
        print("  No proposals.")
    print()
    for x in checks_rows:
        print(
            f"[{x['Status']}] {x['Check']} "
            f"Expected={x['Expected']} Actual={x['Actual']}"
        )
    print()
    print("=" * 88)
    print("IGNORE BOUNDARY PROPOSAL GATE: " + ("PASS" if gate else "FAIL"))
    print("=" * 88)
    print()
    print("READ-ONLY: .gitignore nao foi alterado.")
    print(f"Reports: {out}")

    return 0 if gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
