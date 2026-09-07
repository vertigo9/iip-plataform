"""Event-chain primitives used by disclosure intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EventNode:
    event_id: str
    ticker: str
    event_type: str
    occurred_at: datetime


@dataclass(frozen=True)
class EventEdge:
    source_event_id: str
    target_event_id: str
    relation: str


@dataclass(frozen=True)
class EventChain:
    nodes: tuple[EventNode, ...] = ()
    edges: tuple[EventEdge, ...] = ()

    def add_node(self, node: EventNode) -> EventChain:
        if node.event_id in {n.event_id for n in self.nodes}:
            return self
        return EventChain(self.nodes + (node,), self.edges)

    def add_edge(self, edge: EventEdge) -> EventChain:
        return EventChain(self.nodes, self.edges + (edge,))
