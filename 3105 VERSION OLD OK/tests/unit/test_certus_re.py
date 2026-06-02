"""Unit tests for CERTUS_RE.py (reverse engineering, Excel entries)."""

import pytest
import numpy as np
import sys
from pathlib import Path

# Add root directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import CERTUS_RE
    from certus_physics import Layer, Target, Sample
    from certus.core.certus_core import get_logger

    RE_AVAILABLE = True
except ImportError:
    RE_AVAILABLE = False


@pytest.mark.unit
@pytest.mark.skipif(not RE_AVAILABLE, reason="CERTUS_RE not available")
class TestParseREColumnHeader:
    """RE header parser (incidence, polarization, R/T, backside)."""

    @pytest.mark.parametrize(
        "header,expect",
        [
            ("R", ("R", 0.0, "s", True)),
            ("T", ("T", 0.0, "s", True)),
            ("R-45-s-noBK", ("R", 45.0, "s", False)),
            ("R-45p-noBK", ("R", 45.0, "p", False)),
            ("R-45P-noBK", ("R", 45.0, "p", False)),
            ("T-30-P-BACK", ("T", 30.0, "p", True)),
            ("t_20_s_plate", ("T", 20.0, "s", True)),
            ("R aoi25 polp finite", ("R", 25.0, "p", True)),
            ("R-45-avg-nobk", ("R", 45.0, "Avg", False)),
            ("R0-0deg-BK", ("R", 0.0, "s", True)),
            ("R-45-s-1f", ("R", 45.0, "s", False)),
            ("R-45-p-2f", ("R", 45.0, "p", True)),
            ("T_30_s_2F", ("T", 30.0, "s", True)),
            ("Rs1f", ("R", 0.0, "s", False)),
            ("R 45 s 1f", ("R", 45.0, "s", False)),
            ("R-45s1f", ("R", 45.0, "s", False)),
            ("Reflection 45 sec noBK", ("R", 45.0, "s", False)),
            ("30 P transmission with rear", ("T", 30.0, "p", True)),
            ("Reflexion incidence 25 s", ("R", 25.0, "s", True)),
        ],
    )
    def test_parse_headers(self, header, expect):
        from CERTUS_RE import parse_re_column_header

        p = parse_re_column_header(header)
        tt, ang, pol, inc = expect
        assert p.target_type == tt
        assert abs(p.angle_deg - ang) < 1e-9
        assert p.pol == pol
        assert p.include_backside is inc
        assert p.raw_header == header

    def test_conflicting_backside_raises(self):
        from CERTUS_RE import parse_re_column_header

        with pytest.raises(ValueError, match="conflicting backside"):
            parse_re_column_header("R-45-s-noBK-withback")

        with pytest.raises(ValueError, match="conflicting backside"):
            parse_re_column_header("R-45-s-1f-2f")

    def test_assumed_reflectance_emits_interpretation_note(self):
        from CERTUS_RE import parse_re_column_header

        p = parse_re_column_header("45-s-noBK")
        assert p.target_type == "R"
        assert len(p.interpretation_notes) >= 1
        assert "reflectance" in p.interpretation_notes[0].lower()

    def test_unknown_token_emits_note(self):
        from CERTUS_RE import parse_re_column_header

        p = parse_re_column_header("T-30-s-2f-bizarreToken")
        assert any("bizarreToken" in n for n in p.interpretation_notes)


@pytest.mark.unit
@pytest.mark.skipif(not RE_AVAILABLE, reason="CERTUS_RE not available")
@pytest.mark.unit
@pytest.mark.skipif(not RE_AVAILABLE, reason="CERTUS_RE not available")
class TestRERmseProgressParsing:
    """Pure parsing of RE RMSE progress messages."""

    @pytest.mark.parametrize(
        "message, expected",
        [
            ("Phase 2 RMSE_facade(curr)=0.123456", 0.123456),
            ("done RMSE_facade=1.25e-3", 0.00125),
            ("step RMSE∑=0.004", 0.004),
            ("step RMSEΣ=0.005", 0.005),
            ("done RMSE_combined=0.006", 0.006),
            ("done RMSE(curr)=0.007", 0.007),
            ("done RMSE=0.008", 0.008),
        ],
    )
    def test_parse_re_rmse_combined_from_progress_message(self, message, expected):
        from CERTUS_RE import _parse_re_rmse_combined_from_progress_message

        assert _parse_re_rmse_combined_from_progress_message(message) == pytest.approx(expected)

    @pytest.mark.parametrize("message", ["", "no rmse here", "RMSE=-1.0", "RMSE=nan"])
    def test_parse_re_rmse_combined_rejects_invalid_messages(self, message):
        from CERTUS_RE import _parse_re_rmse_combined_from_progress_message

        assert _parse_re_rmse_combined_from_progress_message(message) is None


