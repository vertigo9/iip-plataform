---
module: credit_counterparty_mapping
version: 0.1
status: active
as_of: 2026-07-31
generated_at: 2026-09-02 16:19:14
---

# 0690 - Credit Counterparty Mapping

## Purpose

Map direct and economic credit overlaps between PCIP11 and priority credit funds.

## Scope

- PCIP11
- VGIP11
- AFHI11
- HGCR11
- BTCI11
- MANA11

MANA11 remains GAP because a sufficiently detailed July-2026 credit composition source was not located in the current library search.
No overlap is asserted for MANA11.

## Direct credit overlaps

### Matarazzo

- Funds: PCIP11 x VGIP11
- Relation: Same CRI instruments
- Instrument: Matarazzo 451S / 22C0509668; Matarazzo 545S / 23J2162618
- PCIP11: 92.7m combined
- VGIP11: 91.0m in 451S; 52.0m in 545S
- Evidence: HIGH
- Source: PCIP11 Jul-2026; VGIP11 Jul-2026
- Note: Direct instrument overlap confirmed.

### Localfrio

- Funds: PCIP11 x VGIP11
- Relation: Same CRI instrument
- Instrument: CRI Localfrio / 19K0981679
- PCIP11: 5.4m / 0.3% PL
- VGIP11: 1.85m / 0.17% PL
- Evidence: HIGH
- Source: PCIP11 Jul-2026; VGIP11 Jul-2026
- Note: Same code identified.

### GPA / RBVA

- Funds: PCIP11 x HGCR11
- Relation: Same CRI instrument
- Instrument: GPA RBVA / 20L0687133
- PCIP11: 2.9m / 0.2% PL
- HGCR11: 9.8m / 0.7% PL
- Evidence: HIGH
- Source: PCIP11 Jul-2026; HGCR11 Jun-2026
- Note: Same operation code.

### GPA / RBVA

- Funds: PCIP11 x AFHI11
- Relation: Same CRI instrument
- Instrument: RBVA GPA / 20L0687133
- PCIP11: 2.9m / 0.2% PL
- AFHI11: 5.0m allocated position
- Evidence: HIGH
- Source: PCIP11 Jul-2026; AFHI11 Jun-2026
- Note: Same operation code.

### Rede D'Or

- Funds: PCIP11 x AFHI11
- Relation: Same CRI instrument
- Instrument: Rede D'Or / 19H0235501
- PCIP11: 6.6m / 0.4% PL
- AFHI11: 1.01m / 0.20% PL
- Evidence: HIGH
- Source: PCIP11 Jul-2026; AFHI11 Jun-2026
- Note: Same operation code.

## Economic counterparty overlaps

### MRV

- Funds: PCIP11 x BTCI11
- Relation: Same economic counterparty; different instruments
- Instrument: PCIP11 26C4863993; BTCI11 25F1669254
- PCIP11: 43.4m / 2.8% PL
- BTCI11: 44.5m MTM / 4.4% PL
- Evidence: MEDIUM-HIGH
- Source: PCIP11 Jul-2026; BTCI11 Jul-2026
- Note: Named MRV Flex operation in both, but codes differ.

### Assai

- Funds: PCIP11 x AFHI11
- Relation: Same economic counterparty; different operations
- Instrument: Multiple retail CRIs
- PCIP11: multiple Assai-linked positions
- AFHI11: Assai GIC 4.36m plus RBVA GPA exposure
- Evidence: MEDIUM
- Source: PCIP11 Jul-2026; AFHI11 Jun-2026
- Note: Economic overlap only.

### Grupo Mateus

- Funds: PCIP11 x AFHI11
- Relation: Same economic counterparty; different operations
- Instrument: Mateus-linked CRIs
- PCIP11: multiple Mateus-linked positions
- AFHI11: TRX Mateus 2.84m plus Mateus exposure
- Evidence: MEDIUM
- Source: PCIP11 Jul-2026; AFHI11 Jun-2026
- Note: Economic overlap only.

## Rules

1. Same code or ISIN = direct instrument overlap.
2. Same named obligor with different codes = economic counterparty overlap.
3. Same sector or tenant without identified obligor = adjacency only.
4. Missing source = GAP; absence is not treated as zero exposure.

## Summary

- Direct overlaps identified: 5
- Economic counterparty overlaps identified: 3
- MANA11: GAP
- Priority direct overlaps: Matarazzo, Localfrio, GPA/RBVA and Rede D'Or.

## Status

0690 COMPLETED - initial evidence layer

