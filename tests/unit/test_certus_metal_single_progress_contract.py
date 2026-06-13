"""Contract test for METAL SINGLE progress normalization."""

from __future__ import annotations

from certus.metal.certus_metal_common import normalize_metal_progress_payload


def test_single_progress_payload_normalization() -> None:
    payload = normalize_metal_progress_payload(
        {
            "iteration": 5,
            "mse": 0.25,
            "params": [1.2, 2.3, 3.4, 4.5],
            "progress_pct": 87,
            "mode": "global",
            "best_cost": 0.2,
            "evaluation_count": 123,
            "elapsed_s": 9.7,
            "max_iteration": 50,
        }
    )

    assert payload["iteration"] == 5
    assert payload["progress_pct"] == 87
    assert payload["best_cost"] == 0.2
    assert payload["evaluation_count"] == 123
    assert payload["elapsed_s"] == 9.7
    assert payload["max_iteration"] == 50
    assert payload["mode"] == "global"
