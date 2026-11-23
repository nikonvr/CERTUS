"""DESIGN in immersion (2026-11-23): the incident-medium field, saved and loaded, and the spectrum it gives.

At n = 1 (air, the default and the value of every file before the field) the configuration does not write the field,
so those files keep their bytes. The example of the OIC 2025 contest, Problem B.1, lights the coating from a cube of
index 1.80 at 45 degrees: the spectrum DESIGN shows for it, at the true wavelengths, must be the one the independent
oracle computes in the cube; the score button must give the contest score.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "example" / "example_design" / "JSON-design-OIC2025-B1.json"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "incident medium field", main_windows_only=True)


def test_air_is_not_written_and_another_index_comes_back(qapp) -> None:
    from certus.ui.certus_design_ui import CertusDesignApp

    source, fresh = CertusDesignApp(), CertusDesignApp()
    assert source.incident_index_spin.value() == 1.0
    assert "incident_index" not in source._collect_config()

    source.incident_index_spin.setValue(1.8)
    cfg = source._collect_config()
    assert cfg["incident_index"] == 1.8
    fresh._apply_config(cfg)
    assert fresh.incident_index_spin.value() == 1.8

    fresh._apply_config({k: v for k, v in cfg.items() if k != "incident_index"})
    assert fresh.incident_index_spin.value() == 1.0  # a file without the key is lit from air


def _evaluate(window):
    from certus.core.certus_design_immersion import immerse_design_cfg, incident_index_of
    from certus.ui.certus_spectrum_eval_ui import spectrum_eval_build_worker_cfg
    from certus.workers.certus_spectral_workers import EvalWorker

    cfg = spectrum_eval_build_worker_cfg(window, "design")
    out: dict = {}
    worker = EvalWorker(immerse_design_cfg(cfg, incident_index_of(window)))
    worker.signals.finished.connect(out.update)
    worker.run()
    return cfg, out


def test_the_spectrum_shown_in_immersion_is_the_oracle_spectrum_in_the_cube(qapp) -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "oracle"))
    from tmm_reference import rt_stack_oblique

    from certus.ui.certus_design_ui import CertusDesignApp

    window = CertusDesignApp()
    window._apply_config(json.loads(EXAMPLE.read_text(encoding="utf-8")))
    assert window.incident_index_spin.value() == pytest.approx(1.8)
    cfg, out = _evaluate(window)

    lam = np.asarray(out["vis"]["l"], dtype=float)
    assert lam == pytest.approx(np.asarray(cfg["wls_vis"], dtype=float), rel=1e-12)  # true wavelengths come back
    assert out["oblique_tgts"][0].lmin == pytest.approx(cfg["oblique_tgts"][0].lmin)  # true bands come back
    n = np.array([cfg["mats"][layer.mat].get_nk(np.array([550.0]))[0] for layer in cfg["stack"]], dtype=complex)
    d = np.asarray(cfg["ep"], dtype=float)
    spectra = {key[:2]: value for key, value in out["spectra_vis"].items()}
    for i in np.linspace(0, lam.size - 1, 7).astype(int):
        for pol in ("s", "p"):
            r_ref, t_ref = rt_stack_oblique(float(lam[i]), n, d, 45.0, pol == "s", n_inc=1.8, n_sub=1.8)
            assert spectra[45.0, pol]["T"][i] == pytest.approx(t_ref, abs=1e-10)
            assert spectra[45.0, pol]["R"][i] == pytest.approx(r_ref, abs=1e-10)


def test_the_back_side_is_refused_in_immersion(qapp) -> None:
    from certus.core.certus_design_immersion import immerse_design_cfg, incident_index_of
    from certus.ui.certus_design_ui import CertusDesignApp
    from certus.ui.certus_spectrum_eval_ui import spectrum_eval_build_worker_cfg

    window = CertusDesignApp()
    window._apply_config(json.loads(EXAMPLE.read_text(encoding="utf-8")))
    window.back_check.setChecked(True)
    with pytest.raises(ValueError, match="back side"):
        immerse_design_cfg(spectrum_eval_build_worker_cfg(window, "design"), incident_index_of(window))


def test_the_score_button_gives_the_contest_score(qapp) -> None:
    from certus.core.certus_contest_scores import oic2025_b1_score
    from certus.ui.certus_design_contest_score import oic2025_b1_report
    from certus.ui.certus_design_ui import CertusDesignApp

    window = CertusDesignApp()
    window._apply_config(json.loads(EXAMPLE.read_text(encoding="utf-8")))
    line = oic2025_b1_report(window)
    stack = window._get_front_stack()
    score, legal = oic2025_b1_score(window._get_materials(), [s.mat for s in stack], np.asarray(window.ep_current))
    assert line is not None
    assert f"{score.total:.6f}" in line
    assert ("within the contest rules" in line) is legal