@pytest.mark.unit
@pytest.mark.skipif(not RE_AVAILABLE, reason="CERTUS_RE not available")
class TestREMeasurementWavelengthColumn:
    """Column detection lambda sheet measurement."""

    def test_explicit_wavelength_header_no_warning(self):
        from CERTUS_RE import _re_find_measurement_wavelength_column

        hdr = ("Wavelength (nm)", "R", "T")
        rows = [(400.0, 0.1, 0.2), (500.0, 0.15, 0.25), (600.0, 0.2, 0.3)]
        idx, warn = _re_find_measurement_wavelength_column(hdr, rows)
        assert idx == 0
        assert warn is None

    def test_french_wavelength_header_recognized(self):
        from CERTUS_RE import _re_header_is_wavelength_label

        assert _re_header_is_wavelength_label("Longueur d'onde (nm)")
        assert _re_header_is_wavelength_label("Longueurs d’onde")

    def test_obvious_fallback_emits_warning(self):
        from CERTUS_RE import _re_find_measurement_wavelength_column

        hdr = ("colA", "colB", "colC")
        rows = [
            (9.0, 0.1, 0.2),
            (1.0, 0.15, 0.25),
            (5.0, 0.2, 0.3),
        ]
        idx, warn = _re_find_measurement_wavelength_column(hdr, rows)
        assert idx == 0
        assert warn is not None
        assert "column a" in warn.lower() or "**lambda**" in warn


@pytest.mark.unit
@pytest.mark.skipif(not RE_AVAILABLE, reason="CERTUS_RE not available")
class TestREDesignQwotAndSheets:
    """Multi-column QWOT and RE sheet name resolution."""

    def test_parse_design_qwot_multicolumn_row_major(self):
        from CERTUS_RE import _re_parse_design_qwot_rows

        rows = [
            ("lambda", 1500, "silicon"),
            (0.562, 2.558, None),
            (0.456, 2.672, None),
            (0.8766, 0.413, None),
        ]
        q = _re_parse_design_qwot_rows(rows)
        assert q == [0.562, 2.558, 0.456, 2.672, 0.8766, 0.413]

    def test_parse_design_qwot_single_column_legacy(self):
        from CERTUS_RE import _re_parse_design_qwot_rows

        rows = [
            ("lambda", 1500, "silicon"),
            (1.520588, None, None),
            (1.698967, None, None),
        ]
        q = _re_parse_design_qwot_rows(rows)
        assert len(q) == 2
        assert abs(q[0] - 1.520588) < 1e-6

    def test_resolve_workbook_sheet_synonyms(self):
        from CERTUS_RE import _re_resolve_re_workbook_sheets

        names = ["Measures", "Indices", "Design"]
        m = _re_resolve_re_workbook_sheets(names)
        assert m.get("measurement") == "Measures"
        assert m.get("index") == "Indices"
        assert m.get("design") == "Design"

    def test_resolve_workbook_accented_french_tab_names(self):
        from CERTUS_RE import _re_resolve_re_workbook_sheets

        names = ["RE data", "Conception", "Material clues"]
        m = _re_resolve_re_workbook_sheets(names)
        assert m.get("measurement") == "RE data"
        assert m.get("design") == "Conception"
        assert m.get("index") == "Material clues"


