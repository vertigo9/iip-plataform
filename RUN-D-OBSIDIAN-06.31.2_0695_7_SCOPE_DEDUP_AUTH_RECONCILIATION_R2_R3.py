from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

AUTH = REPORTS / "PCIP11_0695_7_AUTHORIZATION_MANIFEST_R2.csv"
R4 = REPORTS / "0695_GENERIC_METRIC_SEMANTIC_IDENTITY_RESOLUTION_R4.csv"

OUT_CSV = REPORTS / "PCIP11_0695_7_SCOPE_DEDUP_AUTH_RECONCILIATION_R2.csv"
OUT_MD = REPORTS / "PCIP11_0695_7_SCOPE_DEDUP_AUTH_RECONCILIATION_R2.md"
OUT_JSON = REPORTS / "PCIP11_0695_7_SCOPE_DEDUP_AUTH_RECONCILIATION_R2.json"


REQUIRED_AUTH = {
    "Row",
    "SHA256",
    "FileName",
    "Original_Identity",
    "Lineage",
    "Metric",
    "Value",
    "Original_Unit",
    "Resolved_Unit",
    "Scale",
    "Resolved_Period",
    "Contract_Status",
    "Authorization_Scope",
    "Authorization_Decision",
    "Metric_Persistence_Authorization",
    "KnowledgeBridge_Write_Authorization",
    "Vault_Write_Authorization",
    "Execution_Status",
    "Target_Binding",
    "Metric_ID",
    "Knowledge_Evidence_ID",
    "Target_Relative",
    "Target_Status",
    "Scope_Status",
    "Authorization_Status",
    "Explicit_Grant",
    "Stage_Status",
}

REQUIRED_R4 = {
    "Row",
    "SHA256",
    "FileName",
    "Original_Identity",
    "Original_Ticker",
    "Canonical_Ticker",
    "Lineage",
    "Lineage_Status",
    "Metric",
    "Value_Raw",
    "Value_Parsed",
    "Original_Unit",
    "Resolved_Unit",
    "Scale",
    "Legacy_Period",
    "Resolved_Period",
    "Source_Date",
    "Document_ID",
    "Metric_Evidence_ID",
    "Knowledge_Evidence_ID",
    "Validation_Status",
    "Validation_Reason",
    "Persistence_Executed",
    "KnowledgeBridge_Executed",
    "Vault_Changed",
    "Semantic_Dimension_R4",
    "Semantic_Dimension_Status_R4",
    "Semantic_Dimension_Reason_R4",
    "Semantic_Local_Context_Hits_R4",
    "Identity_Classification_R4",
    "Observation_Key_R4",
    "Identity_Status_R4",
    "Context_Join_Key_R4",
    "Legacy_Period_Preserved_R4",
    "Resolved_Period_Preserved_R4",
}


def clean(value: str | None) -> str:
    return (value or "").strip()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def fail(message: str) -> None:
    raise RuntimeError(f"FAIL-CLOSED: {message}")


