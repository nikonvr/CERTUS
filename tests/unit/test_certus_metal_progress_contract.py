"""Contract tests for the shared METAL progress event."""

from __future__ import annotations

from certus.metal.certus_metal_common import (
    METAL_GLOBAL_STATUS,
    MetalProgressEvent,
    build_metal_progress_event,
)


def test_build_metal_progress_event_clamps_and_normalizes_fields() -> None:
    event = build_metal_progress_event(
        phase="global_opt",
        progress_pct=155,
        message="Running",
        iteration=-3,
        max_iteration=-10,
        evaluation_count=-2,
        best_cost=0.123,
        elapsed_s=-4.2,
        mode=METAL_GLOBAL_STATUS,
    )

    assert isinstance(event, MetalProgressEvent)
    assert event.phase == "global_opt"
    assert event.progress_pct == 100
    assert event.iteration == 0
    assert event.max_iteration == 0
    assert event.evaluation_count == 0
    assert event.best_cost == 0.123
    assert event.elapsed_s == 0.0
    assert event.mode == METAL_GLOBAL_STATUS


def test_build_metal_progress_event_keeps_message_and_defaults() -> None:
    event = build_metal_progress_event(phase="beam", progress_pct=12, message="Beam stage")

    assert event.phase == "beam"
    assert event.progress_pct == 12
    assert event.message == "Beam stage"
    assert event.iteration == 0
    assert event.max_iteration == 0
    assert event.evaluation_count == 0
    assert event.mode == METAL_GLOBAL_STATUS