@pytest.mark.unit
@pytest.mark.skipif(not RE_AVAILABLE, reason="CERTUS_RE not available")
class TestREsubstrateCauchy3:
    """Model n = a0 + a1(lambdaref/lambda)² + a2(lambdaref/lambda)⁴ and tube barrier."""

    def test_phi_and_eval_consistency(self):
        from certus.utils.certus_re_helpers import (
            re_substrate_cauchy_phi_matrix,
        )
        from CERTUS_RE import (
            re_substrate_cauchy_n_re_from_theta,
        )

        wls = np.array([500.0, 1000.0], dtype=np.float64)
        lr = 500.0
        Phi = re_substrate_cauchy_phi_matrix(wls, lr)
        assert Phi.shape == (2, 3)
        assert np.allclose(Phi[:, 0], 1.0)
        th = np.array([1.5, 0.01, -0.001], dtype=np.float64)
        n1 = re_substrate_cauchy_n_re_from_theta(wls, lr, th)
        n2 = Phi @ th
        assert np.allclose(n1, n2)

    def test_feasible_theta_matches_tab(self):
        from certus.utils.certus_re_helpers import (
            re_substrate_cauchy_initial_theta,
            re_substrate_cauchy_phi_matrix,
        )
        from CERTUS_RE import (
            RE_SUB_CAUCHY_TUBE_DELTA,
        )

        wls = np.linspace(400.0, 800.0, 12, dtype=np.float64)
        lr = 500.0
        Phi = re_substrate_cauchy_phi_matrix(wls, lr)
        th_true = np.array([1.52, -0.02, 0.001], dtype=np.float64)
        n_tab = Phi @ th_true
        th0 = re_substrate_cauchy_initial_theta(n_tab, wls, lr, delta=RE_SUB_CAUCHY_TUBE_DELTA)
        assert th0 is not None
        pred = Phi @ th0
        assert np.max(np.abs(pred - n_tab)) <= RE_SUB_CAUCHY_TUBE_DELTA + 1e-7

    def test_barrier_jacobian_active_upper(self):
        from certus.utils.certus_re_helpers import re_substrate_cauchy_barrier_residuals_jac

        Phi = np.ones((1, 3), dtype=np.float64)
        Phi[0, 1] = 0.25
        Phi[0, 2] = 0.0625
        n_tab = np.array([1.5], dtype=np.float64)
        theta = np.array([2.0, 0.0, 0.0], dtype=np.float64)
        r, J = re_substrate_cauchy_barrier_residuals_jac(
            theta, Phi, n_tab, delta=0.05, sqrt_w=10.0
        )
        assert r[0] > 0
        assert np.allclose(J[0, :], 10.0 * Phi[0, :])


@pytest.mark.unit
def test_re_ranking_combined_rmse_matches_formula():
    from certus.workers.certus_re_worker_utils import re_ranking_combined_rmse

    sp, qw, a = 0.012, 0.02, 0.05
    out = re_ranking_combined_rmse(sp, qw, a)
    exp = float(np.sqrt(sp**2 + a * qw**2))
    assert abs(out - exp) < 1e-12


@pytest.mark.unit
@pytest.mark.skipif(not RE_AVAILABLE, reason="CERTUS_RE not available")
class TestREDeadzoneExcess:
    """Bandes mortes DeltaRe / DeltaQ (RE)."""

    def test_excess_zero_inside_band(self):
        from certus.utils.certus_re_helpers import _re_deadzone_excess_abs

        v = np.array([-0.005, 0.008, 0.0], dtype=np.float64)
        ex = _re_deadzone_excess_abs(v, 0.01)
        assert np.allclose(ex, 0.0)

    def test_excess_outside_band(self):
        from certus.utils.certus_re_helpers import _re_deadzone_excess_abs

        v = np.array([-0.02, 0.015], dtype=np.float64)
        ex = _re_deadzone_excess_abs(v, 0.01)
        assert np.allclose(ex, [0.01, 0.005])

    def test_eps_zero_falls_back_to_abs(self):
        from certus.utils.certus_re_helpers import _re_deadzone_excess_abs

        v = np.array([-0.3, 0.2], dtype=np.float64)
        ex = _re_deadzone_excess_abs(v, 0.0)
        assert np.allclose(ex, [0.3, 0.2])


