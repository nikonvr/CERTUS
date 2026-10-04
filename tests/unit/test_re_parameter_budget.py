"""The parameter budget of a reverse-engineering result (port of certus_re, Zenodo, ``dof.count_free_parameters``).

    EVERY BLOCK IS LISTED, the held ones too, with why its count is what it is
    THE COUNT FOLLOWS THE RESULT: a phase-1 result released the thicknesses alone, whatever later phases did
    A MATERIAL WHOSE REFINEMENT IS OFF counts zero: the solver pins its knots at zero
    THE RATIO THAT LIMITS AN INVERSION: data points per released parameter, unknown when the data were not counted
    AN IMPOSED APERTURE costs nothing: the cone is applied, no parameter is released for it
"""

from __future__ import annotations

import logging

import pytest

from certus.core.certus_re_budget import attach_parameter_budget, parameter_budget

BOTH = {"re_refine_h": True, "re_refine_l": True}


def phase4_result(n_layers: int = 17, n_knots: int = 5) -> dict:
    return {
        "ep": [100.0] * n_layers,
        "re_dH_knots": [0.0] * n_knots,
        "re_dL_knots": [0.0] * n_knots,
        "re_sub_cauchy_a0": 1.5,
        "re_p4_beam_ap_knots_deg": [1.8, 1.9, 2.0, 2.1],
    }


def counts(budget: dict) -> dict:
    return {b["name"]: b["count"] for b in budget["blocks"]}


def test_a_phase4_result_counts_every_block_it_released():
    budget = parameter_budget(phase4_result(), BOTH, 1200)
    assert counts(budget) == {
        "layer thicknesses": 17,
        "index correction H": 5,
        "index correction L": 5,
        "spline node lambda2": 1,
        "substrate Cauchy": 3,
        "beam aperture": 4,
    }
    assert budget["n_free_parameters"] == 35
    assert budget["points_per_free_parameter"] == pytest.approx(1200 / 35)


def test_a_phase1_result_released_the_thicknesses_alone_and_says_why_the_rest_is_zero():
    budget = parameter_budget({"ep": [100.0] * 6}, BOTH, 600)
    assert budget["n_free_parameters"] == 6
    statuses = {b["name"]: b["status"] for b in budget["blocks"]}
    assert statuses["index correction H"] == "tabulated indices, no correction"
    assert statuses["substrate Cauchy"] == "tabulated substrate"
    assert statuses["beam aperture"] == "not modelled (no cone average)"


def test_a_material_whose_refinement_is_off_counts_zero():
    budget = parameter_budget(phase4_result(), {"re_refine_h": False, "re_refine_l": True}, 1200)
    assert counts(budget)["index correction H"] == 0
    assert counts(budget)["index correction L"] == 5
    assert counts(budget)["spline node lambda2"] == 1
    assert budget["n_free_parameters"] == 30


def test_the_ratio_is_unknown_when_the_data_were_not_counted():
    budget = parameter_budget(phase4_result(), BOTH, None)
    assert budget["n_data_points"] is None
    assert budget["points_per_free_parameter"] is None


def test_attach_reads_the_data_count_of_the_uncertainty_and_logs_every_block(caplog):
    top = phase4_result()
    top["thickness_uncertainty"] = {"n_data": 1200}
    with caplog.at_level(logging.INFO, logger="t"):
        attach_parameter_budget(top, BOTH, logging.getLogger("t"))
    assert top["parameter_budget"]["n_data_points"] == 1200
    assert "35 free parameters, 1200 data points, 34.3 per free parameter" in caplog.text
    assert caplog.text.count("RE   ") == 6


def test_an_imposed_aperture_is_modelled_but_costs_no_parameter():
    cfg = dict(BOTH, re_beam_aperture_imposed_deg=2.0)
    budget = parameter_budget(phase4_result(), cfg, 1200)
    aperture = next(b for b in budget["blocks"] if b["name"] == "beam aperture")
    assert aperture == {"name": "beam aperture", "count": 0, "status": "imposed, 2.00 deg total"}
    assert budget["n_free_parameters"] == 31
