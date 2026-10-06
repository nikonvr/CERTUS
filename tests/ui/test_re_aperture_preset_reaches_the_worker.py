"""The beam-aperture choice of RE reaches the worker, survives a saved configuration and resets to fitted.

    DEFAULT: fitted, and the worker configuration carries no imposed aperture (the path of before, bit for bit)
    PHOTON RT: the worker configuration carries 2.0 deg total
    SAVED AND RESTORED with the RE preferences; RESET brings back the fitted aperture
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


def _choose(win, key: str) -> None:
    win.re_aperture_combo.setCurrentIndex(win.re_aperture_combo.findData(key))


def test_by_default_the_aperture_is_fitted(re_window):
    assert re_window.re_aperture_combo.currentData() == "fitted"
    assert "re_beam_aperture_imposed_deg" not in re_window.build_re_worker_cfg()


def test_the_photon_rt_preset_reaches_the_worker_and_fitted_takes_it_back(re_window):
    _choose(re_window, "photon_rt_5200")
    assert re_window.build_re_worker_cfg()["re_beam_aperture_imposed_deg"] == 2.0
    _choose(re_window, "fitted")
    assert "re_beam_aperture_imposed_deg" not in re_window.build_re_worker_cfg()


def test_the_choice_is_saved_and_restored(re_window):
    _choose(re_window, "photon_rt_5200")
    saved = re_window._collect_config()["re_gui"]
    assert saved["re_beam_aperture"] == "photon_rt_5200"
    _choose(re_window, "fitted")
    re_window._re_apply_gui_prefs_from_dict(saved)
    assert re_window.re_aperture_combo.currentData() == "photon_rt_5200"
    assert re_window.cfg["re_beam_aperture_imposed_deg"] == 2.0


def test_reset_brings_back_the_fitted_aperture(re_window):
    _choose(re_window, "photon_rt_5200")
    re_window._load_defaults()
    assert re_window.re_aperture_combo.currentData() == "fitted"
    assert "re_beam_aperture_imposed_deg" not in re_window.cfg
