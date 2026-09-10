# D-OBSIDIAN-06.31 — 0695.7 Explicit Persistence Authorization R1

This package introduces the explicit authorization boundary requested after the
06.30 `EXECUTION_NOT_AUTHORIZED` fail-closed result.

The script:
- validates the existing 06.22 execution contract;
- validates the 06.24 target binding;
- requires the exact 31-record scope;
- requires unique identity and exact scope match;
- requires targets under `vault/04_Evidence`;
- creates an auditable authorization manifest with `GRANTED`;
- does NOT write the Vault or execute persistence.

After a PASS, the existing controlled executor may be rerun. It must consume
the authorization artifact and remain fail-closed on scope, conflict, collision,
or overwrite violations.

Run from the repository root:

    python .\RUN_D-OBSIDIAN-06.31_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION.py
