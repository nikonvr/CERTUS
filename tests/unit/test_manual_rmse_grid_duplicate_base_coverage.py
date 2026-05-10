"""Regression: grille RMSE(d) — visite « base » rejetée en doublon conserve le bilan de couverture."""

from __future__ import annotations

import pytest

from spline_profile_corridors import _manual_grid_tag_base_on_duplicate_discard


def test_incoming_extra_does_not_retag_duplicate_slot() -> None:
    kinds = [1]
    _manual_grid_tag_base_on_duplicate_discard(kinds, 0, incoming_point_kind=1)
    assert kinds == [1]


def test_incoming_base_force_tags_slot_as_base() -> None:
    kinds = [1]
    _manual_grid_tag_base_on_duplicate_discard(kinds, 0, incoming_point_kind=0)
    assert kinds == [0]


def test_negative_index_skipped_safely() -> None:
    kinds = [1]
    _manual_grid_tag_base_on_duplicate_discard(kinds, -1, incoming_point_kind=0)
    assert kinds == [1]


@pytest.mark.parametrize("idx", [-5, 3])
def test_out_of_range_skipped(idx: int) -> None:
    kinds = [1, 0]
    _manual_grid_tag_base_on_duplicate_discard(kinds, idx, incoming_point_kind=0)
    assert kinds == [1, 0]
