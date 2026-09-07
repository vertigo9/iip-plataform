"""IIP Event Bus — async pub/sub for module communication."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

EventType = Any
EventHandler = Callable[[Any], None]


@dataclass
class Event:
    type: str
    payload: dict[str, Any]
    timestamp: datetime | None = None
    source: str = "unknown"

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(UTC)


class EventBus:
    _subscribers: dict[str, list[EventHandler]] = defaultdict(list)
    _lock = asyncio.Lock()

    @classmethod
    def subscribe(cls, event_type: str, handler: EventHandler) -> None:
        cls._subscribers[event_type].append(handler)

    @classmethod
    async def publish(cls, event: Event) -> None:
        async with cls._lock:
            handlers = cls._subscribers.get(event.type, [])
        awaitables: list[Any] = []
        for handler in handlers:
            result = handler(event)
            if asyncio.iscoroutine(result):
                awaitables.append(result)
        if awaitables:
            await asyncio.gather(*awaitables, return_exceptions=True)

    @classmethod
    def unsubscribe(cls, event_type: str, handler: EventHandler) -> None:
        if event_type in cls._subscribers:
            try:
                cls._subscribers[event_type].remove(handler)
            except ValueError:
                pass

    @classmethod
    def clear(cls) -> None:
        cls._subscribers.clear()

    @classmethod
    def subscriber_count(cls, event_type: str) -> int:
        return len(cls._subscribers.get(event_type, []))
