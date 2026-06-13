"""Unit tests for the new STRAT DTOs."""

from __future__ import annotations

import logging
import pytest
from certus.workers.certus_strat_workers_dto import StratParamsDTO, StratOptiResultsDTO


class MockDB:
    def __init__(self):
        self.data = {}


@pytest.mark.unit
def test_strat_params_dto_instantiation_and_mapping() -> None:
    # 1. Test standard instantiation
    db = MockDB()
    logger = logging.getLogger("Test")
    params = StratParamsDTO(
        nH_id="mat_H",
        nL_id="mat_L",
        nSub_id="substrate",
        l0=550.0,
        stack_string="1.0, 1.0, 1.0",
        wl_range=[400.0, 800.0],
        wl_step=2.0,
        scan_wl_min=450.0,
        scan_wl_max=750.0,
        reality_sim_params={"trigger_tolerance": 0.5},
        phase_a_seed=42,
        robustness_seed=123,
        logger=logger,
        materials_db=db,
        custom_extra_key="extra_value"  # extra field
    )

    # Test attributes
    assert params.nH_id == "mat_H"
    assert params.l0 == 550.0
    assert params.custom_extra_key == "extra_value"

    # Test Mapping protocol (__getitem__, get, keys, len, iter)
    assert params["nH_id"] == "mat_H"
    assert params["custom_extra_key"] == "extra_value"
    with pytest.raises(KeyError):
        _ = params["non_existent_key"]

    assert params.get("nH_id") == "mat_H"
    assert params.get("non_existent_key") is None
    assert params.get("non_existent_key", "default") == "default"

    # Check keys & iteration
    keys = list(params.keys())
    assert "nH_id" in keys
    assert "custom_extra_key" in keys
    assert len(params) == len(keys)

    # Check equality __eq__
    expected_dict = {
        "nH_id": "mat_H",
        "nL_id": "mat_L",
        "nSub_id": "substrate",
        "l0": 550.0,
        "stack_string": "1.0, 1.0, 1.0",
        "wl_range": [400.0, 800.0],
        "wl_step": 2.0,
        "scan_wl_min": 450.0,
        "scan_wl_max": 750.0,
        "reality_sim_params": {"trigger_tolerance": 0.5},
        "phase_a_seed": 42,
        "robustness_seed": 123,
        "logger": logger,
        "materials_db": db,
        "custom_extra_key": "extra_value"
    }
    assert params == expected_dict
    assert params == StratParamsDTO.model_validate(expected_dict)


@pytest.mark.unit
def test_strat_opti_results_dto_instantiation_and_mapping() -> None:
    results = StratOptiResultsDTO(
        p_thick_nominal=[110.0, 120.0, 130.0],
        all_strategies=["A", "B"],
        clues_at_wl={500.0: {"n": 1.5 + 0.1j}},
        raw_results_thickness=[109.5, 120.1, 129.8],
        my_extra_score=0.99
    )

    assert results.p_thick_nominal == [110.0, 120.0, 130.0]
    assert results.my_extra_score == 0.99
    assert results["my_extra_score"] == 0.99
    assert results.get("all_strategies") == ["A", "B"]

    expected_dict = {
        "p_thick_nominal": [110.0, 120.0, 130.0],
        "all_strategies": ["A", "B"],
        "clues_at_wl": {500.0: {"n": 1.5 + 0.1j}},
        "raw_results_thickness": [109.5, 120.1, 129.8],
        "my_extra_score": 0.99
    }
    assert results == expected_dict
