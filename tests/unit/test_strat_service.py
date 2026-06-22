"""Unit tests for StratStrategyService (Track C)."""

from __future__ import annotations

import logging
import numpy as np
import pytest

import certus.utils.certus_strat_service as strat_service
from certus.utils.certus_strat_service import (
    StratStrategyService,
    build_wavelength_index_map,
    generate_noise_array,
    wavelength_to_index,
)
from certus.workers.certus_strat_workers_dto import StratParamsDTO



def test_validate_payload_rejects_invalid_step() -> None:
    svc = StratStrategyService(lambda cfg: cfg)
    with pytest.raises(ValueError, match=r"unsupported step|is not one of"):
        svc.validate_payload({"step": 999, "params": {}})


def test_validate_payload_accepts_and_normalizes() -> None:
    svc = StratStrategyService(lambda cfg: cfg)
    if svc._get_schema() is not None:
        pytest.skip("Legacy string-step coercion N/A with JSON schema validation active")
    payload = svc.validate_payload({"step": "2", "params": {"seed": 1}, "opti_results": {"x": 1}})
    assert payload["step"] == 2
    assert payload["params"] == {"seed": 1}
    assert payload["opti_results"] == {"x": 1}


def test_validate_payload_checks_material_coverage() -> None:
    svc = StratStrategyService(lambda cfg: cfg)
    class MockDB:
        def __init__(self):
            self.data = {
                "nH": {"min_wl_valid": 400.0, "max_wl_valid": 700.0}
            }
    db = MockDB()
    params = {
        "l0": 550.0,
        "stack_string": "1.0,1.0",
        "wl_range": [200.0, 300.0],
        "scan_wl_min": 200.0,  # Below 400 and no overlap
        "scan_wl_max": 300.0,
        "nH_id": "nH",
        "nL_id": "nL",
        "nSub_id": "nSub"
    }
    # Should raise because no overlap exists at all
    with pytest.raises(ValueError, match="Requested start 200.0nm < Data start 400.0nm"):
        svc.validate_payload({"step": 0, "params": params}, materials_db=db)

    # Should pass if within range
    params["scan_wl_min"] = 450.0
    params["wl_range"] = [450.0, 700.0]
    svc.validate_payload({"step": 0, "params": params}, materials_db=db)


def test_validate_payload_checks_material_coverage_fallback_to_wl() -> None:
    svc = StratStrategyService(lambda cfg: cfg)
    class MockDB:
        def __init__(self):
            self.data = {
                "nH": {"wl": np.array([400.0, 500.0, 700.0])}
            }
    db = MockDB()
    params = {
        "l0": 550.0,
        "stack_string": "1.0,1.0",
        "wl_range": [450.0, 600.0],
        "scan_wl_min": 450.0,
        "scan_wl_max": 600.0,
        "nH_id": "nH",
        "nL_id": "nL",
        "nSub_id": "nSub"
    }
    svc.validate_payload({"step": 0, "params": params}, materials_db=db)


# ---------------------------------------------------------------------------
# P1-8: JSON schema validation tests
# ---------------------------------------------------------------------------

def _valid_params() -> dict:
    return {
        "l0": 550.0,
        "stack_string": "1.0,1.0",
        "wl_range": [400.0, 700.0],
        "nH_id": "Nb2O5",
        "nL_id": "SiO2",
        "nSub_id": "Silice",
    }


def test_p1_8_valid_payload_passes_schema() -> None:
    """A fully valid payload must pass schema validation with zero errors."""
    svc = StratStrategyService(lambda cfg: cfg)
    errors = svc.validate_against_schema({"step": 0, "params": _valid_params()})
    assert errors == [], f"Expected no schema errors, got: {errors}"


def test_p1_8_missing_required_param_detected() -> None:
    """Missing required param (e.g. l0) must be reported as a schema violation."""
    svc = StratStrategyService(lambda cfg: cfg)
    params = _valid_params()
    del params["l0"]
    errors = svc.validate_against_schema({"step": 0, "params": params})
    # If jsonschema is installed, errors must be non-empty; otherwise skip
    if svc._get_schema() is not None:
        assert any("l0" in e for e in errors), f"Expected l0 error, got: {errors}"