def main() -> int:
    print("=" * 100)
    print("D-OBSIDIAN-06.31.2 - 0695.7 SCOPE DEDUP & AUTH RECONCILIATION R2")
    print("=" * 100)
    print("READ-ONLY / FAIL-CLOSED / NO AUTHORIZATION GRANT / NO VAULT WRITE")
    print()

    # ------------------------------------------------------------------
    # Safety boundary
    # ------------------------------------------------------------------

    if not AUTH.exists():
        raise FileNotFoundError(str(AUTH))

    if not R4.exists():
        raise FileNotFoundError(str(R4))

    auth = load_csv(AUTH)
    r4 = load_csv(R4)

    if len(auth) != 31:
        fail(f"authorization manifest expected 31 rows, found {len(auth)}")

    if len(r4) != 31:
        fail(f"R4 expected 31 rows, found {len(r4)}")

    # ------------------------------------------------------------------
    # Schema validation
    # ------------------------------------------------------------------

    missing_auth = REQUIRED_AUTH - set(auth[0])
    missing_r4 = REQUIRED_R4 - set(r4[0])

    if missing_auth:
        fail(f"authorization schema missing fields: {sorted(missing_auth)}")

    if missing_r4:
        fail(f"R4 schema missing fields: {sorted(missing_r4)}")

    # ------------------------------------------------------------------
    # Build R4 row index.
    #
    # Row is used ONLY as an exact source-scope binding.
    # It is NOT the semantic identity.
    # ------------------------------------------------------------------

    r4_by_row: dict[str, dict[str, str]] = {}

    for row in r4:
        row_id = clean(row.get("Row"))

        if not row_id:
            fail("R4 contains a row without Row identifier")

        if row_id in r4_by_row:
            fail(f"duplicate R4 Row identifier: {row_id}")

        r4_by_row[row_id] = row

    # Authorization rows must also be unique.
    auth_rows = [clean(row.get("Row")) for row in auth]

    if len(auth_rows) != len(set(auth_rows)):
        fail("authorization manifest contains duplicate Row identifiers")

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------

    reconciled = []

    for ar in auth:
        row_id = clean(ar.get("Row"))
        rr = r4_by_row.get(row_id)

        if rr is None:
            fail(f"authorization row {row_id} has no R4 counterpart")

        # --------------------------------------------------------------
        # Source integrity checks
        # --------------------------------------------------------------

        integrity_fields = (
            "SHA256",
            "Metric",
            "Resolved_Unit",
            "Resolved_Period",
        )

        for field in integrity_fields:
            auth_value = clean(ar.get(field)).upper() if field == "SHA256" else clean(ar.get(field))
            r4_value = clean(rr.get(field)).upper() if field == "SHA256" else clean(rr.get(field))

            if auth_value != r4_value:
                fail(
                    f"row {row_id} mismatch in {field}: "
                    f"authorization={auth_value!r}, R4={r4_value!r}"
                )

        # --------------------------------------------------------------
        # Authorization safety checks.
        #
        # R2 must never transform NOT_GRANTED into GRANTED.
        # --------------------------------------------------------------

        safety_fields = {
            "Metric_Persistence_Authorization": "NOT_GRANTED",
            "KnowledgeBridge_Write_Authorization": "NOT_GRANTED",
            "Vault_Write_Authorization": "NOT_GRANTED",
            "Explicit_Grant": "NOT_GRANTED",
            "Authorization_Status": "NOT_GRANTED",
            "Execution_Status": "NOT_AUTHORIZED",
        }

        for field, expected in safety_fields.items():
            actual = clean(ar.get(field))

            if actual != expected:
                fail(
                    f"row {row_id} violates authorization safety boundary: "
                    f"{field}={actual!r}, expected={expected!r}"
                )

        # --------------------------------------------------------------
        # R4 semantic authority
        # --------------------------------------------------------------

        classification = clean(
            rr.get("Identity_Classification_R4")
        )

        identity_status = clean(
            rr.get("Identity_Status_R4")
        )

        observation_key = clean(
            rr.get("Observation_Key_R4")
        )

        if not observation_key:
            fail(f"row {row_id} has empty Observation_Key_R4")

        dimension_status = clean(
            rr.get("Semantic_Dimension_Status_R4")
        )

        # --------------------------------------------------------------
        # Semantic decision
        # --------------------------------------------------------------

        if (
            classification == "UNIQUE"
            and identity_status == "IDENTITY_READY"
        ):
            decision = "CANONICAL"
            write_action = "NO_WRITE_DESIGN_REVIEW"

        elif (
            classification == "EXACT_DUPLICATE"
            and identity_status == "DEDUPLICABLE"
        ):
            decision = "ALIAS_EXACT_DUPLICATE"
            write_action = "ALIAS_ONLY_NO_WRITE"

        elif (
            classification == "SEMANTICALLY_DISTINCT_CANDIDATES"
            and identity_status == "IDENTITY_READY_WITH_DIMENSION"
            and dimension_status == "RESOLVED"
        ):
            decision = "CANONICAL_WITH_DIMENSION"
            write_action = "NO_WRITE_DESIGN_REVIEW"

        elif identity_status == "BLOCKED_SEMANTIC_IDENTITY":
            decision = "BLOCKED_SEMANTIC_IDENTITY"
            write_action = "NO_WRITE"

        else:
            decision = "BLOCKED_REQUIRES_REVIEW"
            write_action = "NO_WRITE"

        reconciled.append(
            {
                "Authorization_Row": row_id,
                "SHA256": clean(ar.get("SHA256")),
                "Original_Identity": clean(ar.get("Original_Identity")),
                "Metric": clean(ar.get("Metric")),
                "Value": clean(ar.get("Value")),
                "Resolved_Unit": clean(ar.get("Resolved_Unit")),
                "Resolved_Period": clean(ar.get("Resolved_Period")),
                "Authorization_Metric_ID": clean(ar.get("Metric_ID")),
                "Authorization_Knowledge_Evidence_ID": clean(
                    ar.get("Knowledge_Evidence_ID")
                ),
                "R4_Metric_Evidence_ID": clean(
                    rr.get("Metric_Evidence_ID")
                ),
                "R4_Knowledge_Evidence_ID": clean(
                    rr.get("Knowledge_Evidence_ID")
                ),
                "Canonical_Ticker_R4": clean(
                    rr.get("Canonical_Ticker")
                ),
                "Observation_Key_R4": observation_key,
                "Context_Join_Key_R4": clean(
                    rr.get("Context_Join_Key_R4")
                ),
                "Semantic_Dimension_R4": clean(
                    rr.get("Semantic_Dimension_R4")
                ),
                "Semantic_Dimension_Status_R4": dimension_status,
                "Semantic_Dimension_Reason_R4": clean(
                    rr.get("Semantic_Dimension_Reason_R4")
                ),
                "Semantic_Local_Context_Hits_R4": clean(
                    rr.get("Semantic_Local_Context_Hits_R4")
                ),
                "Identity_Classification_R4": classification,
                "Identity_Status_R4": identity_status,
                "Canonical_Decision_R2": decision,
                "Write_Action_R2": write_action,
                "Metric_Persistence_Authorization": clean(
                    ar.get("Metric_Persistence_Authorization")
                ),
                "KnowledgeBridge_Write_Authorization": clean(
                    ar.get("KnowledgeBridge_Write_Authorization")
                ),
                "Vault_Write_Authorization": clean(
                    ar.get("Vault_Write_Authorization")
                ),
                "Explicit_Grant": clean(ar.get("Explicit_Grant")),
                "Execution_Status": clean(ar.get("Execution_Status")),
                "Vault_Modified": "FALSE",
            }
        )

    # ------------------------------------------------------------------
    # Canonical identity analysis
    # ------------------------------------------------------------------

    canonical_decisions = {
        "CANONICAL",
        "CANONICAL_WITH_DIMENSION",
    }

    canonical_rows = [
        row
        for row in reconciled
        if row["Canonical_Decision_R2"] in canonical_decisions
    ]

    canonical_identity_keys = {
        row["Observation_Key_R4"]
        for row in canonical_rows
    }

    alias_rows = [
        row
        for row in reconciled
        if row["Canonical_Decision_R2"] == "ALIAS_EXACT_DUPLICATE"
    ]

    alias_identity_keys = {
        row["Observation_Key_R4"]
        for row in alias_rows
    }

    blocked_rows = [
        row
        for row in reconciled
        if row["Canonical_Decision_R2"].startswith("BLOCKED_")
    ]

    # ------------------------------------------------------------------
    # Group observations
    # ------------------------------------------------------------------

    observation_groups = defaultdict(list)

    for row in reconciled:
        observation_groups[row["Observation_Key_R4"]].append(row)

    observation_group_sizes = {
        key: len(rows)
        for key, rows in observation_groups.items()
    }

    for row in reconciled:
        row["Observation_Group_Size_R2"] = str(
            observation_group_sizes[row["Observation_Key_R4"]]
        )

    # ------------------------------------------------------------------
    # Identity uniqueness
    # ------------------------------------------------------------------

    canonical_metric_ids = [
        row["R4_Metric_Evidence_ID"]
        for row in canonical_rows
    ]

    canonical_knowledge_ids = [
        row["R4_Knowledge_Evidence_ID"]
        for row in canonical_rows
    ]

    unique_r4_metric_ids = (
        len(canonical_metric_ids)
        == len(set(canonical_metric_ids))
    )

    unique_r4_knowledge_ids = (
        len(canonical_knowledge_ids)
        == len(set(canonical_knowledge_ids))
    )

    # ------------------------------------------------------------------
    # Expected current R4 architecture
    # ------------------------------------------------------------------

    unique_count = sum(
        1
        for row in reconciled
        if row["Identity_Classification_R4"] == "UNIQUE"
    )

    exact_duplicate_count = sum(
        1
        for row in reconciled
        if row["Identity_Classification_R4"] == "EXACT_DUPLICATE"
    )

    semantic_candidate_count = sum(
        1
        for row in reconciled
        if row["Identity_Classification_R4"]
        == "SEMANTICALLY_DISTINCT_CANDIDATES"
    )

    blocked_semantic_count = sum(
        1
        for row in reconciled
        if row["Canonical_Decision_R2"]
        == "BLOCKED_SEMANTIC_IDENTITY"
    )

    dimension_identity_keys = {
        row["Observation_Key_R4"]
        for row in reconciled
        if row["Canonical_Decision_R2"]
        == "CANONICAL_WITH_DIMENSION"
    }

    exact_duplicate_identity_keys = {
        row["Observation_Key_R4"]
        for row in reconciled
        if row["Identity_Classification_R4"]
        == "EXACT_DUPLICATE"
    }

    canonical_identity_count = len(canonical_identity_keys)

    # ------------------------------------------------------------------
    # Structural assertions
    # ------------------------------------------------------------------

    if len(reconciled) != 31:
        fail(f"reconciled rows expected 31, found {len(reconciled)}")

    if unique_count != 26:
        fail(f"expected 26 UNIQUE rows, found {unique_count}")

    if exact_duplicate_count != 2:
        fail(
            f"expected 2 EXACT_DUPLICATE rows, "
            f"found {exact_duplicate_count}"
        )

    if semantic_candidate_count != 3:
        fail(
            "expected 3 SEMANTICALLY_DISTINCT_CANDIDATES rows, "
            f"found {semantic_candidate_count}"
        )

    if len(exact_duplicate_identity_keys) != 1:
        fail(
            "expected exactly one exact-duplicate identity group, "
            f"found {len(exact_duplicate_identity_keys)}"
        )

    if len(dimension_identity_keys) != 1:
        fail(
            "expected exactly one dimension-resolved canonical identity, "
            f"found {len(dimension_identity_keys)}"
        )

    if blocked_semantic_count != 1:
        fail(
            "expected exactly one BLOCKED_SEMANTIC_IDENTITY row, "
            f"found {blocked_semantic_count}"
        )

    distinct_observation_key_count = len(
        {
            row["Observation_Key_R4"]
            for row in reconciled
        }
    )

    blocked_observation_keys = {
        row["Observation_Key_R4"]
        for row in blocked_rows
    }

    if distinct_observation_key_count != 29:
        fail(
            f"expected 29 distinct Observation_Key_R4 identities, "
            f"found {distinct_observation_key_count}"
        )

    if canonical_identity_count != 27:
        fail(
            f"expected 27 canonical identities, "
            f"found {canonical_identity_count}"
        )

    if len(blocked_observation_keys) != 1:
        fail(
            f"expected exactly one blocked semantic identity key, "
            f"found {len(blocked_observation_keys)}"
        )

    if (
        canonical_identity_count
        + len(exact_duplicate_identity_keys)
        + len(blocked_observation_keys)
        != distinct_observation_key_count
    ):
        fail(
            "Observation_Key_R4 identity accounting mismatch: "
            f"canonical={canonical_identity_count}, "
            f"exact_duplicate_groups={len(exact_duplicate_identity_keys)}, "
            f"blocked={len(blocked_observation_keys)}, "
            f"distinct={distinct_observation_key_count}"
        )

    if not unique_r4_metric_ids:
        fail("R4 Metric_Evidence_ID is not unique across canonical identities")

    if not unique_r4_knowledge_ids:
        fail(
            "R4 Knowledge_Evidence_ID is not unique across canonical identities"
        )

    # ------------------------------------------------------------------
    # Safety assertions
    # ------------------------------------------------------------------

    if any(
        row["Metric_Persistence_Authorization"] != "NOT_GRANTED"
        for row in reconciled
    ):
        fail("persistence authorization changed")

    if any(
        row["KnowledgeBridge_Write_Authorization"] != "NOT_GRANTED"
        for row in reconciled
    ):
        fail("KnowledgeBridge authorization changed")

    if any(
        row["Vault_Write_Authorization"] != "NOT_GRANTED"
        for row in reconciled
    ):
        fail("Vault authorization changed")

    if any(
        row["Explicit_Grant"] != "NOT_GRANTED"
        for row in reconciled
    ):
        fail("explicit grant changed")

    if any(
        row["Execution_Status"] != "NOT_AUTHORIZED"
        for row in reconciled
    ):
        fail("execution status changed")

    if any(
        row["Vault_Modified"] != "FALSE"
        for row in reconciled
    ):
        fail("Vault_Modified is not FALSE")

    # ------------------------------------------------------------------
    # Final status
    #
    # A blocked semantic row is expected and intentionally prevents
    # authorization readiness.
    # ------------------------------------------------------------------

    final_status = (
        "BLOCKED_REQUIRES_SEMANTIC_REVIEW"
        if blocked_rows
        else "READY_FOR_AUTHORIZATION_RECONCILIATION_REVIEW"
    )

    decision_counts = Counter(
        row["Canonical_Decision_R2"]
        for row in reconciled
    )

    classification_counts = Counter(
        row["Identity_Classification_R4"]
        for row in reconciled
    )

    # ------------------------------------------------------------------
    # Output CSV
    # ------------------------------------------------------------------

    with OUT_CSV.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=list(reconciled[0].keys()),
        )
        writer.writeheader()
        writer.writerows(reconciled)

    # ------------------------------------------------------------------
    # Output JSON
    # ------------------------------------------------------------------

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "stage": "06.31.2",
        "revision": "R2",
        "status": "PASS",
        "final_status": final_status,
        "read_only": True,
        "fail_closed": True,
        "authorization_rows": len(auth),
        "r4_rows": len(r4),
        "canonical_identity_count": canonical_identity_count,
        "distinct_observation_key_count": distinct_observation_key_count,
        "blocked_observation_key_count": len(blocked_observation_keys),
        "unique_rows": unique_count,
        "exact_duplicate_rows": exact_duplicate_count,
        "exact_duplicate_identity_groups": len(
            exact_duplicate_identity_keys
        ),
        "dimension_resolved_rows": len(
            [
                row
                for row in reconciled
                if row["Canonical_Decision_R2"]
                == "CANONICAL_WITH_DIMENSION"
            ]
        ),
        "dimension_resolved_identity_groups": len(
            dimension_identity_keys
        ),
        "semantic_candidate_rows": semantic_candidate_count,
        "blocked_semantic_rows": blocked_semantic_count,
        "blocked_rows_total": len(blocked_rows),
        "decision_counts": dict(decision_counts),
        "r4_classification_counts": dict(classification_counts),
        "unique_r4_metric_ids": unique_r4_metric_ids,
        "unique_r4_knowledge_ids": unique_r4_knowledge_ids,
        "authorization_granted": False,
        "metric_persistence_authorization": "NOT_GRANTED",
        "knowledgebridge_write_authorization": "NOT_GRANTED",
        "vault_write_authorization": "NOT_GRANTED",
        "execution_status": "NOT_AUTHORIZED",
        "vault_changed": False,
        "authorization_manifest_sha256": file_sha256(AUTH),
        "r4_sha256": file_sha256(R4),
    }

    OUT_JSON.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # ------------------------------------------------------------------
    # Output Markdown
    # ------------------------------------------------------------------

    md = f"""# D-OBSIDIAN-06.31.2 — Scope Dedup & Authorization Reconciliation R2

READ-ONLY / FAIL-CLOSED / NO AUTHORIZATION GRANT / NO VAULT WRITE

## Result

- Authorization rows: **{len(auth)}**
- R4 semantic rows: **{len(r4)}**
- Canonical identities: **{canonical_identity_count}**
- UNIQUE rows: **{unique_count}**
- EXACT_DUPLICATE rows: **{exact_duplicate_count}**
- EXACT_DUPLICATE identity groups: **{len(exact_duplicate_identity_keys)}**
- Dimension-resolved rows: **{len([row for row in reconciled if row["Canonical_Decision_R2"] == "CANONICAL_WITH_DIMENSION"])}**
- Dimension-resolved identity groups: **{len(dimension_identity_keys)}**
- SEMANTICALLY_DISTINCT_CANDIDATES: **{semantic_candidate_count}**
- BLOCKED_SEMANTIC_IDENTITY: **{blocked_semantic_count}**
- Total blocked rows: **{len(blocked_rows)}**

## Canonical identity derivation

The canonical semantic identity is determined by R4 `Observation_Key_R4`.

The authorization manifest `Metric_ID` and `Knowledge_Evidence_ID`
are preserved as authorization-source identifiers and are not treated
as the final semantic identity.

### Canonical calculation

```text
26 UNIQUE rows
+ 2 dimension-resolved rows
= 28 canonical rows

Canonical semantic identities:
26 UNIQUE identities
+ 1 dimension-resolved identity
= 27 canonical identities

Identity accounting:
27 canonical identities
+ 1 EXACT_DUPLICATE identity group
+ 1 BLOCKED semantic identity
= 29 distinct Observation_Key_R4 identities
```

## Decision counts

```text
{json.dumps(dict(decision_counts), indent=2, ensure_ascii=False)}
```

## R4 classification counts

```text
{json.dumps(dict(classification_counts), indent=2, ensure_ascii=False)}
```

## Safety

- Authorization grant: **False**
- Metric persistence authorization: **NOT_GRANTED**
- KnowledgeBridge write authorization: **NOT_GRANTED**
- Vault write authorization: **NOT_GRANTED**
- Execution status: **NOT_AUTHORIZED**
- Vault changed: **False**
- Read-only: **True**
- Fail-closed: **True**

## Final status

**{final_status}**

## Blocked rows

```text
{json.dumps(blocked_rows, indent=2, ensure_ascii=False)}
```

## Integrity

- Authorization manifest SHA256: `{file_sha256(AUTH)}`
- R4 semantic resolution SHA256: `{file_sha256(R4)}`

No authorization was granted and no persistence or Vault mutation
was executed by this reconciliation stage.
"""

    OUT_MD.write_text(
        md,
        encoding="utf-8",
    )

    print("=" * 100)
    print("D-OBSIDIAN-06.31.2 - 0695.7 SCOPE DEDUP & AUTH RECONCILIATION R2")
    print("=" * 100)
    print(f"Authorization rows          : {len(auth)}")
    print(f"R4 semantic rows            : {len(r4)}")
    print(f"Canonical identities        : {canonical_identity_count}")
    print(f"Distinct Observation Keys   : {distinct_observation_key_count}")
    print(f"Blocked identity keys       : {len(blocked_observation_keys)}")
    print(f"UNIQUE rows                 : {unique_count}")
    print(f"EXACT_DUPLICATE rows        : {exact_duplicate_count}")
    print(f"Semantic candidate rows     : {semantic_candidate_count}")
    print(f"Blocked semantic rows       : {blocked_semantic_count}")
    print(f"Total blocked rows          : {len(blocked_rows)}")
    print(f"Final status                : {final_status}")
    print("-" * 100)
    print(f"CSV                         : {OUT_CSV}")
    print(f"Markdown                    : {OUT_MD}")
    print(f"JSON                        : {OUT_JSON}")
    print("-" * 100)
    print("AUTHORIZATION GRANTED       : False")
    print("VAULT CHANGED               : False")
    print("=" * 100)


if __name__ == "__main__":
    raise SystemExit(main())
