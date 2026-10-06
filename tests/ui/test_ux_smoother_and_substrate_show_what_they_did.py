"""SMOOTHER shows the raw curve next to the smoothed one, and SUBSTRATE INDEX says which columns it read (audit UX A11, ETAT D86).

Two decisions the operator could not check at a glance, measured 2026-10-02:

* SMOOTHER hid the raw traces by default (`chk_raw.setChecked(False)`) and, with them hidden, named the smoothed
  curve like the data column: nothing on the plot said it was smoothed, nor how much it differed from the measurement.
* SUBSTRATE INDEX keeps only the columns whose NAME says "bare substrate" (a guard against reading a film as a
  substrate: it stays). The columns it left out were written to the log, which is folded away by default; only a
  workbook with no bare-substrate column at all was explained, in a dialog.

Now the raw traces are on by default, the smoothed curve is always named "(Clean)", and SUBSTRATE shows, under its
naming hint, the columns it read and the ones it left out.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def smoother(qapp):
    from certus.utils.certus_curve_smoother import CurveSmootherGUI

    win = CurveSmootherGUI()
    x = np.linspace(400.0, 800.0, 200)
    win.df = pd.DataFrame({"Wavelength": x, "A": 50.0 + 5.0 * np.sin(x / 40.0) + np.cos(7.0 * x)})
    try:
        yield win
    finally:
        win.close()


def _curve_names(win) -> set[str]:
    return {item.opts.get("name") for item in win.plot_widget.listDataItems()}


def test_the_raw_traces_are_shown_by_default(smoother) -> None:
    assert smoother.chk_raw.isChecked()
    smoother.update_plot()
    assert _curve_names(smoother) == {"A (Raw)", "A (Clean)"}


@pytest.mark.parametrize("show_raw", [True, False])
def test_the_smoothed_curve_is_named_as_such_with_or_without_the_raw_one(smoother, show_raw) -> None:
    smoother.chk_raw.setChecked(show_raw)
    smoother.update_plot()
    assert "A (Clean)" in _curve_names(smoother)
    assert ("A (Raw)" in _curve_names(smoother)) is show_raw


def test_substrate_index_lists_the_columns_it_read_and_the_ones_it_left_out(qapp, monkeypatch, tmp_path) -> None:
    import certus.ui.certus_substrate_ui as module
    from certus.core.certus_substrate_index import _filter_dataframe_bare_substrate_columns

    wavelength = np.linspace(400.0, 800.0, 30)
    workbook = pd.DataFrame(
        {
            "Wavelength": wavelength,
            "T substrate nu": np.full(30, 90.0),
            "R sbst nu": np.full(30, 8.0),
            "T filter stack": np.full(30, 40.0),
        }
    )
    _, kept, left_out = _filter_dataframe_bare_substrate_columns(workbook)
    assert kept
    assert left_out, "the premise of the test: the workbook holds a column that is not a bare substrate"
    monkeypatch.setattr(
        module, "open_measurement_excel_interactive", lambda *_a, **_k: (workbook, str(tmp_path / "m.xlsx"), str(tmp_path))
    )

    window = module.SubstrateIndexGUI()
    try:
        assert not window.columns_recap.isVisibleTo(window), "the recap shows before anything is loaded"

        window.load_file()

        assert window.columns_recap.isVisibleTo(window)
        text = window.columns_recap.text()
        for name in kept + left_out:
            assert str(name) in text, f"{name!r} is missing from the recap: {text!r}"
        assert "Left out" in text
    finally:
        window.close()