def test_p1_8_invalid_step_detected_by_schema() -> None:
    """Step value not in enum must be reported as a schema violation."""
    svc = StratStrategyService(lambda cfg: cfg)
    errors = svc.validate_against_schema({"step": 999, "params": _valid_params()})
    if svc._get_schema() is not None:
        assert len(errors) > 0, "Expected schema errors for step=999"


def test_p1_8_validate_payload_raises_on_schema_violation() -> None:
    """validate_payload must raise ValueError when schema violations are detected."""
    svc = StratStrategyService(lambda cfg: cfg)
    if svc._get_schema() is None:
        pytest.skip("jsonschema not available")
    params = _valid_params()
    del params["l0"]
    with pytest.raises(ValueError, match="schema"):
        svc.validate_payload({"step": 0, "params": params})


def test_strat_schema_rejects_extra_keys() -> None:
    """Unknown keys must be rejected now that additionalProperties is false."""
    svc = StratStrategyService(lambda cfg: cfg)
    if svc._get_schema() is None:
        pytest.skip("jsonschema not available")

    payload = {
        "step": 0,
        "params": {
            **_valid_params(),
            "unexpected_param": 123,
        },
        "unexpected_root": True,
    }

    with pytest.raises(ValueError, match="schema"):
        svc.validate_payload(payload)


def test_p1_8_scan_wl_bounds_must_be_paired() -> None:
    """scan_wl_min and scan_wl_max must be provided together (cross-field rule)."""
    svc = StratStrategyService(lambda cfg: cfg)
    if svc._get_schema() is None:
        pytest.skip("jsonschema not available")

    params = _valid_params()
    params["scan_wl_min"] = 450.0

    with pytest.raises(ValueError, match="schema"):
        svc.validate_payload({"step": 0, "params": params})


def test_p1_10_generate_noise_array_returns_zeros_in_deterministic_mode() -> None:
    noise = generate_noise_array((2, 3), scale=5.0, deterministic=True)

    assert noise.shape == (2, 3)
    assert np.array_equal(noise, np.zeros((2, 3), dtype=np.float64))


def test_p1_10_set_deterministic_toggles_service_flag() -> None:
    svc = StratStrategyService(lambda cfg: cfg)

    svc.set_deterministic(True)
    assert svc._deterministic is True

    svc.set_deterministic(False)
    assert svc._deterministic is False


def test_p1_10_generate_noise_array_is_reproducible_with_local_rng() -> None:
    rng_a = np.random.default_rng(123)
    rng_b = np.random.default_rng(123)

    noise_a = generate_noise_array((4,), scale=2.5, rng=rng_a)
    noise_b = generate_noise_array((4,), scale=2.5, rng=rng_b)

    assert np.allclose(noise_a, noise_b, atol=0.0, rtol=0.0)
    assert np.all(np.abs(noise_a) <= 2.5)


def test_p1_10_validate_candidates_phase_a_uses_params_deterministic_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_generate_noise_array(shape, scale, distribution, rng=None, deterministic=False):
        captured["shape"] = shape
        captured["scale"] = scale
        captured["deterministic"] = deterministic
        return np.zeros(shape, dtype=np.float64)

    def fake_validate_wavelengths_batch(*args, **kwargs):
        return np.array([[0.1, 0.01]], dtype=np.float64)

    def fake_update_run_states_kernel(*args, **kwargs):
        return np.array([[100.0]], dtype=np.float64)

    monkeypatch.setattr(strat_service, "generate_noise_array", fake_generate_noise_array)
    monkeypatch.setattr(strat_service, "validate_wavelengths_batch", fake_validate_wavelengths_batch)
    monkeypatch.setattr(strat_service, "update_run_states_kernel", fake_update_run_states_kernel)

    results, updates = strat_service._validate_candidates_phase_a(
        candidates=[{"wl": 550.0}],
        i_layer=0,
        num_runs=1,
        p_thick_nominal=[100.0],
        clues_at_wl={550.0: {"H": 2.1 + 0.0j, "L": 1.45 + 0.0j, "substrate": 1.52 + 0.0j}},
        params={
            "reality_sim_params": {"trigger_tolerance": 5.0},
            "probe_offset_ratio": 0.0,
            "deterministic": True,
        },
        run_states=[{"p_thick_sim": []}],
    )

    assert captured["deterministic"] is True
    assert results[0]["wl"] == pytest.approx(550.0)
    assert updates == [[100.0]]


