"""Chantier 47: the substrate thickness field of RE (mm), saved, loaded, and given to the run in nm.

At 1 mm (the default and the value of every file before the field) the configuration does not write it, so those
files keep their bytes; another value is written, loaded back, and reaches the worker's configuration.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def re_window(qapp):
    from CERTUS_RE import CertusREApp

    win = CertusREApp()
    win.load_reverse_engineering_from_path("example/example_RE/reverse_sample.xlsx")
    yield win
    win.close()


def test_one_millimetre_is_not_written_and_another_value_comes_back(qapp) -> None:
    from CERTUS_RE import CertusREApp

    source, fresh = CertusREApp(), CertusREApp()
    try:
        assert source.sub_thickness_mm_spin.value() == 1.0
        assert "substrate_thickness_mm" not in source._collect_config()["re_gui"]
        source.sub_thickness_mm_spin.setValue(2.5)
        cfg = source._collect_config()
        assert cfg["re_gui"]["substrate_thickness_mm"] == 2.5
        fresh._apply_re_config(cfg)
        assert fresh.sub_thickness_mm_spin.value() == 2.5
    finally:
        source.close()
        fresh.close()


def test_the_run_receives_the_thickness_in_nanometres(re_window) -> None:
    assert re_window.build_re_worker_cfg()["substrate_thickness_nm"] == 1.0e6
    re_window.sub_thickness_mm_spin.setValue(2.5)
    assert re_window.build_re_worker_cfg()["substrate_thickness_nm"] == 2.5e6
