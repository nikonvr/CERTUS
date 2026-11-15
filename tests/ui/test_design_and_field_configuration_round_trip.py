"""A saved DESIGN or FIELD configuration brings back the settings it left out (audit 2026-11-15, M-L5b).

DESIGN wrote the number of Monte Carlo draws and the absolute sigma, not the relative sigma, the optical-thickness sigma
nor the RMSE threshold of the spectral Monte Carlo. FIELD did not write the minimal thickness of its optimiser.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "configuration round trip", main_windows_only=True)


def test_design_brings_back_the_spectral_monte_carlo_settings(qapp) -> None:
    from certus.ui.certus_design_ui import CertusDesignApp

    source, fresh = CertusDesignApp(), CertusDesignApp()
    source.mc_sigma_rel_spin.setValue(1.5)
    source.mc_sigma_ot_spin.setValue(0.75)
    source.mc_rmse_threshold_spin.setValue(0.02)

    fresh._apply_config(source._collect_config())

    assert fresh.mc_sigma_rel_spin.value() == 1.5
    assert fresh.mc_sigma_ot_spin.value() == 0.75
    assert fresh.mc_rmse_threshold_spin.value() == pytest.approx(0.02)


def test_field_brings_back_the_minimal_thickness_of_the_optimiser(qapp) -> None:
    from certus.ui.certus_field_ui import CertusFieldApp

    source, fresh = CertusFieldApp(), CertusFieldApp()
    source.opt_panel.edit_dmin.setValue(12.5)

    fresh._apply_config(source._collect_config())

    assert fresh.opt_panel.edit_dmin.value() == 12.5


def test_field_keeps_its_minimal_thickness_when_the_configuration_has_none(qapp) -> None:
    from certus.ui.certus_field_ui import CertusFieldApp

    source, fresh = CertusFieldApp(), CertusFieldApp()
    old = {k: v for k, v in source._collect_config().items() if k != "opt_dmin"}
    fresh.opt_panel.edit_dmin.setValue(12.5)

    fresh._apply_config(old)

    assert fresh.opt_panel.edit_dmin.value() == 12.5
