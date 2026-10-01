"""
QSettings contract for session persistence (INDEX SPLINE step 3, classic INDEX wT/wR).

The settings go to an INI file under tmp_path, never to the registry: certus_settings honours
CERTUS_CONFIG_DIR. Until 2026-09-27 this file set `QSettings.setPath(IniFormat, ...)`, which the
(organization, application) constructor ignores -- each run rewrote the user's INDEX SPLINE
fit options in the registry.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from certus.utils.certus_qsettings import certus_settings


def _as_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() in ("true", "1", "yes", "on")
    return bool(v)


@pytest.fixture
def isolated_qsettings_path(tmp_path, monkeypatch):
    monkeypatch.setenv("CERTUS_CONFIG_DIR", str(tmp_path))
    return tmp_path


def test_spline_spectrum_step3_keys_roundtrip(isolated_qsettings_path):
    from CERTUS_INDEX_SPLINE import (
        _QS_SPECTRUM_FIT_R,
        _QS_SPECTRUM_FIT_T,
        _QS_SPECTRUM_FIT_TREL,
        _QS_SPECTRUM_WR,
        _QS_SPECTRUM_WT,
        _QS_SPLINE_APP,
        _QS_SPLINE_ORG,
    )

    s = certus_settings(_QS_SPLINE_ORG, _QS_SPLINE_APP)
    assert Path(s.fileName()).is_relative_to(isolated_qsettings_path), s.fileName()
    s.setValue(_QS_SPECTRUM_FIT_T, False)
    s.setValue(_QS_SPECTRUM_FIT_TREL, True)
    s.setValue(_QS_SPECTRUM_FIT_R, True)
    s.setValue(_QS_SPECTRUM_WT, 0.3)
    s.setValue(_QS_SPECTRUM_WR, 0.7)
    s.sync()

    s2 = certus_settings(_QS_SPLINE_ORG, _QS_SPLINE_APP)
    assert _as_bool(s2.value(_QS_SPECTRUM_FIT_T)) is False
    assert _as_bool(s2.value(_QS_SPECTRUM_FIT_TREL)) is True
    assert _as_bool(s2.value(_QS_SPECTRUM_FIT_R)) is True
    assert float(s2.value(_QS_SPECTRUM_WT)) == pytest.approx(0.3)
    assert float(s2.value(_QS_SPECTRUM_WR)) == pytest.approx(0.7)


def test_index_classic_weight_keys_roundtrip(isolated_qsettings_path):
    from certus.ui.certus_index_ui_state import _QS_INDEX_APP, _QS_INDEX_ORG, _QS_INDEX_WEIGHT_R, _QS_INDEX_WEIGHT_T

    s = certus_settings(_QS_INDEX_ORG, _QS_INDEX_APP)
    assert Path(s.fileName()).is_relative_to(isolated_qsettings_path), s.fileName()
    s.setValue(_QS_INDEX_WEIGHT_T, 0.25)
    s.setValue(_QS_INDEX_WEIGHT_R, 0.75)
    s.sync()

    s2 = certus_settings(_QS_INDEX_ORG, _QS_INDEX_APP)
    assert float(s2.value(_QS_INDEX_WEIGHT_T)) == pytest.approx(0.25)
    assert float(s2.value(_QS_INDEX_WEIGHT_R)) == pytest.approx(0.75)
