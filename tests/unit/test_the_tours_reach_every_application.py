"""Every application starts the tour written for it, not the generic welcome (audit UX A09, ETAT D87).

The catalogue of tours (`certus/ui/certus_tours_catalog.py`) is keyed by `APP_NAME`. Measured 2026-10-02, INDEX SPLINE
showed "Welcome: Every CERTUS app has a command palette ...", one step of one: its tour was registered under
"CERTUS-INDEX-SPLINE" while the window is named "CERTUS_INDEX_SPLINE", so the key never matched and the default tour
took over. FIELD had no tour at all.
"""

from __future__ import annotations

import importlib

import pytest

from certus.ui.certus_tours_catalog import registered_app_names, steps_for_app

DEFAULT_TITLE = steps_for_app("an application that has no tour")[0].title

@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "tour targets", main_windows_only=True)


APPLICATIONS = [
    ("certus.ui.certus_design_ui", "CertusDesignApp"),
    ("certus.ui.certus_field_ui", "CertusFieldApp"),
    ("certus.ui.certus_index_ui", "CertusIndexApp"),
    ("certus.ui.certus_index_spline_ui", "CertusIndexSplineApp"),
    ("certus.ui.certus_strat_ui", "CertusStratApp"),
    ("CERTUS_RE", "CertusREApp"),
    ("certus.metal.certus_metal_bilayer_app", "CertusMetalBilayerApp"),
]


@pytest.mark.parametrize(("module", "name"), APPLICATIONS, ids=[name for _, name in APPLICATIONS])
def test_the_name_of_the_window_has_a_tour(module, name) -> None:
    app_name = getattr(importlib.import_module(module), name).APP_NAME

    assert app_name in registered_app_names(), f"{name} is called {app_name!r}: no tour is registered under that name"
    assert steps_for_app(app_name)[0].title != DEFAULT_TITLE


def test_the_single_layer_metal_window_has_a_tour() -> None:
    """Its name is given to the base class by the constructor, so it is read from the source."""
    assert "CERTUS-METAL-SINGLE" in registered_app_names()


def test_the_field_tour_points_at_widgets_that_exist(qapp) -> None:
    from certus.ui.certus_field_ui import CertusFieldApp

    win = CertusFieldApp()
    try:
        targets = [step.target_attr for step in steps_for_app(win.APP_NAME) if step.target_attr]
        assert targets, "the FIELD tour points at nothing"
        for attr in targets:
            assert getattr(win, attr, None) is not None, f"the FIELD tour points at {attr!r}, which the window lacks"
    finally:
        win.close()
