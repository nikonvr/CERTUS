"""
Property-Based Tests for Event Bus

Tests event sourcing pattern avec Hypothesis.
"""

import pytest
from hypothesis import given, strategies as st, settings

from certus.domain.optical.events import DomainEvent, EventBus, get_event_bus


# ============================================================================
# DomainEvent Tests
# ============================================================================


@given(
    event_type=st.text(min_size=1, max_size=50),
    aggregate_id=st.text(min_size=1, max_size=50),
)
@settings(max_examples=100, deadline=1000)
def test_domain_event_creation(event_type, aggregate_id):
    """Property: Valid inputs create valid DomainEvent."""
    event = DomainEvent(event_type, aggregate_id, {})

    assert event.event_type == event_type
    assert event.aggregate_id == aggregate_id
    assert isinstance(event.payload, dict)
    assert event.timestamp > 0
    assert event.event_id.startswith("evt-")


def test_domain_event_immutable():
    """Property: DomainEvent is immutable (frozen)."""
    event = DomainEvent("Test", "agg-1", {"key": "value"})

    with pytest.raises(Exception):  # dataclass frozen
        event.event_type = "Modified"  # type: ignore


def test_domain_event_rejects_empty_type():
    """Property: Empty event_type must be rejected."""
    with pytest.raises(ValueError, match="event_type cannot be empty"):
        DomainEvent("", "agg-1", {})


def test_domain_event_rejects_empty_aggregate_id():
    """Property: Empty aggregate_id must be rejected."""
    with pytest.raises(ValueError, match="aggregate_id cannot be empty"):
        DomainEvent("Test", "", {})


# ============================================================================
# EventBus Tests
# ============================================================================


@given(n_events=st.integers(min_value=1, max_value=50))
@settings(max_examples=50, deadline=2000)
def test_event_bus_stores_events(n_events):
    """Property: EventBus stores all published events."""
    bus = EventBus()

    for i in range(n_events):
        event = DomainEvent(f"Event{i}", f"agg-{i}", {"index": i})
        bus.publish(event)

    assert bus.event_count() == n_events
    assert len(bus.get_all_events()) == n_events


@given(n_events=st.integers(min_value=1, max_value=30))
@settings(max_examples=50, deadline=2000)
def test_event_bus_notifies_subscribers(n_events):
    """Property: EventBus notifies all subscribers."""
    bus = EventBus()

    # Track notifications
    notifications = []

    def handler(event: DomainEvent):
        notifications.append(event.event_type)

    bus.subscribe("TestEvent", handler)

    # Publish events
    for i in range(n_events):
        event = DomainEvent("TestEvent", f"agg-{i}", {})
        bus.publish(event)

    assert len(notifications) == n_events


@given(
    aggregate_id=st.text(min_size=1, max_size=20),
    n_events=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=50, deadline=2000)
def test_event_bus_replay(aggregate_id, n_events):
    """Property: Replay returns all events for aggregate."""
    bus = EventBus()

    # Publish events for specific aggregate
    for i in range(n_events):
        event = DomainEvent(f"Event{i}", aggregate_id, {"index": i})
        bus.publish(event)

    # Publish events for other aggregates
    for i in range(5):
        event = DomainEvent("OtherEvent", f"other-{i}", {})
        bus.publish(event)

    # Replay
    replayed = bus.replay(aggregate_id)

    assert len(replayed) == n_events
    assert all(e.aggregate_id == aggregate_id for e in replayed)


def test_event_bus_multiple_handlers():
    """Property: Multiple handlers can subscribe to same event."""
    bus = EventBus()

    calls = {"handler1": 0, "handler2": 0}

    def handler1(event: DomainEvent):
        calls["handler1"] += 1

    def handler2(event: DomainEvent):
        calls["handler2"] += 1

    bus.subscribe("Test", handler1)
    bus.subscribe("Test", handler2)

    event = DomainEvent("Test", "agg-1", {})
    bus.publish(event)

    assert calls["handler1"] == 1
    assert calls["handler2"] == 1


def test_event_bus_singleton():
    """Property: get_event_bus() returns same instance."""
    bus1 = get_event_bus()
    bus2 = get_event_bus()

    assert bus1 is bus2


def test_event_bus_clear():
    """Property: clear() removes all events and handlers."""
    bus = EventBus()

    bus.subscribe("Test", lambda e: None)
    bus.publish(DomainEvent("Test", "agg-1", {}))

    assert bus.event_count() > 0

    bus.clear()

    assert bus.event_count() == 0
    assert len(bus.get_all_events()) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])
