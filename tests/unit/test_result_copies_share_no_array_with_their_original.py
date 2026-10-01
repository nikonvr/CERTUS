"""A copy of a result shares no array with its original, and the three copiers differ in what else they copy.

`certus/utils/certus_copy_utils.py` replaces `copy.deepcopy` on result dictionaries "~3x faster". It was covered at
64.3 % on 2026-09-30 and no test named it. What it promises is independence: a caller that keeps a backup of a
result and then edits the result must not see its backup change. Arrays, nested dictionaries and lists of arrays
are copied by all three functions; what differs is the list of dictionaries, which only some of them copy, and
that difference is pinned here so that a change of it is a decision and not an accident.
"""

from __future__ import annotations

import copy

import numpy as np
import pytest

from certus.utils import certus_copy_utils as utils
from certus.utils.certus_copy_utils import (
    copy_list_of_results,
    copy_optimization_result,
    copy_result_dict,
    copy_spline_result,
)

COPIERS = [copy_spline_result, copy_optimization_result, copy_result_dict]


def _result() -> dict:
    return {
        "rmse": 0.01,
        "name": "run",
        "missing": None,
        "ep": np.array([10.0, 20.0, 30.0]),
        "nested": {"curve": np.array([1.0, 2.0]), "label": "inner"},
        "arrays": [np.array([1.0]), np.array([2.0, 3.0])],
        "history": [{"step": 1, "x": np.array([0.5])}],
    }


@pytest.mark.parametrize("copier", COPIERS)
def test_an_array_of_the_copy_is_a_different_array_with_the_same_values(copier) -> None:
    original = _result()
    copied = copier(original)

    copied["ep"][0] = -1.0
    copied["nested"]["curve"][:] = 0.0
    copied["arrays"][1][0] = -5.0

    assert original["ep"].tolist() == [10.0, 20.0, 30.0]
    assert original["nested"]["curve"].tolist() == [1.0, 2.0]
    assert original["arrays"][1].tolist() == [2.0, 3.0]


@pytest.mark.parametrize("copier", COPIERS)
def test_the_copy_holds_the_same_values_as_the_original_and_as_a_deepcopy(copier) -> None:
    original = _result()
    reference = copy.deepcopy(original)

    copied = copier(original)

    assert copied.keys() == reference.keys()
    assert copied["rmse"] == 0.01
    assert copied["name"] == "run"
    assert copied["missing"] is None
    np.testing.assert_array_equal(copied["ep"], reference["ep"])
    np.testing.assert_array_equal(copied["nested"]["curve"], reference["nested"]["curve"])
    assert [a.tolist() for a in copied["arrays"]] == [a.tolist() for a in reference["arrays"]]


@pytest.mark.parametrize("copier", COPIERS)
def test_a_nested_dictionary_is_a_different_dictionary(copier) -> None:
    original = _result()

    copier(original)["nested"]["label"] = "changed"

    assert original["nested"]["label"] == "inner"


def test_a_list_of_dictionaries_is_copied_by_the_design_copier_and_by_deep_lists_only() -> None:
    """Not a wish: what the three functions do today. `copy_spline_result` and the default `copy_result_dict`
    keep the SAME dictionary inside a list, `copy_optimization_result` and `deep_lists=True` copy it."""
    original = _result()
    inner = original["history"][0]

    assert copy_spline_result(original)["history"][0] is inner
    assert copy_result_dict(original)["history"][0] is inner
    assert copy_optimization_result(original)["history"][0] is not inner
    assert copy_result_dict(original, deep_lists=True)["history"][0] is not inner
    assert copy_optimization_result(original)["history"][0]["x"] is not inner["x"]  # its arrays come with it


def test_copying_a_list_of_results_copies_each_result() -> None:
    originals = [_result(), _result()]

    copies = copy_list_of_results(originals)
    copies[0]["ep"][0] = -1.0

    assert originals[0]["ep"][0] == 10.0
    assert copies[1]["ep"][0] == 10.0
    assert len(copies) == 2


def test_the_old_names_are_the_generic_copier() -> None:
    assert utils.fast_deepcopy is copy_result_dict
    assert utils.copy_dict_result is copy_result_dict