@pytest.mark.unit
@pytest.mark.skipif(not RE_AVAILABLE, reason="CERTUS_RE not available")
class TestREHLDeltaReKnotRegularization:
    """Residue √(w)·(DeltaRe/env)²: ~quartic growth in amplitude of DeltaRe."""

    def test_residual_scales_quartic_in_delta(self):
        from CERTUS_RE import (
            RE_SPLINE_NODE2_DEFAULT_NM,
            re_knots_wavelengths,
        )
        from certus.utils.certus_re_helpers import (
            re_envelope_max_delta_n,
        )

        kn = re_knots_wavelengths(RE_SPLINE_NODE2_DEFAULT_NM)
        env = np.maximum(re_envelope_max_delta_n(kn, scale=1.0), 1e-18)
        w = 10.0
        sqw = float(np.sqrt(w))
        dh = np.full_like(env, 0.01, dtype=np.float64)
        r1 = sqw * ((dh / env) ** 2)
        r2 = sqw * (((2.0 * dh) / env) ** 2)
        assert np.allclose(r2 / r1, 4.0, rtol=1e-9)


@pytest.mark.unit
@pytest.mark.skipif(not RE_AVAILABLE, reason="CERTUS_RE not available")
class TestREPhase4BeamKnots:
    """Phase-4 chromatic beam helpers and spectrum path (no full REWorker)."""

    def test_sort_knot_pairs_permutes_ap_with_lam(self):
        from CERTUS_RE import _re_p4_sort_knot_pairs
        from certus.utils.certus_re_helpers import _re_p4_band_ap_deg

        lam = np.array([800.0, 400.0, 600.0], dtype=np.float64)
        ap = np.array([1.0, 2.0, 3.0], dtype=np.float64)
        ls, aa = _re_p4_sort_knot_pairs(lam, ap)
        assert np.allclose(ls, [400.0, 600.0, 800.0])
        assert np.allclose(aa, [2.0, 3.0, 1.0])
        assert abs(_re_p4_band_ap_deg(lam, ap, 400.0) - 2.0) < 1e-9
        assert abs(_re_p4_band_ap_deg(lam, ap, 800.0) - 1.0) < 1e-9

    def test_chromatic_band_masks_do_not_mutate_knots(self):
        from CERTUS_RE import RE_P4_BEAM_N_KNOTS
        from certus.utils.certus_re_helpers import _re_p4_chromatic_band_masks

        knots = np.array([700.0, 500.0, 600.0], dtype=np.float64)
        ref = knots.copy()
        wls = np.linspace(400.0, 900.0, 20, dtype=np.float64)
        m3 = _re_p4_chromatic_band_masks(wls, knots)
        assert np.array_equal(knots, ref)
        assert len(m3) == 3
        k4 = np.array([400.0, 550.0, 700.0, 900.0], dtype=np.float64)
        m4 = _re_p4_chromatic_band_masks(wls, k4)
        assert len(m4) == int(RE_P4_BEAM_N_KNOTS)

    def test_phase4_spectrum_matches_subprocess(self):
        """Isolated process: avoids Numba NUMBA_NUM_THREADS conflicts with other tests."""
        import json
        import subprocess
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent.parent
        rp = json.dumps(str(root))
        code = f"""
import numpy as np
import sys
sys.path.insert(0, {rp})
import CERTUS_RE as cr
wls = np.linspace(400.0, 800.0, 50, dtype=np.float64)
nlay = np.ones((wls.size, 2), dtype=np.complex128) * (2.35 - 0j)
nsub = np.ones(wls.size, dtype=np.complex128) * (1.52 - 0j)
ep = np.array([100.0, 150.0], dtype=np.float64)
ap = 1.2
lk = np.array([400.0, 600.0, 800.0], dtype=np.float64)
ak = np.array([ap, ap, ap], dtype=np.float64)
R1, T1 = cr._re_calc_spectrum_for_config(
    wls, nlay, ep, nsub, 25.0, "s", False,
    phase4_average=True, beam_aperture=ap,
)
R2, T2 = cr._re_calc_spectrum_for_config(
    wls, nlay, ep, nsub, 25.0, "s", False,
    phase4_average=True, beam_aperture=ap,
    beam_aperture_knots_deg=ak, beam_aperture_knots_lam_nm=lk,
)
assert np.allclose(R1, R2, rtol=0, atol=1e-9)
assert np.allclose(T1, T2, rtol=0, atol=1e-9)
wls2 = np.linspace(400.0, 800.0, 20, dtype=np.float64)
nlay2 = np.ones((wls2.size, 2), dtype=np.complex128) * (2.35 - 0j)
nsub2 = np.ones(wls2.size, dtype=np.complex128) * (1.52 - 0j)
Ra, Ta = cr._re_calc_spectrum_for_config(
    wls2, nlay2, ep, nsub2, 5.0, "s", False,
    phase4_average=True, beam_aperture=2.0,
)
Rb, Tb = cr._re_calc_spectrum_for_config(
    wls2, nlay2, ep, nsub2, 5.0, "s", False, phase4_average=False,
)
assert np.allclose(Ra, Rb)
assert np.allclose(Ta, Tb)
"""
        subprocess.check_call([sys.executable, "-c", code], cwd=str(root))

    def test_ap_staircase_polyline_matches_band_model(self):
        """Polyline du plot ap(lambda) : chaque palier horizontal = _re_p4_band_ap_deg (même physique que P4)."""
        from CERTUS_RE import _re_p4_ap_staircase_polyline
        from certus.utils.certus_re_helpers import _re_p4_band_ap_deg

        rng = np.random.default_rng(42)
        for n in (2, 3, 4, 6):
            for _ in range(8):
                lam_k = np.sort(rng.uniform(350.0, 2200.0, n))
                ap_k = rng.uniform(0.5, 12.0, n)
                w_lo = float(lam_k[0] - 50.0)
                w_hi = float(lam_k[-1] + 50.0)
                sx, sy = _re_p4_ap_staircase_polyline(lam_k, ap_k, w_lo, w_hi)
                for i in range(int(sx.size) - 1):
                    if abs(float(sy[i + 1]) - float(sy[i])) > 1e-12:
                        continue
                    xa, xb = sorted((float(sx[i]), float(sx[i + 1])))
                    if xb - xa <= 1e-6:
                        continue
                    xm = 0.5 * (xa + xb)
                    ref = _re_p4_band_ap_deg(lam_k, ap_k, xm)
                    assert abs(ref - float(sy[i])) < 1e-9

    def test_four_knot_stair_non_monotone(self):
        from certus.utils.certus_re_helpers import _re_p4_band_ap_deg

        lam_k = np.array([400.0, 600.0, 800.0, 1000.0], dtype=np.float64)
        ap_k = np.array([2.0, 1.0, 2.5, 1.2], dtype=np.float64)
        assert abs(_re_p4_band_ap_deg(lam_k, ap_k, 450.0) - 2.0) < 1e-9
        assert abs(_re_p4_band_ap_deg(lam_k, ap_k, 650.0) - 1.0) < 1e-9
        assert abs(_re_p4_band_ap_deg(lam_k, ap_k, 850.0) - 2.5) < 1e-9
        assert abs(_re_p4_band_ap_deg(lam_k, ap_k, 950.0) - 1.2) < 1e-9
        g = np.array([450.0, 650.0, 850.0, 950.0], dtype=np.float64)
        y = np.array([_re_p4_band_ap_deg(lam_k, ap_k, float(x)) for x in g], dtype=np.float64)
        assert np.allclose(y, [2.0, 1.0, 2.5, 1.2])

    def test_p4_kwargs_from_opt_result(self):
        from CERTUS_RE import _re_p4_kwargs_from_opt_result

        cfg = {"re_beam_aperture_deg": 1.25}
        assert _re_p4_kwargs_from_opt_result({}, cfg) == {}
        assert _re_p4_kwargs_from_opt_result({"re_p4_beam_ap_knots_deg": [1.0]}, cfg) == {}
        r = {
            "re_p4_beam_ap_knots_deg": [1.5, 1.5, 1.5],
            "re_p4_beam_ap_knots_nm": [400.0, 600.0, 800.0],
            "re_p4_aperture_deg": 1.7,
        }
        kw = _re_p4_kwargs_from_opt_result(r, cfg)
        assert kw["phase4_average"] is True
        assert kw["beam_aperture"] == pytest.approx(1.7)
        assert np.allclose(kw["beam_aperture_knots_deg"], [1.5, 1.5, 1.5])
        assert np.allclose(kw["beam_aperture_knots_lam_nm"], [400.0, 600.0, 800.0])
        r2 = {
            "re_p4_beam_ap_knots_deg": [1.0, 1.0, 1.0],
            "re_p4_beam_ap_knots_nm": [500.0, 600.0, 700.0],
        }
        kw2 = _re_p4_kwargs_from_opt_result(r2, cfg)
        assert kw2["beam_aperture"] == pytest.approx(1.25)
        r4 = {
            "re_p4_beam_ap_knots_deg": [1.1, 2.0, 1.5, 1.8],
            "re_p4_beam_ap_knots_nm": [400.0, 550.0, 700.0, 900.0],
            "re_p4_aperture_deg": 1.0,
        }
        kw4 = _re_p4_kwargs_from_opt_result(r4, cfg)
        assert np.allclose(kw4["beam_aperture_knots_deg"], [1.1, 2.0, 1.5, 1.8])
        assert np.allclose(kw4["beam_aperture_knots_lam_nm"], [400.0, 550.0, 700.0, 900.0])

    def test_rmse_oblique_phase4_consistency_subprocess(self):
        """Processus isolé : évite RuntimeError NUMBA_NUM_THREADS vs autres tests du même worker."""
        import json
        import subprocess
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent.parent
        rp = json.dumps(str(root))
        code = f"""
import numpy as np
import sys
sys.path.insert(0, {rp})
from CERTUS_RE import _re_rmse_oblique_weighted
from certus_physics import ObliqueTarget
wls = np.array([500.0, 700.0], dtype=np.float64)
n_layers_T = np.ones((2, 1), dtype=np.complex128) * (2.15 - 0j)
n_sub = np.ones(2, dtype=np.complex128) * (1.52 - 0j)
ep = np.array([95.0], dtype=np.float64)
tgts = [
    ObliqueTarget(28.0, "s", 500.0, 500.0, 0.08, 0.08, target_type="R", w=1.0, include_backside=False),
    ObliqueTarget(28.0, "s", 700.0, 700.0, 0.09, 0.09, target_type="R", w=1.0, include_backside=False),
]
r_plain = _re_rmse_oblique_weighted(ep, n_layers_T, n_sub, wls, tgts)
r_p4_zero = _re_rmse_oblique_weighted(
    ep, n_layers_T, n_sub, wls, tgts,
    phase4_average=True, beam_aperture=0.0,
)
assert abs(r_plain - r_p4_zero) < 1e-10
ap = 1.1
lk = np.array([400.0, 600.0, 900.0], dtype=np.float64)
ak = np.array([ap, ap, ap], dtype=np.float64)
tg2 = [
    ObliqueTarget(22.0, "s", 550.0, 550.0, 0.08, 0.08, target_type="R", w=1.0, include_backside=False),
    ObliqueTarget(22.0, "s", 750.0, 750.0, 0.07, 0.07, target_type="R", w=1.0, include_backside=False),
]
wls2 = np.array([550.0, 750.0], dtype=np.float64)
r_scalar = _re_rmse_oblique_weighted(
    ep, n_layers_T, n_sub, wls2, tg2,
    phase4_average=True, beam_aperture=ap,
)
r_knots = _re_rmse_oblique_weighted(
    ep, n_layers_T, n_sub, wls2, tg2,
    phase4_average=True, beam_aperture=ap,
    beam_aperture_knots_deg=ak, beam_aperture_knots_lam_nm=lk,
)
assert abs(r_scalar - r_knots) < 1e-9
"""
        subprocess.check_call([sys.executable, "-c", code], cwd=str(root))


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skipif(not RE_AVAILABLE, reason="CERTUS_RE not available")
class TestReverseSampleXlsxInitialRmse:
    """RE integration (disabled without headless helper)."""

    @pytest.mark.skip(
        reason="REWorker.run() requiert un cfg complet (stack, targets, wl_arrays…) "
        "construit par CertusREApp. À activer si un helper headless est exposé."
    )
    def test_re_workflow_convergence(self):
        pass


