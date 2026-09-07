from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

AUTH_FILE = REPORTS / "PCIP11_0695_7_AUTHORIZATION_MANIFEST_R2.csv"
R4_FILE = REPORTS / "0695_GENERIC_METRIC_SEMANTIC_IDENTITY_RESOLUTION_R4.csv"

OUT_CSV = REPORTS / "PCIP11_0695_7_SCOPE_DEDUP_AUTH_RECONCILIATION_R2.csv"
OUT_JSON = REPORTS / "PCIP11_0695_7_SCOPE_DEDUP_AUTH_RECONCILIATION_R2.json"
OUT_MD = REPORTS / "PCIP11_0695_7_SCOPE_DEDUP_AUTH_RECONCILIATION_R2.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def normalized(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip()


def semantic_join_key(row: dict[str, str]) -> tuple[str, ...]:
    """
    Primary reconciliation key.

    R4 is authoritative for semantic identity.
    SHA256 + Metric + Resolved_Period + normalized value/unit
    provide an additional integrity guard.
    """
    return (
        normalized(row.get("SHA256")).upper(),
        normalized(row.get("Metric")),
        normalized(row.get("Resolved_Period")),
        normalized(row.get("Value_Parsed")),
        normalized(row.get("Resolved_Unit")),
    )


def r4_identity_key(row: dict[str, str]) -> str:
    """
    R4 Observation_Key is the canonical semantic identity key.

    It is intentionally preferred over the legacy Metric_ID from
    the authorization manifest.
    """
    return normalized(row.get("Observation_Key_R4"))


