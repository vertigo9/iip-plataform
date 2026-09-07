"""Deep portfolio integration planning with enablement-safe deduplication."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntegrationNode:
    name: str
    enabled: bool = True


@dataclass(frozen=True)
class IntegrationPlan:
    nodes: tuple[IntegrationNode, ...]

    @property
    def ready(self) -> bool:
        return bool(self.nodes) and all(node.enabled for node in self.nodes)


def plan(nodes: tuple[IntegrationNode, ...]) -> IntegrationPlan:
    """Deduplicate nodes without allowing a duplicate disabled record to
    deactivate an already-enabled integration node.

    Policy:
    - same-name nodes are merged;
    - enabled wins over disabled;
    - final order is deterministic by name.
    """
    unique: dict[str, IntegrationNode] = {}
    for node in nodes:
        current = unique.get(node.name)
        if current is None:
            unique[node.name] = node
            continue
        if node.enabled or not current.enabled:
            unique[node.name] = IntegrationNode(node.name, node.enabled)
    return IntegrationPlan(tuple(sorted(unique.values(), key=lambda item: item.name)))