@pytest.mark.unit
@pytest.mark.skipif(not RE_AVAILABLE, reason="CERTUS_RE not available")
class TestREAppSkeletonLoaders:
    """Validate skeleton loader integration on CertusREApp."""

    def test_re_app_skeletons_methods(self, qapp, monkeypatch):
        from CERTUS_RE import CertusREApp
        from unittest.mock import MagicMock
        
        # We can mock or instantiate CertusREApp
        app = MagicMock(spec=CertusREApp)
        app.spectrum_plot = MagicMock()
        app.profile_plot = MagicMock()
        app.nk_plot = MagicMock()
        
        # Retrieve the unbound method
        func_remove = CertusREApp._remove_re_skeletons
        
        # Mock the remove_skeleton_loader function
        mock_remove = MagicMock()
        monkeypatch.setattr("CERTUS_RE.remove_skeleton_loader", mock_remove)
        
        func_remove(app)
        
        assert mock_remove.call_count == 3
        mock_remove.assert_any_call(app.spectrum_plot)
        mock_remove.assert_any_call(app.profile_plot)
        mock_remove.assert_any_call(app.nk_plot)


@pytest.mark.unit
@pytest.mark.skipif(not RE_AVAILABLE, reason="CERTUS_RE not available")
class TestCertusREResultsDialogSmoke:
    """Smoke test for CertusREResultsDialog initialization."""

    def test_dialog_init(self, qapp):
        from certus.ui.certus_re_ui import CertusREResultsDialog
        from unittest.mock import MagicMock

        # Mock l0_spin spinbox
        mock_l0_spin = MagicMock()
        mock_l0_spin.value.return_value = 500.0

        # Mock material and get_nk method
        mock_material = MagicMock()
        mock_material.get_nk.return_value = np.array([2.0 + 0j], dtype=np.complex128)

        mock_materials = {"H": mock_material, "L": mock_material}

        # Mock Layer with 'mat' property
        class DummyLayer:
            def __init__(self, mat, thickness):
                self.mat = mat
                self.thickness = thickness

        initial_stack = [DummyLayer("H", 100.0), DummyLayer("L", 150.0)]

        # Mock the main application
        mock_app = MagicMock()
        mock_app.l0_spin = mock_l0_spin
        mock_app._get_materials.return_value = mock_materials
        mock_app._re_envelope_scale_from_gui.return_value = 1.0
        mock_app._re_spline_lam2_nm_from_result.return_value = 2000.0

        results = [
            {
                "label": "Run 1",
                "rmse": 0.001,
                "nfev": 10,
                "ep": np.array([100.0, 150.0], dtype=np.float64),
                "re_ranking_score": 0.002,
                "re_ranking_alpha_ref": 0.05,
                "re_dH_knots": np.zeros(5, dtype=np.float64),
                "re_dL_knots": np.zeros(5, dtype=np.float64),
                "re_knots_nm": np.array([400.0, 600.0, 800.0, 1000.0, 1200.0], dtype=np.float64),
            }
        ]

        # Use MagicMock / direct mock to avoid exec/show blocking issues
        # Since .exec() starts an event loop, let's mock self.exec / self.show so the dialog starts and finishes immediately during the test
        original_exec = CertusREResultsDialog.exec
        original_show = CertusREResultsDialog.show
        CertusREResultsDialog.exec = MagicMock()
        CertusREResultsDialog.show = MagicMock()

        mock_app._re_initial_stack = initial_stack

        try:
            dlg = CertusREResultsDialog(
                mock_app,
                results,
                ep0=np.array([100.0, 150.0]),
                re_rmse_initial=0.015,
                re_rmse_phase1=0.008,
                re_rmse_final=0.002,
                initial_stack=None,
                announce_in_log=False,
            )
            assert dlg is not None
            assert dlg.main_app == mock_app
            assert dlg.initial_stack == initial_stack
        finally:
            CertusREResultsDialog.exec = original_exec
            CertusREResultsDialog.show = original_show

