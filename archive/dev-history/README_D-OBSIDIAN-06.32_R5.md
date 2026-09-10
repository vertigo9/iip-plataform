# D-OBSIDIAN-06.32 — Controlled Persistence Executor R5

## Root cause fixed

R4 correctly imported `re` and contained the fallback to derive the ticker
from an authorized `Metric_ID`. However, execution called `build_evidence(row)`
using only the execution-contract row.

The current execution contract can omit identity fields that are already
present in the explicit authorization manifest. Therefore the fallback could
not see the authorized `Metric_ID`, and execution still failed with:

`ValueError: missing required identity fields: ticker`

## R5 correction

For every NEW target, R5 constructs the evidence identity from the
**authorized authorization row as the identity authority**, then overlays
non-empty execution-contract fields. `Metric_ID` and
`Knowledge_Evidence_ID` are explicitly retained from authorization when absent
from the contract.

No identity is invented or manually assigned. The official
`metric_evidence_id()` and `knowledge_evidence_id()` functions still
recalculate and must exactly match the authorized IDs.

Existing identical targets remain NO-OP. Conflicts remain fail-closed.
No Vault write occurs during dry-run.

## Validation

First run:

```powershell
python .\RUN-D-OBSIDIAN-06.32_0695_7_CONTROLLED_PERSISTENCE_EXECUTOR_R3.py
```

Expected:
- authorization 31
- contract 31
- scope exact 31
- existing identical 28
- new 3
- conflicts 0
- DRY_RUN_PASS

Only after that:

```powershell
python .\RUN-D-OBSIDIAN-06.32_0695_7_CONTROLLED_PERSISTENCE_EXECUTOR_R3.py --execute
```
