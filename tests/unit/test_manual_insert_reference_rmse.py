"""`_reference_rmse_of_the_base_result` is the RMSE a manually inserted mesh is judged against (audit v2, plan S5.2).

It was eleven lines in the middle of `insert_manual_sigma_nodes` (490 lines, complexity 61). The reference is the RMSE of the base result, unless a polished or globally best value is
tighter and finite: a K+n result must not be accepted when it regresses against the polished baseline.
"""

from __future__ import annotations

import inspect

import pytest

from certus.spline import spline_pipeline_mesh_insert as module
from certus.spline.spline_pipeline_mesh_insert import _reference_rmse_of_the_base_result as reference


def test_the_reference_is_the_rmse_of_the_base_result():
    assert reference({"rmse": 0.004}) == 0.004


def test_the_rmse_is_read_as_a_float():
    assert isinstance(reference({"rmse": 1}), float)


def test_a_base_result_without_rmse_has_an_infinite_reference():
    assert reference({}) == float("inf")


def test_a_tighter_polished_value_becomes_the_reference():
    assert reference({"rmse": 0.004, "spectral_rmse_polished_value": 0.003}) == 0.003


def test_a_looser_polished_value_is_ignored():
    assert reference({"rmse": 0.004, "spectral_rmse_polished_value": 0.005}) == 0.004


def test_an_equal_polished_value_changes_nothing():
    assert reference({"rmse": 0.004, "spectral_rmse_polished_value": 0.004}) == 0.004


def test_the_globally_best_value_wins_over_the_polished_one_when_both_are_there():
    assert reference({"rmse": 0.004, "spectral_rmse_global_best_value": 0.001, "spectral_rmse_polished_value": 0.002}) == 0.001
    assert reference({"rmse": 0.004, "spectral_rmse_global_best_value": 0.003, "spectral_rmse_polished_value": 0.001}) == 0.003


def test_a_polished_value_is_used_when_the_global_one_is_missing():
    assert reference({"rmse": 0.004, "spectral_rmse_global_best_value": None, "spectral_rmse_polished_value": 0.002}) == 0.002


@pytest.mark.parametrize("polished", [float("nan"), float("inf"), float("-inf")], ids=["nan", "inf", "-inf"])
def test_a_polished_value_that_is_not_finite_is_ignored(polished):
    assert reference({"rmse": 0.004, "spectral_rmse_polished_value": polished}) == 0.004


@pytest.mark.parametrize("polished", ["not a number", [0.001], {"v": 0.001}], ids=["text", "list", "dict"])
def test_a_polished_value_that_cannot_be_read_is_ignored(polished):
    assert reference({"rmse": 0.004, "spectral_rmse_polished_value": polished}) == 0.004


def test_a_polished_value_can_be_given_as_text_of_a_number():
    assert reference({"rmse": 0.004, "spectral_rmse_polished_value": "0.002"}) == 0.002


def test_a_polished_value_replaces_a_missing_base_rmse():
    assert reference({"spectral_rmse_polished_value": 0.002}) == 0.002


def test_the_insertion_asks_for_it_once_the_mesh_summary_is_known():
    source = inspect.getsource(module.insert_manual_sigma_nodes)
    assert "rmse_ref = _reference_rmse_of_the_base_result(out)" in source
    assert source.index("mesh_summary = ") < source.index("rmse_ref = _reference_rmse_of_the_base_result(out)") < source.index("if not np.isfinite(rmse_ref):")
