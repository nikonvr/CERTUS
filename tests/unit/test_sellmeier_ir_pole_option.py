"""Chantier 05: the SUBSTRATE Sellmeier fit can take an infrared pole (`sellmeier_ir_pole`, off by default).

Measured on 2026-11-17 (`reports/chantier05_2026-11-17/bilan.md`): variant A floors its denominators, so a pole beyond the
shortest wavelength is pinned at B = 0 and BK7 (IR pole at 10.18 um) stays at 2.9e-4 whatever the noise. The option adds
a catalog-form candidate: signed denominators, two UV poles below the window, one IR pole beyond it.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.core.certus_substrate_index import IndexCore
from certus.core.certus_substrate_sellmeier import _fit_model_sellmeier3poles, sellmeier_ir_pole_eval

B = (1.03961212, 0.231792344, 1.01046945)  # BK7, Schott
C = (0.00600069867, 0.0200179144, 103.560653)
WL = np.linspace(380.0, 1100.0, 361)
LU = WL / 1000.0
BK7 = np.sqrt(1.0 + sum(b * LU**2 / (LU**2 - c) for b, c in zip(B, C, strict=True)))


def _fit(n, **kw):
    mask = np.ones(n.size, dtype=bool)
    return _fit_model_sellmeier3poles(n, WL, mask, n, WL, LU, None, None, 300, 12, 3000, None, **kw)


def test_the_catalog_form_is_bk7_itself():
    bk7_as_ir = np.array([1.0, B[0], np.sqrt(C[0]), B[1], np.sqrt(C[1]), B[2], np.sqrt(C[2])])
    assert np.max(np.abs(sellmeier_ir_pole_eval(bk7_as_ir, LU) - BK7)) < 1e-13


def test_with_the_option_bk7_is_fitted_to_its_own_curve():
    curve, src, coeffs, _ = _fit(BK7, sellmeier_ir_pole=True)

    assert src == "analytic-sellmeier-3poles-ir"
    assert np.sqrt(np.mean((curve - BK7) ** 2)) < 1e-6  # 2.9e-4 without the option
    assert coeffs[6] > WL[-1] / 1000.0  # the third pole lies beyond the window


def test_without_the_option_the_fit_is_unchanged():
    off = _fit(BK7)
    explicit = _fit(BK7, sellmeier_ir_pole=False)

    assert off[1] == explicit[1] == "analytic-sellmeier-3term-standard"
    assert np.array_equal(off[0], explicit[0])


def test_the_option_reaches_the_fit_through_index_core():
    _n, meta = IndexCore.fit_sellmeier(BK7, WL, 380.0, 1100.0, model_kind="sellmeier3poles", return_meta=True,
                                       sellmeier_ir_pole=True)

    assert meta["source"] == "analytic-sellmeier-3poles-ir"


@pytest.mark.parametrize("helper", ["_clipboard_law_line_from_source", "_clipboard_coeffs_line_from_source"])
def test_the_new_source_is_described(helper):
    _curve, src, coeffs, _ = _fit(BK7, sellmeier_ir_pole=True)
    fn = getattr(IndexCore, helper)
    text = fn(src, coeffs) if helper == "_clipboard_coeffs_line_from_source" else fn(src, "sellmeier3poles")

    assert "L3" in text
    assert "non-analytical" not in text
    assert "unavailable" not in text
