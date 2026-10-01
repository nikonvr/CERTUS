"""`SubstrateIndexGUI.display_results` shows the fit in the output tabs and builds nothing else (audit v2, plan S5.5, F841).

Found 2026-10-01 by the unused-variable rule: `display_results` assigned `dialog = IndexTableDialog(...)` and never used `dialog`. That is a complete window
("Substrate Refractive Index (n)", 1100 x 820, three laws compared, plots and tables) built at the end of every fit, parented to nothing, never shown, and
dropped when the method returns. The results reach the user through `_plot_output_results` and the second tab, which is all the method does besides.

The dialog is dead weight on every fit - and a way for a fit to fail AFTER it has succeeded, since its constructor reads the very same arrays. The class stays (a
guardrail test builds it); the method no longer builds one.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from certus.ui import certus_substrate_ui


@pytest.fixture
def constructed(monkeypatch):
    """The dialogs the method builds: the class is replaced by a recorder that refuses to be built."""
    built: list[tuple] = []

    def refuse(*args, **kwargs):
        built.append((args, kwargs))
        raise AssertionError("display_results built an IndexTableDialog that nobody shows")

    monkeypatch.setattr(certus_substrate_ui, "IndexTableDialog", refuse)
    return built


def stub_window():
    """What `display_results` touches of its window: the plot call, the tab bar, and the attribute it writes."""
    calls: list[tuple] = []
    tabs: list[int] = []
    window = SimpleNamespace(
        _plot_output_results=lambda *args: calls.append(args),
        main_tabs=SimpleNamespace(setCurrentIndex=tabs.append),
    )
    return window, calls, tabs


def results():
    x = np.linspace(400.0, 900.0, 6)
    raw = np.full(6, 1.52)
    by_model = {"cauchy": {"n": np.full(6, 1.51)}}
    rmse_row = {"cauchy": {"rmse": 1e-3}}
    return x, raw, by_model, rmse_row, {}, 420.0, 880.0, {"status": "ok"}


def test_display_results_builds_no_dialog(constructed):
    window, _, _ = stub_window()
    certus_substrate_ui.SubstrateIndexGUI.display_results(window, *results())
    assert constructed == []


def test_display_results_hands_the_arrays_to_the_plot_and_opens_the_output_tab(constructed):
    window, calls, tabs = stub_window()
    x, raw, by_model, rmse_row, meta, lo, hi, quality = results()
    certus_substrate_ui.SubstrateIndexGUI.display_results(window, x, raw, by_model, rmse_row, meta, lo, hi, quality)
    assert len(calls) == 1
    (got_x, got_raw, got_models, got_rmse, got_lo, got_hi) = calls[0]
    assert got_x is x
    assert got_raw is raw
    assert got_models is by_model
    assert got_rmse is rmse_row
    assert (got_lo, got_hi) == (lo, hi)
    assert tabs == [1]


def test_display_results_keeps_the_quality_summary_for_the_manifest(constructed):
    window, _, _ = stub_window()
    certus_substrate_ui.SubstrateIndexGUI.display_results(window, *results())
    assert window._last_quality_summary == {"status": "ok"}


def test_the_dialog_class_is_still_there_for_the_guardrail_that_builds_it():
    assert hasattr(certus_substrate_ui, "IndexTableDialog")
