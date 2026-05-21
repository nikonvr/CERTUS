"""Unit tests for CERTUS STRAT headless service boundaries."""

from __future__ import annotations

import numpy as np
import pytest

from certus_strat_service import (
    StratPayloadParts,
    StratStrategyService,
    generate_noise_array,
    wavelength_to_index,
)


@pytest.mark.unit
def test_validate_payload_returns_normalized_copy() -> None:
    service = StratStrategyService(runner=lambda cfg: cfg)
    payload = {
        "step": "0",
        "params": {"scan_wl_min": 400, "scan_wl_max": 700},
        "opti_results": {"ok": True},
    }

    normalized = service.validate_payload(payload)

    assert normalized == {
        "step": 0,
        "params": {"scan_wl_min": 400, "scan_wl_max": 700},
        "opti_results": {"ok": True},
    }
    assert normalized["params"] is not payload["params"]
    assert normalized["opti_results"] is not payload["opti_results"]


@pytest.mark.unit
@pytest.mark.parametrize(
    "payload, message",
    [
        ([], "payload must be a mapping"),
        ({"step": "bad", "params": {}}, "payload.step must be an integer"),
        ({"step": 999, "params": {}}, "unsupported step"),
        ({"step": 0, "params": []}, "payload.params must be a dict"),
        ({"step": 0, "params": {}, "opti_results": []}, "payload.opti_results must be a dict or None"),
    ],
)
def test_validate_payload_rejects_invalid_shape(payload, message: str) -> None:
    service = StratStrategyService(runner=lambda cfg: cfg)

    with pytest.raises(ValueError, match=message):
        service.validate_payload(payload)


@pytest.mark.unit
def test_validate_payload_shape_returns_structured_parts() -> None:
    service = StratStrategyService(runner=lambda cfg: cfg)

    parts = service._validate_payload_shape({"step": 23, "params": {"a": 1}, "opti_results": None})

    assert isinstance(parts, StratPayloadParts)
    assert parts.step == 23
    assert parts.params == {"a": 1}
    assert parts.opti_results is None


@pytest.mark.unit
def test_wavelength_to_index_is_stable_at_declared_precision() -> None:
    assert wavelength_to_index(500.1234564) == wavelength_to_index(500.12345649)
    assert wavelength_to_index(500.1234564) != wavelength_to_index(500.1234576)


@pytest.mark.unit
def test_generate_noise_array_deterministic_mode_returns_zeroes() -> None:
    noise = generate_noise_array((2, 3), scale=0.5, deterministic=True)

    assert noise.shape == (2, 3)
    assert noise.dtype == np.float64
    assert np.all(noise == 0.0)


@pytest.mark.unit
def test_generate_noise_array_with_seeded_rng_is_reproducible() -> None:
    rng_a = np.random.default_rng(123)
    rng_b = np.random.default_rng(123)

    noise_a = generate_noise_array((5,), scale=0.2, rng=rng_a)
    noise_b = generate_noise_array((5,), scale=0.2, rng=rng_b)

    assert np.allclose(noise_a, noise_b)
    assert np.all(np.abs(noise_a) <= 0.2)