def test_p1_9_wavelength_to_index_collapses_float_drift_at_wl_decimals() -> None:
    assert wavelength_to_index(550.0000004) == wavelength_to_index(550.00000049)


def test_p1_9_build_wavelength_index_map_supports_nearby_float_queries() -> None:
    clue = {"H": 2.1 + 0.0j, "L": 1.45 + 0.0j, "substrate": 1.52 + 0.0j}
    wl_map = build_wavelength_index_map({550.0000004: clue})

    assert wl_map[wavelength_to_index(550.00000049)] is clue


def test_p1_9_validate_candidates_phase_a_uses_integer_wavelength_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_validate_wavelengths_batch(*args, **kwargs):
        return np.array([[0.1, 0.01]], dtype=np.float64)

    def fake_update_run_states_kernel(*args, **kwargs):
        return np.array([[100.0]], dtype=np.float64)

    monkeypatch.setattr(strat_service, "validate_wavelengths_batch", fake_validate_wavelengths_batch)
    monkeypatch.setattr(strat_service, "update_run_states_kernel", fake_update_run_states_kernel)

    results, updates = strat_service._validate_candidates_phase_a(
        candidates=[{"wl": 550.00000049}],
        i_layer=0,
        num_runs=1,
        p_thick_nominal=[100.0],
        clues_at_wl={550.0000004: {"H": 2.1 + 0.0j, "L": 1.45 + 0.0j, "substrate": 1.52 + 0.0j}},
        params={
            "reality_sim_params": {"trigger_tolerance": 5.0},
            "probe_offset_ratio": 0.0,
            "deterministic": True,
        },
        run_states=[{"p_thick_sim": []}],
        layer_noise_array=np.zeros((1,), dtype=np.float64),
    )

    assert results[0]["wl"] == pytest.approx(550.00000049)
    assert updates == [[100.0]]


def test_p1_2_select_candidates_phase_a_raises_on_strict_transmission_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_calculate_dynamics_ultimate(*args, **kwargs):
        return [
            {
                "wl": 550.0,
                "dynamics": 0.5,
                "t_init": 0.05,
                "t_final": 0.05,
                "t_min": 0.05,
            }
        ]

    monkeypatch.setattr(strat_service, "calculate_dynamics_ULTIMATE", fake_calculate_dynamics_ultimate)

    with pytest.raises(RuntimeError, match="strict_min_transmission_floor=True"):
        strat_service._select_candidates_phase_a(
            scan_wl_range=np.array([550.0], dtype=np.float64),
            i_layer=0,
            p_thick_nominal=[100.0],
            clues_at_wl={550.0: {"H": 2.1 + 0.0j, "L": 1.45 + 0.0j, "substrate": 1.52 + 0.0j}},
            nominal_matrix_cache=np.zeros((1, 2, 2), dtype=np.complex128),
            all_wls=np.array([550.0], dtype=np.float64),
            params={
                "logger": logging.getLogger("test_strat_service"),
                "reality_sim_params": {"trigger_tolerance": 5.0},
                "dynamics_threshold": 0.01,
                "min_transmission_floor": 0.10,
                "strict_min_transmission_floor": True,
            },
            l0=550.0,
        )


def test_select_best_strat_result_empty() -> None:
    """Test select_best_strat_result handles empty/invalid lists."""
    assert strat_service.select_best_strat_result([]) is None
    assert strat_service.select_best_strat_result([None]) is None


def test_select_best_strat_result_ranking() -> None:
    """Test select_best_strat_result finds first finite positive score."""
    strategies = [
        {"strategy_id": "strat_0", "robustness_score": None},
        {"strategy_id": "strat_1", "robustness_score": 0.0},
        {"strategy_id": "strat_2", "robustness_score": float("nan")},
        {"strategy_id": "strat_3", "rmse_p95": 1.23},
        {"strategy_id": "strat_4", "rmse_mean": 0.45},
    ]
    best = strat_service.select_best_strat_result(strategies)
    assert best is not None
    assert best["strategy_id"] == "strat_3"


