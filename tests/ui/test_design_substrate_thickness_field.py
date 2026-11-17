"""Chantier 47: the substrate thickness field of DESIGN (mm), saved, loaded, and read by the runs in nm.

At 1 mm (the default and the value of every file before the field) the configuration does not write it, so those
files keep their bytes; another value is written, loaded back, and reaches what the window gives its workers.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "substrate thickness field", main_windows_only=True)


def test_one_millimetre_is_not_written_and_another_value_comes_back(qapp) -> None:
    from certus.ui.certus_design_ui import CertusDesignApp

    source, fresh = CertusDesignApp(), CertusDesignApp()
    assert source.sub_thickness_mm_spin.value() == 1.0
    assert "substrate_thickness_mm" not in source._collect_config()

    source.sub_thickness_mm_spin.setValue(2.5)
    cfg = source._collect_config()
    assert cfg["substrate_thickness_mm"] == 2.5

    fresh._apply_config(cfg)
    assert fresh.sub_thickness_mm_spin.value() == 2.5

    fresh._apply_config({k: v for k, v in cfg.items() if k != "substrate_thickness_mm"})
    assert fresh.sub_thickness_mm_spin.value() == 1.0  # a file without the key is a file at 1 mm


def test_the_window_gives_its_runs_the_thickness_in_nanometres(qapp) -> None:
    from certus.core.certus_design_worker_utils import design_substrate_thickness_nm
    from certus.physics.certus_substrate_absorption import DEFAULT_SUBSTRATE_THICKNESS_NM
    from certus.ui.certus_design_ui import CertusDesignApp

    window = CertusDesignApp()
    assert design_substrate_thickness_nm(window) == DEFAULT_SUBSTRATE_THICKNESS_NM
    window.sub_thickness_mm_spin.setValue(2.5)
    assert design_substrate_thickness_nm(window) == 2.5e6
    assert design_substrate_thickness_nm(object()) == DEFAULT_SUBSTRATE_THICKNESS_NM
