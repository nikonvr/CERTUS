"""Contract test for METAL BILAYER progress normalization."""

from __future__ import annotations

from certus.metal.certus_metal_common import normalize_metal_progress_payload


def test_bilayer_progress_payload_normalization() -> None:
    payload = normalize_metal_progress_payload(
        {
            "iteration": 8,
            "mse": 0.49,
            "params": [1.2, 2.3, 3.4, 4.5],
            "progress_pct": 55,
            "mode": "global",
            "best_cost": 0.4,
            "evaluation_count": 321,
            "elapsed_s": 4.5,
            "max_iteration": 75,
        }
    )

    assert payload["iteration"] == 8
    assert payload["progress_pct"] == 55
    assert payload["best_cost"] == 0.4
    assert payload["evaluation_count"] == 321
    assert payload["elapsed_s"] == 4.5
    assert payload["max_iteration"] == 75
    assert payload["mode"] == "global"
