# Obsidian ↔ IIP — Setup Windows

## 1. Vault
Open **only** the `vault` directory as an Obsidian Vault.

Example:

`C:\IIP\knowledge-vault`

## 2. Configure IIP
From PowerShell, in the IIP project:

```powershell
.\scripts\setup_obsidian.ps1 -VaultPath "C:\IIP\knowledge-vault"
```

This creates the expected folders and writes `IIP_OBSIDIAN_VAULT` to `.env`.

## 3. Validate

```powershell
python -m pytest tests/knowledge -q
python -m compileall src
python -m iip.cli.main knowledge-status
```

## 4. First real round-trip
Use an actual IIP event to persist an evidence record and decision for an existing ticker. The recommended regression fixture is PCIP11 because it exercises evidence, decision history, portfolio context and exposure links.

Do not treat the test fixture as financial evidence. Replace it with the actual Atlas document event before using the record for investment decisions.

## 5. Architecture
- PostgreSQL: operational source of truth when connected.
- Obsidian: knowledge/decision projection and human-readable graph.
- Git: version history.
- Atlas: detect/validate/classify/process/materiality/sync/audit.
- Research/Portfolio: analysis, valuation, thesis and allocation decisions.
