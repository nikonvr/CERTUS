"""
CERTUS Domain - Event Bus (Simple Implementation)

Event bus pour domain events (event sourcing pattern).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List
import time


@dataclass(frozen=True)
class DomainEvent:
    """
    Domain event immutable.

    Examples:
        >>> event = DomainEvent(
        ...     event_type="LayerAdded",
        ...     aggregate_id="stack-123",
        ...     payload={"material": "TiO2", "position": 0}
        ... )
    """

    event_type: str
    aggregate_id: str
    payload: dict
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: f"evt-{int(time.time() * 1000)}")

    def __post_init__(self):
        """Validation."""
        if not self.event_type:
            raise ValueError("event_type cannot be empty")
        if not self.aggregate_id:
            raise ValueError("aggregate_id cannot be empty")


class EventBus:
    """
    Event bus simple pour domain events.

    Permet publish/subscribe pattern pour découpler le domain.

    Examples:
        >>> bus = EventBus()
        >>> bus.subscribe("LayerAdded", lambda e: print(f"Layer added: {e.payload}"))
        >>> event = DomainEvent("LayerAdded", "stack-1", {"material": "TiO2"})
        >>> bus.publish(event)
    """

    def __init__(self):
        self._handlers: Dict[str, List[Callable[[DomainEvent], None]]] = {}
        self._store: List[DomainEvent] = []

    def subscribe(self, event_type: str, handler: Callable[[DomainEvent], None]) -> None:
        """
        Subscribe handler to event type.

        Args:
            event_type: Type d'event (ex: "LayerAdded")
            handler: Callback appelé lors de l'event
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent) -> None:
        """
        Publish event to all subscribers.

        Args:
            event: Domain event à publier
        """
        # Store event (event sourcing)
        self._store.append(event)

        # Notify handlers
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                # Log error but don't crash
                print(f"Error in event handler: {e}")

    def replay(self, aggregate_id: str) -> List[DomainEvent]:
        """
        Replay all events for aggregate (event sourcing).

        Args:
            aggregate_id: ID de l'aggregate

        Returns:
            Liste des events pour cet aggregate
        """
        return [e for e in self._store if e.aggregate_id == aggregate_id]

    def get_all_events(self) -> List[DomainEvent]:
        """
        Get all events in order.

        Returns:
            Liste complète des events
        """
        return self._store.copy()

    def clear(self) -> None:
        """Clear all events and handlers (for testing)."""
        self._store.clear()
        self._handlers.clear()

    def event_count(self) -> int:
        """Number of events in store."""
        return len(self._store)


# Global event bus instance (singleton pattern)
_global_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """
    Get global event bus instance (singleton).

    Returns:
        Global EventBus instance
    """
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus()
    return _global_bus
