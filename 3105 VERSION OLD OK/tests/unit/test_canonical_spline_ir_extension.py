"""INDEX SPLINE canonical sigma mesh tests (IR extension).





Context:


  • The 'standard' grid has 12 sigma nodes, spaced uniformly in log(sigma) over the spectral band.


  • When the spectrum exceeds 4000 nm (red edge strictly > threshold), we insert **two**


    additional nodes on the **last** wavelength segment (between the 2nd largest lambda and lambda_max),


    positioned at **wavelength thirds** - not in arithmetic sigma.





These tests guarantee:


  1) no change for lambda_max <= 4000 nm (bit-for-bit non-regression vs ``build_sigma_knots``);


  2) presence of the two expected sigma when lambda_max > 4000 nm;


  3) the threshold is **strict** (4000.0 nm exact -> no extension).


"""


from __future__ import annotations





import numpy as np





from certus.spline.certus_index_spline_core import (


    SPLINE_EXTRA_IR_KNOTS_LAM_MAX_THRESHOLD_NM,


    SPLINE_PWL_N_SEG,


    build_sigma_knots,


    canonical_spline_sigma_knots,


    min_relative_lambda_spacing_ratio,


)








def test_no_extension_when_lam_max_at_threshold() -> None:


    """lambda_max equal to the threshold: identical behavior to the 12-point grid (no K=14)."""


    hi = SPLINE_EXTRA_IR_KNOTS_LAM_MAX_THRESHOLD_NM


    sk = canonical_spline_sigma_knots(300.0, hi)


    sk_base = build_sigma_knots(300.0, hi, SPLINE_PWL_N_SEG)


    assert sk.shape == sk_base.shape


    assert np.allclose(sk, sk_base)








def test_no_extension_when_lam_max_below_threshold() -> None:


    """Short spectrum (typical unit tests): always 12 nodes, equal to build_sigma_knots."""


    sk = canonical_spline_sigma_knots(400.0, 800.0)


    assert int(sk.size) == 12


    sk_b = build_sigma_knots(400.0, 800.0, SPLINE_PWL_N_SEG)


    assert np.allclose(sk, sk_b)








def test_extension_two_equi_lambda_nodes_when_lam_max_above_threshold() -> None:


    """Long IR case: K=14 and the two added sigma coincide with 1/lambda for lambda at thirds on [lambda_pen, lambda_max]."""


    lam_lo, lam_hi = 250.0, 4800.0


    sk12 = build_sigma_knots(lam_lo, lam_hi, SPLINE_PWL_N_SEG)


    sk = canonical_spline_sigma_knots(lam_lo, lam_hi)


    assert int(sk.size) == 14


    s0, s1 = float(sk12[0]), float(sk12[1])


    lam_max = 1.0 / s0


    lam_pen = 1.0 / s1


    dlam = lam_max - lam_pen


    lam_a = lam_pen + dlam / 3.0


    lam_b = lam_pen + 2.0 * dlam / 3.0


    sa = 1.0 / lam_a


    sb = 1.0 / lam_b


    assert np.any(np.isclose(sk, sa, rtol=0, atol=5e-6))


    assert np.any(np.isclose(sk, sb, rtol=0, atol=5e-6))


    for v in sk12:


        assert np.any(np.isclose(sk, float(v), rtol=0, atol=5e-6))








def test_extension_threshold_strictly_greater_than_4000() -> None:


    """The trigger is a strict inequality: 4000 + ε -> 14 nodes; 4000.0 -> 12 nodes."""


    eps = 1e-6


    sk_plus = canonical_spline_sigma_knots(300.0, SPLINE_EXTRA_IR_KNOTS_LAM_MAX_THRESHOLD_NM + eps)


    assert int(sk_plus.size) == 14


    sk_eq = canonical_spline_sigma_knots(300.0, SPLINE_EXTRA_IR_KNOTS_LAM_MAX_THRESHOLD_NM)


    assert int(sk_eq.size) == 12








def test_min_delta_lambda_spacing_honoured_on_mesh() -> None:


    """Avec min Deltalambda/lambdā > 0, le maillage canonique respecte le ratio (et peut réduire K)."""


    lam_lo, lam_hi = 250.0, 4800.0


    req = 0.01


    sk = canonical_spline_sigma_knots(


        lam_lo, lam_hi, min_delta_lambda_over_lambda_mean=req


    )


    r = min_relative_lambda_spacing_ratio(sk, lam_lo, lam_hi)


    assert r >= req - 1e-12








def test_min_delta_aggressive_reduces_k_below_nominal_12() -> None:


    """Seuil très élevé : moins de 12 nœuds sur une bande large."""


    lam_lo, lam_hi = 200.0, 5000.0


    sk = canonical_spline_sigma_knots(


        lam_lo, lam_hi, min_delta_lambda_over_lambda_mean=0.12


    )


    assert int(sk.size) < 12


