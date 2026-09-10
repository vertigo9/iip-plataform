#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

def latest(directory: Path, pattern: str) -> Path:
    files = list(directory.glob(pattern))
    if not files:
        raise FileNotFoundError(f"Arquivo nao encontrado: {directory}\\{pattern}")
    return max(files, key=lambda x: x.stat().st_mtime)

def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def main() -> int:
    repo = Path.cwd().resolve()
    r1 = repo / "reports" / "D-OBSIDIAN-06.12-R1"
    d69 = repo / "reports" / "D-OBSIDIAN-06.9-R1"
    out = repo / "reports" / "D-OBSIDIAN-06.12-R2"
    out.mkdir(parents=True, exist_ok=True)

    groups_file = latest(r1, "D-OBSIDIAN-06.12_R1_REVIEW_GROUPS_*.csv")
    members_file = latest(r1, "D-OBSIDIAN-06.12_R1_REVIEW_MEMBERS_*.csv")
    decision_file = latest(d69, "D-OBSIDIAN-06.9_R1_DECISION_MATRIX_*.csv")

    groups = read_csv(groups_file)
    members = read_csv(members_file)
    decisions = read_csv(decision_file)

    review = [
        r for r in decisions
        if (r.get("Decision") or "").strip() == "REVIEW-DUPLICATE"
    ]

    def hashes(rows):
        return {
            (r.get("Hash") or "").strip()
            for r in rows
            if (r.get("Hash") or "").strip()
        }

    gh = hashes(groups)
    mh = hashes(members)
    rh = hashes(review)

    review_by_hash = defaultdict(list)
    member_by_hash = defaultdict(list)
    for r in review:
        review_by_hash[(r.get("Hash") or "").strip()].append(r)
    for r in members:
        member_by_hash[(r.get("Hash") or "").strip()].append(r)

    common = gh & rh
    review_only = rh - gh
    group_only = gh - rh

    print("=" * 88)
    print("D-OBSIDIAN-06.12 R3 - HASH RECONCILIATION DIAGNOSTIC")
    print("=" * 88)
    print("READ-ONLY / NON-DESTRUCTIVE")
    print()
    print(f"GROUP rows             : {len(groups)}")
    print(f"GROUP unique hashes    : {len(gh)}")
    print(f"MEMBER rows            : {len(members)}")
    print(f"MEMBER unique hashes   : {len(mh)}")
    print(f"REVIEW rows (06.09)    : {len(review)}")
    print(f"REVIEW unique hashes   : {len(rh)}")
    print()
    print(f"GROUP ∩ REVIEW hashes  : {len(common)}")
    print(f"REVIEW-only hashes     : {len(review_only)}")
    print(f"GROUP-only hashes      : {len(group_only)}")
    print()

    print("REVIEW ROWS PER HASH")
    dist = Counter(len(v) for v in review_by_hash.values())
    for n in sorted(dist):
        print(f"  {n:>3} row(s): {dist[n]:>3} hash(es)")
    print()

    print("R1 GROUP DECISION ROWS")
    group_reported = Counter()
    for g in groups:
        try:
            n = int((g.get("DecisionRows") or "0").strip())
        except ValueError:
            n = 0
        group_reported[n] += 1
    for n in sorted(group_reported):
        print(f"  DecisionRows={n}: {group_reported[n]} group(s)")
    print()

    print("REVIEW-ONLY HASHES WITH AUTHORITATIVE ROW COUNTS")
    for h in sorted(review_only):
        print(f"  {h} -> {len(review_by_hash[h])} row(s)")
    print()

    print("COMMON HASHES: AUTHORITATIVE VS R1 FORENSIC")
    for h in sorted(common):
        print(
            f"  {h} -> review={len(review_by_hash[h])}; "
            f"members={len(member_by_hash.get(h, []))}"
        )
    print()

    # Export the exact mismatch so the next consolidation script can consume it.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mismatch = []
    for h in sorted(rh | gh):
        mismatch.append({
            "Hash": h,
            "InR1Groups": h in gh,
            "InR1Members": h in mh,
            "In06_09ReviewMatrix": h in rh,
            "AuthoritativeReviewRows": len(review_by_hash.get(h, [])),
            "R1ForensicMemberRows": len(member_by_hash.get(h, [])),
        })

    out_file = out / f"D-OBSIDIAN-06.12_R3_HASH_RECONCILIATION_{stamp}.csv"
    with out_file.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=mismatch[0].keys())
        w.writeheader()
        w.writerows(mismatch)

    print(f"Diagnostic CSV: {out_file}")
    print()
    print("CONCLUSAO DO DIAGNOSTICO:")
    print("  Nao executar exclusao nem consolidacao decisoria ainda.")
    print("  O universo de grupos R1 (31 hashes) nao cobre o universo")
    print("  autoritativo REVIEW-DUPLICATE (88 hashes / 126 rows).")
    print("  O proximo passo deve explicar a origem dos 57 hashes REVIEW-only.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
