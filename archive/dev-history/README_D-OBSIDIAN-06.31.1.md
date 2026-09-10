# D-OBSIDIAN-06.31.1 — Authorization Identity Reconciliation

## Root cause

The current `PCIP11_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION_R2_1.csv`
does not contain `Metric_ID`, `Knowledge_Evidence_ID`, `Ticker`, or the other
canonical identity columns. This is confirmed by the local inspection output.

Therefore the 06.32 executor cannot reconstruct an authorized identity from
the authorization artifact.

## Corrective boundary

Do NOT fix this in the executor by guessing `PCIP11`, parsing target filenames,
or bypassing authorization.

R3 is rebuilt from:
- existing R2.1 authorization: policy, target and authorization decisions;
- `PCIP11_0695_7_PERSISTENCE_CONTRACT_R4.csv`: canonical identity authority.

The source authorization file is not modified. Vault is not touched.

Run:

```powershell
python .\RUN-D-OBSIDIAN-06.31.1_0695_7_AUTHORIZATION_IDENTITY_RECONCILIATION.py
```

Only if it reports all PASS should the resulting R3 authorization artifact
be used as input to a new explicit authorization gate. The 06.32 executor
must not be run until that gate has revalidated and authorized the corrected
artifact.
