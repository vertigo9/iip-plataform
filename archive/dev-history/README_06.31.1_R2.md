# D-OBSIDIAN-06.31.1 R2

This is a fail-closed reconciliation gate.

It maps the 31-row explicit authorization scope against the proven canonical
0695 generic persistence evidence using the exact key:

`Row + SHA256 + Metric`

Canonical identity fields are copied only when present in the canonical
source. Rows whose canonical source is BLOCKED or not uniquely matched remain
BLOCKED.

The gate NEVER grants persistence authorization and NEVER writes Vault.

Run first:

```powershell
python .\RUN-D-OBSIDIAN-06.31.1_R2_0695_7_IDENTITY_RECONCILIATION_GATE.py
```

If it stops, inspect the blocked rows; do not run 06.32.
