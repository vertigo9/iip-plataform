# Knowledge Layer v1.3

## Guarantees
1. Historical decision IDs are append-only.
2. Decisions cannot be persisted with missing evidence references.
3. Current state is a projection; snapshots remain historical.
4. Context assembly reads decision history, evidence, portfolio snapshots and exposures.
5. Event adapters map versioned IIP contracts to knowledge records.
6. Redundancy detection aggregates economic factors across assets.

## Event contracts
- `atlas.document.processed.v1`
- `atlas.event.materiality_evaluated.v1`
- `iip.decision.created.v1`
- `iip.portfolio.snapshot_created.v1`
- `knowledge.sync.completed.v1`
- `knowledge.sync.failed.v1`
- `knowledge.redundancy.detected.v1`

## Failure policy
Knowledge projection failure must be visible. It must not silently overwrite an existing record or silently drop a decision.