def test_extract_best_rmse_correctness() -> None:
    """Test extract_best_rmse extracts correct float values from fallbacks."""
    strategies = [
        {"strategy_id": "strat_1", "rmse": 0.0},
        {"strategy_id": "strat_2", "final_rmse": 0.005},
    ]
    assert strat_service.extract_best_rmse(strategies) == pytest.approx(0.005)
    assert strat_service.extract_best_rmse([]) == 0.0

    strategies_invalid = [
        {"strategy_id": "strat_1", "rmse": -1.0},
    ]
    assert strat_service.extract_best_rmse(strategies_invalid) == 0.0


def test_extract_best_rmse_raises_physics_convergence_error() -> None:
    """Test extract_best_rmse raises PhysicsConvergenceError for abnormally low RMSE (< 1e-7)."""
    from certus.utils.errors import PhysicsConvergenceError
    
    strategies_too_low = [
        {"strategy_id": "strat_1", "rmse": 0.0},
    ]
    with pytest.raises(PhysicsConvergenceError, match="abnormally low/null value"):
        strat_service.extract_best_rmse(strategies_too_low)


# ---------------------------------------------------------------------------
# PR 5: Validation, Material Coverage, Legacy & DTO compatibility tests
# ---------------------------------------------------------------------------

def test_pr5_invalid_schema_rejected() -> None:
    """An invalid payload structure (wrong types or missing root keys) must be rejected."""
    svc = StratStrategyService(lambda cfg: cfg)

    # Missing params root key
    with pytest.raises(ValueError, match=r"Invalid params payload structure|payload.params must be a dict|'params' is a required property"):
        svc.validate_payload({"step": 0})

    # Wrong params type
    with pytest.raises(ValueError, match=r"payload.params must be a dict|is not of type"):
        svc.validate_payload({"step": 0, "params": "not-a-dict"})



def test_pr5_material_coverage_failure() -> None:
    """Material coverage checking must raise ValueError when all materials are out of bounds."""
    svc = StratStrategyService(lambda cfg: cfg)
    class MockDB:
        def __init__(self):
            self.data = {
                "Nb2O5": {"min_wl_valid": 400.0, "max_wl_valid": 700.0},
                "SiO2": {"min_wl_valid": 400.0, "max_wl_valid": 700.0},
                "Silice": {"min_wl_valid": 400.0, "max_wl_valid": 700.0},
            }
    db = MockDB()
    
    # Range [800.0, 900.0] has absolutely no overlap with Nb2O5 / SiO2 / Silice (400-700)
    params = _valid_params()
    params["scan_wl_min"] = 800.0
    params["scan_wl_max"] = 900.0
    params["wl_range"] = [800.0, 900.0]

    with pytest.raises(ValueError, match="CRITICAL: Material Data Missing for Spectral Range"):
        svc.validate_payload({"step": 0, "params": params}, materials_db=db)


def test_pr5_legacy_payload_normalization() -> None:
    """Legacy dict-based payloads must be correctly validated and normalized."""
    svc = StratStrategyService(lambda cfg: cfg)
    legacy_payload = {
        "step": 0,
        "params": _valid_params()
    }
    
    normalized = svc.validate_payload(legacy_payload)
    assert normalized["step"] == 0
    assert isinstance(normalized["params"], StratParamsDTO)
    assert normalized["params"]["l0"] == 550.0
    assert normalized["opti_results"] is None


def test_pr5_dto_compatibility() -> None:
    """Passing Pydantic DTO instances directly in the payload must work seamlessly."""
    svc = StratStrategyService(lambda cfg: cfg)
    if svc._get_schema() is not None:
        pytest.skip("DTO passthrough N/A with JSON schema active (schema expects plain dict for params)")
    params_dto = StratParamsDTO.model_validate(_valid_params())
    dto_payload = {
        "step": 0,
        "params": params_dto
    }

    normalized = svc.validate_payload(dto_payload)
    assert normalized["step"] == 0
    assert normalized["params"] is params_dto