def canonical_id(row: dict[str, str]) -> str:
    return r4_identity_key(row)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def main() -> int:
    # ------------------------------------------------------------------
    # Safety boundary
    # ------------------------------------------------------------------
    #
    # This script is READ-ONLY.
    # It does not:
    #   - grant authorization
    #   - persist metrics
    #   - write KnowledgeBridge
    #   - modify Vault
    #   - overwrite/delete/rename/move files
    #
    # ------------------------------------------------------------------

    if not AUTH_FILE.exists():
        raise FileNotFoundError(AUTH_FILE)

    if not R4_FILE.exists():
        raise FileNotFoundError(R4_FILE)

    auth_rows = read_csv(AUTH_FILE)
    r4_rows = read_csv(R4_FILE)

    # ------------------------------------------------------------------
    # Contract cardinality
    # ------------------------------------------------------------------

    if len(auth_rows) != 31:
        raise RuntimeError(
            f"FAIL-CLOSED: authorization manifest expected 31 rows, "
            f"found {len(auth_rows)}"
        )

    if len(r4_rows) != 31:
        raise RuntimeError(
            f"FAIL-CLOSED: R4 expected 31 rows, found {len(r4_rows)}"
        )

    # ------------------------------------------------------------------
    # Index R4
    # ------------------------------------------------------------------

    r4_by_row = {}
    r4_by_sha_metric = defaultdict(list)
    r4_by_observation = defaultdict(list)

    for row in r4_rows:
        row_number = normalized(row.get("Row"))

        if not row_number:
            raise RuntimeError(
                "FAIL-CLOSED: R4 contains a row without Row identifier"
            )

        if row_number in r4_by_row:
            raise RuntimeError(
                f"FAIL-CLOSED: duplicate R4 Row={row_number}"
            )

        r4_by_row[row_number] = row

        r4_by_sha_metric[
            (
                normalized(row.get("SHA256")).upper(),
                normalized(row.get("Metric")),
            )
        ].append(row)

        observation = r4_identity_key(row)
        if observation:
            r4_by_observation[observation].append(row)

    # ------------------------------------------------------------------
    # Reconcile authorization → R4
    #
    # IMPORTANT:
    # We use Row only as a source-scope binding.
    # We do NOT use Row as the semantic identity.
    # ------------------------------------------------------------------

    output = []

    for auth in auth_rows:
        auth_row = normalized(auth.get("Row"))

        candidates = r4_by_row.get(auth_row)

        if not candidates:
            raise RuntimeError(
                f"FAIL-CLOSED: authorization row {auth_row} "
                f"has no R4 counterpart"
            )

        if len(candidates) != 1:
            raise RuntimeError(
                f"FAIL-CLOSED: authorization row {auth_row} "
                f"has {len(candidates)} R4 counterparts"
            )

        r4 = candidates[0]

        # --------------------------------------------------------------
        # Integrity cross-check
        # --------------------------------------------------------------

        integrity_checks = {
            "SHA256": (
                normalized(auth.get("SHA256")).upper()
                == normalized(r4.get("SHA256")).upper()
            ),
            "Metric": (
                normalized(auth.get("Metric"))
                == normalized(r4.get("Metric"))
            ),
            "Resolved_Period": (
                normalized(auth.get("Resolved_Period"))
                == normalized(r4.get("Resolved_Period"))
            ),
            "Resolved_Unit": (
                normalized(auth.get("Resolved_Unit"))
                == normalized(r4.get("Resolved_Unit"))
            ),
        }

        if not all(integrity_checks.values()):
            failed = [
                key for key, ok in integrity_checks.items() if not ok
            ]

            raise RuntimeError(
                f"FAIL-CLOSED: R4 mismatch at authorization row "
                f"{auth_row}: {failed}"
            )

        classification = normalized(
            r4.get("Identity_Classification_R4")
        )

        identity_status = normalized(
            r4.get("Identity_Status_R4")
        )

        observation_key = r4_identity_key(r4)

        if not observation_key:
            raise RuntimeError(
                f"FAIL-CLOSED: row {auth_row} has no "
                f"Observation_Key_R4"
            )

        # --------------------------------------------------------------
        # Semantic decision
        # --------------------------------------------------------------

        if (
            classification == "UNIQUE"
            and identity_status == "IDENTITY_READY"
        ):
            decision = "CANONICAL"
            write_action = "CANONICAL_READY"

        elif (
            classification == "EXACT_DUPLICATE"
            and identity_status == "DEDUPLICABLE"
        ):
            decision = "ALIAS_EXACT_DUPLICATE"
            write_action = "ALIAS_ONLY"

        elif (
            classification == "SEMANTICALLY_DISTINCT_CANDIDATES"
            and identity_status == "IDENTITY_READY_WITH_DIMENSION"
            and normalized(r4.get("Semantic_Dimension_Status_R4"))
            == "RESOLVED"
        ):
            decision = "CANONICAL_WITH_DIMENSION"
            write_action = "CANONICAL_READY_WITH_DIMENSION"

        elif (
            identity_status == "BLOCKED_SEMANTIC_IDENTITY"
        ):
            decision = "BLOCKED_SEMANTIC_IDENTITY"
            write_action = "NO_WRITE"

        else:
            decision = "BLOCKED_REQUIRES_REVIEW"
            write_action = "NO_WRITE"

        # --------------------------------------------------------------
        # Preserve authorization state.
        # Never transform NOT_GRANTED into GRANTED.
        # --------------------------------------------------------------

        auth_persistence = normalized(
            auth.get("Metric_Persistence_Authorization")
        )
        auth_kb = normalized(
            auth.get("KnowledgeBridge_Write_Authorization")
        )
        auth_vault = normalized(
            auth.get("Vault_Write_Authorization")
        )
        explicit_grant = normalized(
            auth.get("Explicit_Grant")
        )

        if auth_persistence != "NOT_GRANTED":
            raise RuntimeError(
                f"FAIL-CLOSED: unexpected persistence authorization "
                f"at row {auth_row}: {auth_persistence}"
            )

        if auth_kb != "NOT_GRANTED":
            raise RuntimeError(
                f"FAIL-CLOSED: unexpected KnowledgeBridge authorization "
                f"at row {auth_row}: {auth_kb}"
            )

        if auth_vault != "NOT_GRANTED":
            raise RuntimeError(
                f"FAIL-CLOSED: unexpected Vault authorization "
                f"at row {auth_row}: {auth_vault}"
            )

        if explicit_grant != "NOT_GRANTED":
            raise RuntimeError(
                f"FAIL-CLOSED: unexpected explicit grant "
                f"at row {auth_row}: {explicit_grant}"
            )

        output.append(
            {
                "Authorization_Row": auth_row,
                "SHA256": auth.get("SHA256", ""),
                "Original_Identity": auth.get("Original_Identity", ""),
                "Metric": auth.get("Metric", ""),
                "Value": auth.get("Value", ""),
                "Resolved_Unit": auth.get("Resolved_Unit", ""),
                "Resolved_Period": auth.get("Resolved_Period", ""),
                "Authorization_Metric_ID": auth.get("Metric_ID", ""),
                "Authorization_Knowledge_Evidence_ID": auth.get(
                    "Knowledge_Evidence_ID", ""
                ),
                "R4_Metric_Evidence_ID": r4.get(
                    "Metric_Evidence_ID", ""
                ),
                "R4_Knowledge_Evidence_ID": r4.get(
                    "Knowledge_Evidence_ID", ""
                ),
                "Observation_Key_R4": observation_key,
                "Context_Join_Key_R4": r4.get(
                    "Context_Join_Key_R4", ""
                ),
                "Semantic_Dimension_R4": r4.get(
                    "Semantic_Dimension_R4", ""
                ),
                "Semantic_Dimension_Status_R4": r4.get(
                    "Semantic_Dimension_Status_R4", ""
                ),
                "Semantic_Dimension_Reason_R4": r4.get(
                    "Semantic_Dimension_Reason_R4", ""
                ),
                "Identity_Classification_R4": classification,
                "Identity_Status_R4": identity_status,
                "Canonical_Decision_R2": decision,
                "Write_Action_R2": write_action,
                "Metric_Persistence_Authorization": auth_persistence,
                "KnowledgeBridge_Write_Authorization": auth_kb,
                "Vault_Write_Authorization": auth_vault,
                "Explicit_Grant": explicit_grant,
                "Execution_Status": "NOT_AUTHORIZED",
                "Vault_Modified": "FALSE",
            }
        )

    # ------------------------------------------------------------------
    # Canonical grouping
    # ------------------------------------------------------------------

    canonical_groups = defaultdict(list)

    for row in output:
        decision = row["Canonical_Decision_R2"]

        if decision in {
            "CANONICAL",
            "CANONICAL_WITH_DIMENSION",
            "ALIAS_EXACT_DUPLICATE",
        }:
            canonical_groups[row["Observation_Key_R4"]].append(row)

    canonical_observation_keys = set()

    for row in output:
        decision = row["Canonical_Decision_R2"]

        if decision in {
            "CANONICAL",
            "CANONICAL_WITH_DIMENSION",
        }:
            canonical_observation_keys.add(
                row["Observation_Key_R4"]
            )

        elif decision == "ALIAS_EXACT_DUPLICATE":
            canonical_observation_keys.add(
                row["Observation_Key_R4"]
            )

    # ------------------------------------------------------------------
    # Exact duplicate validation
    # ------------------------------------------------------------------

    exact_duplicate_rows = [
        row
        for row in output
        if row["Identity_Classification_R4"] == "EXACT_DUPLICATE"
    ]

    exact_duplicate_groups = {
        row["Observation_Key_R4"]
        for row in exact_duplicate_rows
    }

    # ------------------------------------------------------------------
    # Dimension group validation
    # ------------------------------------------------------------------

    dimension_rows = [
        row
        for row in output
        if row["Canonical_Decision_R2"]
        == "CANONICAL_WITH_DIMENSION"
    ]

    dimension_groups = {
        row["Observation_Key_R4"]
        for row in dimension_rows
    }

    # ------------------------------------------------------------------
    # Blocked rows
    # ------------------------------------------------------------------

    blocked_rows = [
        row
        for row in output
        if row["Canonical_Decision_R2"]
        in {
            "BLOCKED_SEMANTIC_IDENTITY",
            "BLOCKED_REQUIRES_REVIEW",
        }
    ]

    blocked_semantic_rows = [
        row
        for row in output
        if row["Canonical_Decision_R2"]
        == "BLOCKED_SEMANTIC_IDENTITY"
    ]

    # ------------------------------------------------------------------
    # Expected structural result
    # ------------------------------------------------------------------

    canonical_unique = [
        row
        for row in output
        if row["Canonical_Decision_R2"] == "CANONICAL"
    ]

    canonical_with_dimension = [
        row
        for row in output
        if row["Canonical_Decision_R2"]
        == "CANONICAL_WITH_DIMENSION"
    ]

    canonical_identity_count = len(
        {
            row["Observation_Key_R4"]
            for row in output
            if row["Canonical_Decision_R2"]
            in {
                "CANONICAL",
                "CANONICAL_WITH_DIMENSION",
            }
        }
    )

    # ------------------------------------------------------------------
    # Safety assertions
    # ------------------------------------------------------------------

    assert len(output) == 31

    assert all(
        row["Metric_Persistence_Authorization"] == "NOT_GRANTED"
        for row in output
    )

    assert all(
        row["KnowledgeBridge_Write_Authorization"] == "NOT_GRANTED"
        for row in output
    )

    assert all(
        row["Vault_Write_Authorization"] == "NOT_GRANTED"
        for row in output
    )

    assert all(
        row["Explicit_Grant"] == "NOT_GRANTED"
        for row in output
    )

    assert all(
        row["Execution_Status"] == "NOT_AUTHORIZED"
        for row in output
    )

    assert all(
        row["Vault_Modified"] == "FALSE"
        for row in output
    )

    # Current R4 structure should yield:
    #
    # 26 UNIQUE canonical identities
    # 1 dimension-resolved canonical identity
    # 1 exact-duplicate canonical identity
    #
    # = 28 canonical identities
    #
    # The duplicate rows do not add identities.
    # The 13.09 conflict remains blocked.

    if len(canonical_unique) != 26:
        raise RuntimeError(
            "FAIL-CLOSED: expected 26 UNIQUE canonical rows, "
            f"found {len(canonical_unique)}"
        )

    if len(canonical_with_dimension) != 2:
        raise RuntimeError(
            "FAIL-CLOSED: expected two rows representing the "
            "single dimension-resolved 13.4 identity, "
            f"found {len(canonical_with_dimension)}"
        )

    if len(exact_duplicate_rows) != 2:
        raise RuntimeError(
            "FAIL-CLOSED: expected 2 exact-duplicate rows, "
            f"found {len(exact_duplicate_rows)}"
        )

    if len(exact_duplicate_groups) != 1:
        raise RuntimeError(
            "FAIL-CLOSED: expected 1 exact-duplicate group, "
            f"found {len(exact_duplicate_groups)}"
        )

    if len(blocked_semantic_rows) != 1:
        raise RuntimeError(
            "FAIL-CLOSED: expected exactly one blocked semantic row, "
            f"found {len(blocked_semantic_rows)}"
        )

    if canonical_identity_count != 28:
        raise RuntimeError(
            "FAIL-CLOSED: expected 28 canonical identities, "
            f"found {canonical_identity_count}"
        )

    # ------------------------------------------------------------------
    # Add canonical group metadata to every row
    # ------------------------------------------------------------------

    group_sizes = {
        key: len(rows)
        for key, rows in canonical_groups.items()
    }

    for row in output:
        row["Canonical_Group_Size_R2"] = str(
            group_sizes.get(row["Observation_Key_R4"], 0)
        )

        row["Canonical_Identity_Count_R2"] = str(
            canonical_identity_count
        )

    # ------------------------------------------------------------------
    # Write CSV
    # ------------------------------------------------------------------

    fieldnames = list(output[0].keys())

    with OUT_CSV.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=fieldnames,
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(output)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    decision_counts = Counter(
        row["Canonical_Decision_R2"]
        for row in output
    )

    classification_counts = Counter(
        row["Identity_Classification_R4"]
        for row in output
    )

    summary = {
        "stage": "06.31.2",
        "revision": "R2",
        "status": "PASS",
        "safety_mode": "READ_ONLY_FAIL_CLOSED",
        "authorization_rows": len(auth_rows),
        "generic_r4_rows": len(r4_rows),
        "canonical_identity_count": canonical_identity_count,
        "unique_canonical_rows": len(canonical_unique),
        "dimension_canonical_rows": len(canonical_with_dimension),
        "exact_duplicate_rows": len(exact_duplicate_rows),
        "exact_duplicate_groups": len(exact_duplicate_groups),
        "blocked_semantic_rows": len(blocked_semantic_rows),
        "blocked_rows_total": len(blocked_rows),
        "decision_counts": dict(decision_counts),
        "r4_classification_counts": dict(classification_counts),
        "authorization": "NOT_GRANTED",
        "metric_persistence_authorization": "NOT_GRANTED",
        "knowledgebridge_write_authorization": "NOT_GRANTED",
        "vault_write_authorization": "NOT_GRANTED",
        "execution_status": "NOT_AUTHORIZED",
        "vault_modified": False,
        "auth_manifest_sha256": sha256_file(AUTH_FILE),
        "r4_sha256": sha256_file(R4_FILE),
        "source_r1_retained_as_historical_comparison": True,
    }

    with OUT_JSON.open(
        "w",
        encoding="utf-8",
    ) as fh:
        json.dump(
            summary,
            fh,
            ensure_ascii=False,
            indent=2,
        )

    # ------------------------------------------------------------------
    # Markdown report
    # ------------------------------------------------------------------

    md = f"""# D-OBSIDIAN-06.31.2 — Scope Dedup & Authorization Reconciliation R2

READ-ONLY / FAIL-CLOSED / NO AUTHORIZATION GRANT / NO VAULT WRITE

## Result

- Authorization rows: **{len(auth_rows)}**
- R4 semantic rows: **{len(r4_rows)}**
- Canonical identities: **{canonical_identity_count}**
- UNIQUE canonical rows: **{len(canonical_unique)}**
- Dimension-resolved rows: **{len(canonical_with_dimension)}**
- Exact duplicate rows: **{len(exact_duplicate_rows)}**
- Exact duplicate groups: **{len(exact_duplicate_groups)}**
- Blocked semantic rows: **{len(blocked_semantic_rows)}**
- Total blocked rows: **{len(blocked_rows)}**

## Decision distribution

"""

    for key, value in decision_counts.items():
        md += f"- `{key}`: **{value}**\n"

    md += f"""
## R4 classification

"""

    for key, value in classification_counts.items():
        md += f"- `{key}`: **{value}**\n"

    md += """
## Canonicalization rule

R4 `Observation_Key_R4` is the authoritative semantic identity.

The authorization manifest `Metric_ID` and `Knowledge_Evidence_ID`
are preserved as source authorization identifiers but are not used
as the final semantic identity.

### Exact duplicate

`EXACT_DUPLICATE` + `DEDUPLICABLE`:

- same canonical observation
- alias only
- no second canonical identity
- source authorization row remains preserved

### Dimension-resolved identity

`SEMANTICALLY_DISTINCT_CANDIDATES` +
`IDENTITY_READY_WITH_DIMENSION` +
`Semantic_Dimension_Status_R4=RESOLVED`:

- canonical identity with resolved semantic dimension
- no automatic collapse with unrelated semantic observations

### Semantic conflict

`BLOCKED_SEMANTIC_IDENTITY`:

- no persistence
- no KnowledgeBridge write
- no Vault write
- requires semantic review

## 2024-01 conflict

The `13.4` records share:

- the same SHA256
- metric
- resolved period
- Metric_Evidence_ID
- Knowledge_Evidence_ID
- Context_Join_Key_R4
- Observation_Key_R4

R4 resolves their semantic dimension as `MARKET_VALUE`.

The `13.09` record has no resolved semantic dimension and is
`BLOCKED_SEMANTIC_IDENTITY` because multiple semantic dimensions are
equally supported near the value.

It is therefore not promoted.

## Safety boundary

This report:

- does not grant authorization;
- does not execute metric persistence;
- does not execute KnowledgeBridge;
- does not modify the Vault;
- does not overwrite, delete, rename, or move evidence;
- preserves all 31 authorization rows.

Authorization state remains:

`NOT_GRANTED`

Execution state remains:

`NOT_AUTHORIZED`

Vault modification remains:

`FALSE`

## Integrity

Authorization manifest SHA256:

`{summary["auth_manifest_sha256"]}`

R4 SHA256:

`{summary["r4_sha256"]}`

## Final status

**PASS — RECONCILIATION_R2_COMPLETE**

**READY_FOR_DESIGN_REVIEW_ONLY**

No execution authorization is granted by this artifact.
"""

    OUT_MD.write_text(md, encoding="utf-8")

    # ------------------------------------------------------------------
    # Console output
    # ------------------------------------------------------------------

    print("=" * 90)
    print("0695.7 SCOPE DEDUP & AUTHORIZATION RECONCILIATION R2")
    print("=" * 90)
    print(f"Authorization rows        : {len(auth_rows)}")
    print(f"R4 rows                   : {len(r4_rows)}")
    print(f"Canonical identities      : {canonical_identity_count}")
    print(f"UNIQUE canonical rows     : {len(canonical_unique)}")
    print(f"Dimension rows             : {len(canonical_with_dimension)}")
    print(f"Exact duplicate rows      : {len(exact_duplicate_rows)}")
    print(f"Exact duplicate groups    : {len(exact_duplicate_groups)}")
    print(f"Blocked semantic rows     : {len(blocked_semantic_rows)}")
    print(f"Blocked rows total        : {len(blocked_rows)}")
    print("-" * 90)

    for key, value in decision_counts.items():
        print(f"{key:<35}: {value}")

    print("-" * 90)
    print("Authorization             : NOT_GRANTED")
    print("Metric persistence        : NOT_GRANTED")
    print("KnowledgeBridge           : NOT_GRANTED")
    print("Vault write               : NOT_GRANTED")
    print("Execution                 : NOT_AUTHORIZED")
    print("Vault modified            : FALSE")
    print("-" * 90)
    print(f"CSV                       : {OUT_CSV}")
    print(f"JSON                      : {OUT_JSON}")
    print(f"MD                        : {OUT_MD}")
    print("=" * 90)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())