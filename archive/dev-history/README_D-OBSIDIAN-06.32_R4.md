# D-OBSIDIAN-06.32 — Controlled Persistence Executor R4

R4 is a fail-closed correction of R3.

## Correction
R3 had a preparation-time defect: `build_evidence()` calls `re.match()` to
derive the canonical ticker from the already-authorized `Metric_ID`, but
`re` was not imported. This caused:

`NameError: name 're' is not defined`

R4 adds only the missing standard-library import. No persistence logic,
authorization scope, target binding, idempotency rule, or overwrite behavior
was changed.

## Required validation sequence

Run dry-run first:

```powershell
python .\RUN-D-OBSIDIAN-06.32_0695_7_CONTROLLED_PERSISTENCE_EXECUTOR_R3.py
```

Expected structural state from the prior R3 run:

- Authorization: 31
- Contract: 31
- Scope exact match: 31
- Existing identical targets: 28
- New targets: 3
- Conflicting targets: 0
- No Vault writes during dry-run

Only after `DRY_RUN_PASS`, run:

```powershell
python .\RUN-D-OBSIDIAN-06.32_0695_7_CONTROLLED_PERSISTENCE_EXECUTOR_R3.py --execute
```

## Safety
- Conflicting targets block execution.
- Existing identical targets are NO-OP.
- New records are prepared before the first write.
- A target returned by the bridge must exactly match the authorized
  `Target_Relative`; otherwise execution stops.
- Writes are one record at a time.
- No destructive rollback is performed.
- The correction itself does not write to Vault.
