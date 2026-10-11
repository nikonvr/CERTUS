"""What the machine reads while a layer grows, and where it stops it: the signal and the inversion of the stop.

`simulate_growth_kernel` (certus_strat_growth.py) builds the witness stack layer by layer, reads the monitoring signal on
it, and turns the trigger level into a thickness. This module holds the two halves it calls:

* the signal -- the characteristic matrices of the witness, real and nominal (`_stack_matrix`, `_stack_matrix_pair`),
  the closed form of the growing layer (`layer_scan_coeffs`), the slit bias at a depth (`slit_bias_at`), the coarse
  scan of the replayed layers and of the layer being grown (`_fill_history_signal`, `_fill_current_signal`), the
  readings the machine makes every 0.125 nm (`_machine_grid_signal`), and, when asked, POEM's anchors moved from the
  coarse samples to the extremum of their layer (`_exact_poem_anchors`, D96);
* the stop -- the thickness at which the read signal reaches the trigger level, on a parabola through three probes
  (`_invert_thickness_from_probes`) or on the exact signal when asked (`_invert_thickness_exact`, D97).

The pieces compiled with `inline="always"` are pasted into the kernel that calls them, whatever file they live in: the
note on the sub-kernels in certus_strat_growth.py holds for them (do not remove `inline="always"`, and do not split a
fused loop, without running `python scripts/c1_diff.py HEAD`). The kernel module re-imports every name it uses from
here, so they stay importable from it.
"""

import numpy as np
from numba import njit

from certus.domain.constants import TWO_PI

from .certus_strat_math import (
    _calc_T_added_layer,
    _seeded_noise_sample,
    _solve_quadratic_target,
    fit_parabola_vertex_3points,
)

#: Sweep span, as a multiple of the nominal thickness. Declared at module level so the
#: slit-bias profiles can be sampled on EXACTLY the axis the kernel sweeps: the profile
#: is indexed by u = d / d_nominal in [0, D_SCAN_VAL], and a mismatch between the two
#: would shift every bias by a fraction of a layer with no error anywhere.
D_SCAN_VAL: float = 3.0

#: Points of the scan of the layer being grown, and of each layer of the replayed block history. The current layer is
#: swept over D_SCAN_VAL times its thickness in 64 points (the nominal stop falls on index 21). Numerical choices, not
#: the machine's cadence (see the reading-noise note in `simulate_growth_kernel`). Module level because the pieces cut
#: out of the kernel all size their arrays with them.
SCAN_NPTS_CURRENT: int = 64
SCAN_NPTS_HISTORY: int = 16

#: Above this extinction coefficient the closed form below is no longer the same
#: computation -- delta becomes complex and |denom|^2 stops being a sinusoid in a real
#: 2.delta. 👤 settled the restriction on 2026-08-11: "limit STRAT to cases where
#: k < 1e-4".
#:
#: 📏 Measured on a real 24-layer stack, keeping only physical transmissions: the error
#: grows LINEARLY in k and is 4.2e-8 at k = 1e-4 -- 0.008 % of the reading noise
#: amplitude, four decades below it. The bound is comfortable, with a decade to spare.
#:
#: ⚠️ Two earlier attempts to locate this limit used RANDOM stack matrices, whose
#: denominator can approach zero: T explodes and the error is then measured on
#: unphysical values. They reported the form breaking at 1e-3, then at 1e-6. Both were
#: artefacts of the rig, not of the physics.
K_MAX_CLOSED_FORM: float = 1e-4


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def slit_bias_at(profiles: np.ndarray, layer: int, u: float) -> float:
    """Slit bias of ``layer`` at relative thickness ``u = d / d_nominal``.

    🔴 WHY A PROFILE AND NOT A CONSTANT -- and this is the whole point of the upgrade.

    The bias was one number per layer, added identically to every reading of that
    layer. But a constant added to the read signal is EXACTLY the ``b`` of the affine
    map ``T -> a.T + b``, and 12.1 proved POEM rigorously invariant under it. So the
    old model handed POEM precisely the part it absorbs for free, and modelled nothing
    of the part it cannot.

    📏 Measured on the judge of paix at 544 nm, B = 2 nm, the wavelength every one of
    the top twenty strategies uses. Bias sampled at d = 0, d_nom/2 and d_nom:

        layer 10    variation 0.07 A     mean |bias|  0.04 A
        layer 30    variation 1.52 A     mean |bias|  2.96 A
        layer 44    variation 44.4 A     mean |bias| 30.93 A
        layer 46    variation 62.2 A     mean |bias| 34.96 A

    The bias VARIES by up to 62 times the reading-noise amplitude inside a single
    layer. That variation is what shifts POEM's two anchors by different amounts and
    the trigger level by a third -- the "distortion depending on local curvature" that
    12.7 names as the one thing POEM cannot absorb.

    ⚠️ ``u`` is clamped, not extrapolated. Beyond the swept window the profile has not
    been measured, and a linear extrapolation of a curvature term would grow without
    bound in exactly the region the sweep was cut short to avoid.
    """
    nb = profiles.shape[1]
    if nb < 2:
        return 0.0
    x = u / D_SCAN_VAL * (nb - 1)
    if x <= 0.0:
        return profiles[layer, 0]
    if x >= nb - 1:
        return profiles[layer, nb - 1]
    i0 = int(x)
    t = x - i0
    return profiles[layer, i0] * (1.0 - t) + profiles[layer, i0 + 1] * t


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def layer_scan_coeffs(
    M00: complex, M01: complex, M10: complex, M11: complex,
    n_layer: complex, n_sub: complex,
) -> tuple[float, float, float]:
    """The three coefficients that make T(d) a CLOSED FORM for the growing layer.

    👤 asked whether an analytical derivative would save time (2026-08-11). It does more
    than that. For the layer growing on an already-deposited stack, the denominator is

        denom = C.cos(delta) + i.S.sin(delta)        with C and S CONSTANT in d

    so |denom|^2 is a pure sinusoid and

        T(d) = 4.n_sub / (P + Q.cos(2.delta) + R.sin(2.delta)),  delta = 2.pi.n.d/lambda

    📏 Verified to 5.4e-20 against the kernel, and to 3.2e-15 against the INDEPENDENT
    TMM oracle over 60 random stacks of 2 to 20 layers -- the same order as the
    production paths. This is not an approximation: it is the same computation written
    differently, with the three coefficients paid once instead of a 2x2 complex matrix
    product per point.

    🔑 WHAT IT UNLOCKS beyond raw speed (x3.6 measured on the sweep):

      * turning points become `tan 2.delta = R/Q`, a closed form -- no scanning;
      * the stopping point becomes `sqrt(Q^2+R^2).cos(2.delta - phi) = const`, likewise;
      * the second derivative costs NOTHING new, because d2D/ddelta2 = -4(D - P).

    🔴 VALID ONLY FOR k < K_MAX_CLOSED_FORM. The caller must check and RAISE rather than
    fall back silently -- 17-25 is the lesson: a silent fallback reinstalls a defect
    without anyone seeing it. Someone running STRAT on a metal must find out, not
    receive a plausible number.

    🔴 AND IT MUST BE VALIDATED AGAINST THE ORACLE, never against the kernel. Interdit 7
    exists because two sign bugs have already hidden inside re-implementations, worth 46
    and 82 points of reflectance -- and BOTH were exact at k = 0, hence invisible to any
    test that only looks at dielectrics. Which is exactly this case.
    """
    X = M00 + n_sub * M01
    Y = M10 + n_sub * M11
    C = X + Y
    S = Y / n_layer + n_layer * X
    cc = C.real * C.real + C.imag * C.imag
    ss = S.real * S.real + S.imag * S.imag
    # Im(C . conj(S))
    r = C.imag * S.real - C.real * S.imag
    return (0.5 * (cc + ss), 0.5 * (cc - ss), r)


# 🔑 MULTIPLE-TESTGLASS: BOTH stacks below start at `witness_base_layer`, not at 0.
#
# A fresh witness carries only the layers deposited SINCE it was swapped in, so the
# monitoring signal is that of a shorter stack -- which is the whole point: on a
# 99-layer filter the witness goes optically dead long before the part is finished
# (half-wave spacers swing by nothing, 19-layer mirrors transmit under 1e-4).
#
# 🔴 AND THE COST OF THE SWAP FALLS OUT OF THESE TWO LOOPS ON ITS OWN -- it is not
# modelled anywhere else, and must not be. The trigger level is computed on the
# NOMINAL stack and applied to the REAL one; that mismatch is what produces the
# error of opposite sign, i.e. optical monitoring's self-compensation. Start both
# loops at the same `witness_base_layer` and the errors of the layers BELOW it are
# invisible to both: they can no longer be compensated, and they stay frozen in the
# part for good. Truncating only one of the two would be far worse than wrong -- it
# would compare a 99-layer nominal target against a 20-layer real stack.
#
# ⚠️ `witness_base_layer = 0` reproduces the single-witness behaviour exactly. That
# is the invariant to test first.
#
# --- NOMINAL stack, accumulated in parallel with the real one ---------------------
#
# The trigger level of a layer is calculated BEFORE deposition, on the
# nominal design, and it no longer moves. Targeting it on a stack that
# has become erroneous is what produces the error of opposite sign: this
# is the compensation mechanism (Macleod, Bousquet).
#
# Before this fix, the target was T_real(d_nom) : the inversion parabola
# interpolating exactly this same point, the resolution gave Delta_d =
# noise / P', WITHOUT any accumulated error term. At zero noise, the
# thickness was nominal whatever the previous errors, so no compensation
# could appear OR be measured.
#
@njit(cache=True, fastmath=True, nogil=True, error_model="numpy", inline="always")
def _stack_matrix(wl: float, n_even: complex, n_odd: complex, thicknesses: np.ndarray, j_start: int, j_end: int) -> tuple[complex, complex, complex, complex]:
    """Characteristic matrix of layers `j_start` .. `j_end - 1`, as (m00, m01, m10, m11).

    Even layers have index `n_even`, odd ones `n_odd`, and `thicknesses[j]` is the thickness of layer j. An empty range
    is the identity. `simulate_growth_kernel` builds two of these: the stack of the witness up to the layer being
    grown, real and nominal.
    """
    m00 = 1.0 + 0j
    m01 = 0.0 + 0j
    m10 = 0.0 + 0j
    m11 = 1.0 + 0j
    for j in range(j_start, j_end):
        n_prev = n_even if j % 2 == 0 else n_odd
        th_prev = thicknesses[j]
        phi = TWO_PI / wl * n_prev * th_prev
        cp, sp = (np.cos(phi), np.sin(phi))
        son = sp / n_prev if abs(n_prev) > 1e-09 else 0.0
        e01 = +1j * son
        e10 = +1j * n_prev * sp
        t00 = cp * m00 + e01 * m10
        t01 = cp * m01 + e01 * m11
        t10 = e10 * m00 + cp * m10
        t11 = e10 * m01 + cp * m11
        m00, m01, m10, m11 = (t00, t01, t10, t11)
    return m00, m01, m10, m11


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy", inline="always")
def _stack_matrix_pair(wl: float, n_even_r: complex, n_odd_r: complex, th_r: np.ndarray, n_even_n: complex, n_odd_n: complex, th_n: np.ndarray, j_start: int, j_end: int) -> tuple[complex, complex, complex, complex, complex, complex, complex, complex]:
    """The real and the nominal characteristic matrices of layers `j_start` .. `j_end - 1`, in ONE loop.

    Returns (R00, R01, R10, R11, Q00, Q01, Q10, Q11): R is the real stack (indices `n_even_r`, `n_odd_r`, thicknesses
    `th_r`), Q the nominal one. The two are computed in the same loop on purpose: two loops moved the last bits (see
    the note above).
    """
    R00, R01, R10, R11 = (1.0 + 0j, 0.0 + 0j, 0.0 + 0j, 1.0 + 0j)
    Q00, Q01, Q10, Q11 = (1.0 + 0j, 0.0 + 0j, 0.0 + 0j, 1.0 + 0j)
    for j in range(j_start, j_end):
        n_p_r = n_even_r if j % 2 == 0 else n_odd_r
        n_p_n = n_even_n if j % 2 == 0 else n_odd_n
        ph1 = TWO_PI / wl * n_p_r * th_r[j]
        c1, s1 = (np.cos(ph1), np.sin(ph1))
        so1 = s1 / n_p_r if abs(n_p_r) > 1e-09 else 0.0
        a0 = c1 * R00 + 1j * so1 * R10
        a1 = c1 * R01 + 1j * so1 * R11
        a2 = 1j * n_p_r * s1 * R00 + c1 * R10
        a3 = 1j * n_p_r * s1 * R01 + c1 * R11
        R00, R01, R10, R11 = (a0, a1, a2, a3)
        ph2 = TWO_PI / wl * n_p_n * th_n[j]
        c2, s2 = (np.cos(ph2), np.sin(ph2))
        so2 = s2 / n_p_n if abs(n_p_n) > 1e-09 else 0.0
        b0 = c2 * Q00 + 1j * so2 * Q10
        b1 = c2 * Q01 + 1j * so2 * Q11
        b2 = 1j * n_p_n * s2 * Q00 + c2 * Q10
        b3 = 1j * n_p_n * s2 * Q01 + c2 * Q11
        Q00, Q01, Q10, Q11 = (b0, b1, b2, b3)
    return R00, R01, R10, R11, Q00, Q01, Q10, Q11


# CONTINUOUS SCAN OVER THE BLOCK LENGTH, and not only on the current layer.
# Without this POEM only captures the intra-layer swing.
#
#   At UNCHANGED wavelength the monitoring signal is CONTINUOUS from one
#   layer to the next: the turning points already crossed during the previous
#   layers of the block remain valid measurements, exploitable to realign
#   the current layer. Upon changing lambda we start on a new signal
#   and all history is lost.
#
# This is what gives monochromatic blocks their value, what Arsac's P-PM
# (chap. 4) exploits, and what Zideluns et al. (Opt. Express 29, 33398,
# 2021) formulate as: "self-compensation operates only at the monitored
# wavelength and diminishes when layers are monitored at different
# wavelengths".
#
# block_start_layer = index of the first layer of the block. Default -1 =
# layer alone, which preserves the behavior of unmodified callers.
# ---- READING NOISE ON THE MONITORING SIGNAL (axis 1.1) --------------
#
# `noise_val_precalc` for a long time only noised A SINGLE point in the whole
# chain: the stopping comparison (`target_T_noisy`, below). However `Ts_r`, the
# "real" signal, is used for three more things, and none were noised:
#
#   - the DETECTION of turning points           -> "do we see the TPs?"
#   - reading the POEM ANCHORS (T_prev, T_last) -> "is POEM free?"
#   - the REACHABILITY test of the level        -> "do we reach the level?"
#
# The three questions of the final arbiter thus received the answer "always, and
# exactly", which has no content: the extrema were localized on a perfect TMM
# curve. In particular POEM reports its frozen fraction on the ACTUALLY OBSERVED
# extrema -- T_prev_real and T_last_real are supposed to be MEASUREMENTS.
# We gave it the benefit of realignment without making it pay the cost: the
# target level being T_prev + p.(T_last - T_prev), two anchors each carrying a
# standard deviation error sigma give
#
#     Var[target] = sigma^2 . [ (1-p)^2 + p^2 ]   + sigma^2 on the stopping reading
#
# which is an effective noise of sigma.sqrt(1 + (1-p)^2 + p^2): x1.22 at p = 0.5,
# and up to x1.41 when the trigger falls on an anchor. POEM exchanges a BIAS
# (uncompensated error) for a VARIANCE (two more measurements), and the model
# only counted the benefit -- it therefore structurally favored strategies that
# rely on many anchors, or on old anchors inherited from the block, since it
# assumed them to be perfect.
#
# 🔴 COMMON RANDOM NUMBERS -- the constraint not to lose.
#
# The draw is a PURE FUNCTION of (seed, scanned layer, draw, point index). No
# input depends on the strategy: neither the wavelength, nor the block splitting,
# nor `block_start_layer`. Two strategies compared on the same (seed, draw)
# therefore see EXACTLY the same reading noise, and their score difference
# remains attributable to the strategy alone.
#
# This is why the draw is not materialized as an array: an array indexed flat on
# the scan would BECOME MISALIGNED from one strategy to another, since the
# history length `n_hist` depends on the block splitting. The
# `_seeded_noise_sample` generator -- already in production for nucleation,
# same N(0, 1/3) law truncated to +/-1 as the Phase B Sobol draw -- is called
# with indices ALIGNED TO PHYSICS:
#
#   history of layer j, point k           ->  (group=j,       elem=k)
#   scan of the current layer, k          ->  (group=i_layer, elem=NPTS_PREV+k)
#
# The first indexing is invariant in `i_layer`: all layers of a same block reread
# the past of layer j WITH THE SAME NOISE. This is the physical invariant --
# the machine recorded a measurement, it does not remeasure it.
#
# ⚠ WHAT REMAINS UNFAITHFUL, and what must be kept in mind to read the produced
# crash rates. The number of PARASITE extrema fabricated by a reading noise
# depends on the sampling DENSITY of the scan, which is here a numerical choice
# (NPTS = 64 over 3x the thickness, NPTS_PREV = 16 over 1x) and not the machine's
# cadence. The history is therefore sampled four times more coarsely than the
# current layer, and the same physical point does not have the same noise
# depending on whether it is read as "current layer" or as "history".
# Modeling the cadence and integration time is axis 1.2, not this one.
#
# ARE NOT NOISED, and it is intended:
#   - `Ts_n`: the NOMINAL signal is the strategy, calculated offline before
#     deposition. There is nobody to measure it.
#   - `T_mono`: design quantity (dynamic range, monotonicity), not a reading.
#   - the three points `T_points` of the parabolic inversion: they are not a
#     measurement but the resolution of T_real(d) = target_T_noisy. The noise
#     of the stopping reading is already carried, and only carried, by
#     `noise_val_precalc`.
#
@njit(cache=True, fastmath=True, nogil=True, error_model="numpy", inline="always")
def _fill_history_signal(
    wl: float,
    n_Sub: complex,
    n_H_r: complex,
    n_L_r: complex,
    n_H: complex,
    n_L: complex,
    prev_thicknesses_sim: np.ndarray,
    p_thick_nominal: np.ndarray,
    j0: int,
    i_layer: int,
    R00: complex,
    R01: complex,
    R10: complex,
    R11: complex,
    Q00: complex,
    Q01: complex,
    Q10: complex,
    Q11: complex,
    Ts_r: np.ndarray,
    Ts_n: np.ndarray,
    apply_signal_noise: bool,
    signal_noise_scale: float,
    signal_noise_seed: int,
    signal_noise_run: int,
) -> tuple[int, complex, complex, complex, complex, complex, complex, complex, complex]:
    """Replay the layers `j0` .. `i_layer - 1` of the block: fill `Ts_r` and `Ts_n` with their signal, from index 0.

    `Ts_r` is what the machine read (real thicknesses, real indices, reading noise), `Ts_n` what the strategy expects
    (nominal). `(R00, R01, R10, R11)` and `(Q00, Q01, Q10, Q11)` are the real and nominal matrices of the stack below
    `j0`. Returns (idx, R00, R01, R10, R11, Q00, Q01, Q10, Q11): the next free index of the arrays, and the matrices
    of the stack up to `i_layer`, where the scan of the current layer goes on.
    """
    TWO_PI_VAL = TWO_PI
    NPTS_PREV = SCAN_NPTS_HISTORY
    idx = 0
    for j in range(j0, i_layer):
        n_j_r = n_H_r if j % 2 == 0 else n_L_r
        n_j_n = n_H if j % 2 == 0 else n_L
        d_rj = prev_thicknesses_sim[j]
        d_nj = p_thick_nominal[j]
        # ---- CLOSED FORM ON THE HISTORY TOO (18ter) -----------------------
        #
        # 📏 The ablation of 2026-08-11 named this block: re-scanning the block
        # history is **38.6 %** of the kernel, the single largest item -- and the
        # closed form had only been applied to the CURRENT layer's sweep. Each
        # history layer j is equally "a layer growing on a fixed substack", the
        # substack being layers 0..j-1, so the same three coefficients apply.
        #
        # ⚠️ TWO SETS OF COEFFICIENTS, and they are not interchangeable: the real
        # signal is swept over the REAL thickness d_rj on the real indices, the
        # nominal one over d_nj on the nominal indices. Sharing them would silently
        # merge the two stacks -- the very divergence this kernel exists to measure.
        fast_j = (
            abs(n_j_r.imag) < K_MAX_CLOSED_FORM and abs(n_j_n.imag) < K_MAX_CLOSED_FORM
        )
        Pjr = 0.0
        Qjr = 0.0
        Rjr = 0.0
        Pjn = 0.0
        Qjn = 0.0
        Rjn = 0.0
        kkjr = 0.0
        kkjn = 0.0
        if fast_j:
            Pjr, Qjr, Rjr = layer_scan_coeffs(R00, R01, R10, R11, n_j_r, n_Sub)
            Pjn, Qjn, Rjn = layer_scan_coeffs(Q00, Q01, Q10, Q11, n_j_n, n_Sub)
            kkjr = TWO_PI_VAL / wl * n_j_r.real
            kkjn = TWO_PI_VAL / wl * n_j_n.real
        for k in range(1, NPTS_PREV + 1):
            f = k / NPTS_PREV
            if fast_j:
                tdj = 2.0 * kkjr * (f * d_rj)
                denj = Pjr + Qjr * np.cos(tdj) + Rjr * np.sin(tdj)
                if denj > 1e-18:
                    Ts_r[idx] = 4.0 * n_Sub.real / denj
            else:
                p3 = TWO_PI_VAL / wl * n_j_r * (f * d_rj)
                c3, s3 = (np.cos(p3), np.sin(p3))
                o3 = s3 / n_j_r if abs(n_j_r) > 1e-09 else 0.0
                z1 = (c3 * R00 + 1j * o3 * R10) + n_Sub * (c3 * R01 + 1j * o3 * R11)
                z1 = z1 + (1j * n_j_r * s3 * R00 + c3 * R10) + n_Sub * (1j * n_j_r * s3 * R01 + c3 * R11)
                if abs(z1) > 1e-09:
                    Ts_r[idx] = 4.0 * n_Sub.real / (z1.real**2 + z1.imag**2)
            if apply_signal_noise:
                # group = j: the past of layer j carries the SAME noise for
                # all the layers of the block that read it again.
                Ts_r[idx] += signal_noise_scale * _seeded_noise_sample(
                    signal_noise_seed, j, signal_noise_run, k - 1, True
                )
            if fast_j:
                tdn = 2.0 * kkjn * (f * d_nj)
                denn = Pjn + Qjn * np.cos(tdn) + Rjn * np.sin(tdn)
                if denn > 1e-18:
                    Ts_n[idx] = 4.0 * n_Sub.real / denn
            else:
                p4 = TWO_PI_VAL / wl * n_j_n * (f * d_nj)
                c4, s4 = (np.cos(p4), np.sin(p4))
                o4 = s4 / n_j_n if abs(n_j_n) > 1e-09 else 0.0
                z2 = (c4 * Q00 + 1j * o4 * Q10) + n_Sub * (c4 * Q01 + 1j * o4 * Q11)
                z2 = z2 + (1j * n_j_n * s4 * Q00 + c4 * Q10) + n_Sub * (1j * n_j_n * s4 * Q01 + c4 * Q11)
                if abs(z2) > 1e-09:
                    Ts_n[idx] = 4.0 * n_Sub.real / (z2.real**2 + z2.imag**2)
            idx += 1
        p3 = TWO_PI_VAL / wl * n_j_r * d_rj
        c3, s3 = (np.cos(p3), np.sin(p3))
        o3 = s3 / n_j_r if abs(n_j_r) > 1e-09 else 0.0
        g0 = c3 * R00 + 1j * o3 * R10
        g1 = c3 * R01 + 1j * o3 * R11
        g2 = 1j * n_j_r * s3 * R00 + c3 * R10
        g3 = 1j * n_j_r * s3 * R01 + c3 * R11
        R00, R01, R10, R11 = (g0, g1, g2, g3)
        p4 = TWO_PI_VAL / wl * n_j_n * d_nj
        c4, s4 = (np.cos(p4), np.sin(p4))
        o4 = s4 / n_j_n if abs(n_j_n) > 1e-09 else 0.0
        h0 = c4 * Q00 + 1j * o4 * Q10
        h1 = c4 * Q01 + 1j * o4 * Q11
        h2 = 1j * n_j_n * s4 * Q00 + c4 * Q10
        h3 = 1j * n_j_n * s4 * Q01 + c4 * Q11
        Q00, Q01, Q10, Q11 = (h0, h1, h2, h3)
    return idx, R00, R01, R10, R11, Q00, Q01, Q10, Q11


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy", inline="always")
def _fill_current_signal(
    wl: float,
    n_Sub: complex,
    n_H_r: complex,
    n_L_r: complex,
    n_H: complex,
    n_L: complex,
    i_layer: int,
    R00: complex,
    R01: complex,
    R10: complex,
    R11: complex,
    Q00: complex,
    Q01: complex,
    Q10: complex,
    Q11: complex,
    d_max: float,
    npts_cur: int,
    n_hist: int,
    idx: int,
    Ts_r: np.ndarray,
    Ts_n: np.ndarray,
    apply_signal_noise: bool,
    signal_noise_scale: float,
    signal_noise_seed: int,
    signal_noise_run: int,
) -> None:
    """Scan the layer being grown, from 0 to `d_max` in `npts_cur` steps: its real and nominal signals go to `Ts_r[idx:]`
    and `Ts_n[idx:]`.

    `(R00 .. R11)` and `(Q00 .. Q11)` are the real and nominal matrices of the stack under it. The real signal carries
    the reading noise of the (seed, run) draw, indexed by the layer and the point; when the block has a history
    (`n_hist > 0`), the first point is the continuation of the last history point and takes ITS noise draw, so that one
    reading is not drawn twice.
    """
    TWO_PI_VAL = TWO_PI
    NPTS_PREV = SCAN_NPTS_HISTORY
    step_s = d_max / (npts_cur - 1)
    n_cur_r = n_H_r if i_layer % 2 == 0 else n_L_r
    n_cur_n = n_H if i_layer % 2 == 0 else n_L
    # ---- CLOSED-FORM FAST PATH (18ter) ----------------------------------
    #
    # 🔴 GUARD, not a fallback. `layer_scan_coeffs` is exact only while delta stays
    # real, i.e. k = 0. 👤 restricted STRAT to k < 1e-4 on 2026-08-11, where the
    # measured error is 4.2e-8 -- 0.008 % of the reading noise. Beyond that the
    # matrix path is used, and it is chosen HERE rather than silently: the two paths
    # must never diverge without anyone noticing (17-25).
    fast_path = (
        abs(n_cur_r.imag) < K_MAX_CLOSED_FORM and abs(n_cur_n.imag) < K_MAX_CLOSED_FORM
    )
    Pr = 0.0
    Qr = 0.0
    Rr = 0.0
    Pn = 0.0
    Qn = 0.0
    Rn = 0.0
    kk_r = 0.0
    kk_n = 0.0
    if fast_path:
        Pr, Qr, Rr = layer_scan_coeffs(R00, R01, R10, R11, n_cur_r, n_Sub)
        Pn, Qn, Rn = layer_scan_coeffs(Q00, Q01, Q10, Q11, n_cur_n, n_Sub)
        kk_r = TWO_PI_VAL / wl * n_cur_r.real
        kk_n = TWO_PI_VAL / wl * n_cur_n.real
    for k in range(npts_cur):
        d_k = k * step_s
        if fast_path:
            # CLOSED FORM: three coefficients paid once, then two trig calls per
            # point and no complex arithmetic at all. Verified to 1.2e-15 against
            # the INDEPENDENT TMM oracle over 40 random stacks -- the same order as
            # the production paths. See `layer_scan_coeffs`.
            td_r = 2.0 * kk_r * d_k
            den_r = Pr + Qr * np.cos(td_r) + Rr * np.sin(td_r)
            if den_r > 1e-18:
                Ts_r[idx] = 4.0 * n_Sub.real / den_r
        else:
            phi_kr = TWO_PI_VAL / wl * n_cur_r * d_k
            cpkr, spkr = (np.cos(phi_kr), np.sin(phi_kr))
            sonkr = spkr / n_cur_r if abs(n_cur_r) > 1e-09 else 0.0
            e01r = +1j * sonkr
            e10r = +1j * n_cur_r * spkr
            r00 = cpkr * R00 + e01r * R10
            r01 = cpkr * R01 + e01r * R11
            r10 = e10r * R00 + cpkr * R10
            r11 = e10r * R01 + cpkr * R11
            dr = r00 + n_Sub * r01 + r10 + n_Sub * r11
            if abs(dr) > 1e-09:
                Ts_r[idx] = 4.0 * n_Sub.real / (dr.real**2 + dr.imag**2)
        if apply_signal_noise:
            g_noise = i_layer
            e_noise = NPTS_PREV + k
            if k == 0 and n_hist > 0:
                g_noise = i_layer - 1
                e_noise = NPTS_PREV - 1
            Ts_r[idx] += signal_noise_scale * _seeded_noise_sample(
                signal_noise_seed, g_noise, signal_noise_run, e_noise, True
            )
        phi_kn = TWO_PI_VAL / wl * n_cur_n * d_k
        if fast_path:
            td_n = 2.0 * kk_n * d_k
            den_n = Pn + Qn * np.cos(td_n) + Rn * np.sin(td_n)
            if den_n > 1e-18:
                Ts_n[idx] = 4.0 * n_Sub.real / den_n
        else:
            cpkn, spkn = (np.cos(phi_kn), np.sin(phi_kn))
            sonkn = spkn / n_cur_n if abs(n_cur_n) > 1e-09 else 0.0
            e01n = +1j * sonkn
            e10n = +1j * n_cur_n * spkn
            q00 = cpkn * Q00 + e01n * Q10
            q01 = cpkn * Q01 + e01n * Q11
            q10 = e10n * Q00 + cpkn * Q10
            q11 = e10n * Q01 + cpkn * Q11
            dn = q00 + n_Sub * q01 + q10 + n_Sub * q11
            if abs(dn) > 1e-09:
                Ts_n[idx] = 4.0 * n_Sub.real / (dn.real**2 + dn.imag**2)
        idx += 1


# ---- A8: THE MACHINE SAMPLING GRID, UNWELDED FROM THE SMOOTHING (17-2) ----
#
# The grid and the smoothing are two different things and they were expressible
# only together. `SAMPLE_DD = 0.125` lived INSIDE `if smoothing_window > 1`, so
# the configuration 12.4 requires in order to be validated -- FINE GRID, WINDOW
# AT 1 -- could not be written at all.
#
# 🔑 WHY THE GRID MATTERS, and it is not about being "a bit coarse". The plate
# turns at 240 rpm, the witness passes the detector 4 times a second, the
# deposit advances at 0.5 nm/s: the machine reads every 0.125 nm, so 800 times
# on a 100 nm layer where the model simulates 21. A factor 38 -- and EVERY
# READING CARRIES ITS OWN NOISE DRAW. 12.4 measured what that governs: noise
# alone fabricates a false turning point in 32.9 % of layers at 80 points,
# 92.9 % at 320, and 99.9 % at the machine's own 800. The model has been
# underestimating that risk by construction, simply by drawing 38 times less.
#
# 🔑 THE SIGNAL IS COMPUTED EXACTLY AT EVERY READING (D94, D95). It used to be the coarse scan (16 points per replayed
# layer, 64 over three thicknesses of the current one) INTERPOLATED onto the reading positions, on the idea that T(d) is
# smooth. 📏 Measured on 2026-10-10 on the judge of paix's winner, nominal signal: the interpolated values were 6.1 A off
# the exact T in median per layer and up to 33 A, the extrapolated start of the window (the line through its first two
# coarse points) up to 36 A where the window starts on a turning point -- against a reading noise of +/- 1 A. And the
# coarse points already carried their own noise draw, so every reading carried two, one of them interpolated, i.e.
# correlated from one reading to the next, which the frozen reading model (ETAT section 3) excludes.
#
# Exactness costs little: for a real index the growing layer obeys the closed form of `layer_scan_coeffs`, three
# coefficients per layer and two trigonometric calls per reading -- less than the noise draw of that reading. An
# absorbing index (k above `K_MAX_CLOSED_FORM`) takes the characteristic matrix, exact too, slower.
#
# 🔴 C2 STAYS AS IT WAS. A replayed layer j is read `ceil(d_nominal_j / dd)` times whatever its real thickness, so the
# number of draws never depends on the strategy; reading m sits at depth m * dd of the nominal layer, and at the same
# FRACTION of the real one (a real layer 0.3 % thicker is read 0.3 % more sparsely, not cut short: the previous rule
# held its last readings flat or dropped its end, and the signal jumped at the next layer). The draws are the ones of
# before: (group j, element m) for a replayed layer, (group i_layer, element 4096 + m) for the current one, whose
# first reading is the last of the layer below and takes its draw.
#
# ⚠️ THE UNWELDING IS ONE-DIRECTIONAL, and that is correct rather than lazy. The
# smoothing window is counted IN MACHINE READINGS, so it is meaningless on the
# coarse grid: smoothing still implies the fine grid. What was missing is the
# other direction -- the fine grid WITHOUT smoothing -- and that is now
# expressible via `machine_sampling_dd`.
#
# 🔴 AND 12.4 WARNS ABOUT EXACTLY THIS CONFIGURATION: the fine grid ALONE takes
# fabrication from 33 % to 99.9 %. The crash rate will rise sharply. That is
# EXPECTED, it is the whole point of measuring it, and it must not be read as
# the physics having degraded.
#
@njit(cache=True, fastmath=True, nogil=True, error_model="numpy", inline="always")
def _advance_matrix(
    wl: float, n_layer: complex, d: float, M00: complex, M01: complex, M10: complex, M11: complex
) -> tuple[complex, complex, complex, complex]:
    """The characteristic matrix of the stack (M) once a layer of index `n_layer` and thickness `d` is laid on it."""
    phi = TWO_PI / wl * n_layer * d
    c, s_ = (np.cos(phi), np.sin(phi))
    so = s_ / n_layer if abs(n_layer) > 1e-09 else 0.0
    return (
        c * M00 + 1j * so * M10,
        c * M01 + 1j * so * M11,
        1j * n_layer * s_ * M00 + c * M10,
        1j * n_layer * s_ * M01 + c * M11,
    )


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy", inline="always")
def _layer_T(
    wl: float,
    n_layer: complex,
    n_Sub: complex,
    M00: complex,
    M01: complex,
    M10: complex,
    M11: complex,
    depths: np.ndarray,
    out: np.ndarray,
    first: int,
) -> None:
    """T of the stack (M) under a growing layer of index `n_layer`, at each depth of `depths`, written to `out[first:]`.

    The closed form of `layer_scan_coeffs` for a real index, the characteristic matrix otherwise: both exact.
    """
    count = depths.shape[0]
    if abs(n_layer.imag) < K_MAX_CLOSED_FORM:
        P, Q, R = layer_scan_coeffs(M00, M01, M10, M11, n_layer, n_Sub)
        kk = TWO_PI / wl * n_layer.real
        for m in range(count):
            td = 2.0 * kk * depths[m]
            den = P + Q * np.cos(td) + R * np.sin(td)
            out[first + m] = 4.0 * n_Sub.real / den if den > 1e-18 else 0.0
    else:
        for m in range(count):
            out[first + m] = _calc_T_added_layer(wl, n_layer, depths[m], n_Sub, M00, M01, M10, M11)


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy", inline="always")
def _machine_grid_signal(
    machine_sampling_dd: float,
    wl: float,
    n_Sub: complex,
    n_H_r: complex,
    n_L_r: complex,
    n_H: complex,
    n_L: complex,
    witness_base_layer: int,
    j0: int,
    i_layer: int,
    nominal_th: float,
    p_thick_nominal: np.ndarray,
    prev_thicknesses_sim: np.ndarray,
    slit_profiles: np.ndarray | None,
    apply_signal_noise: bool,
    signal_noise_scale: float,
    signal_noise_seed: int,
    signal_noise_run: int,
) -> tuple[np.ndarray, np.ndarray, int, int, int]:
    """The real and the nominal signal at the readings the machine makes: one every `machine_sampling_dd` nm (0.125 by
    default) over the replayed layers `j0` .. `i_layer - 1` of the block, then over three nominal thicknesses of the
    layer being grown -- each value exact, the real one with its slit bias and its own noise draw.

    Returns (Ts_r, Ts_n, n_tot, idx_nom_stop, n_hist): the two signals, their length, the index of the nominal stop, and
    that of the first reading of the layer being grown (the readings of the replayed layers come before it).
    """
    D_SCAN = D_SCAN_VAL
    SAMPLE_DD = machine_sampling_dd if machine_sampling_dd > 0.0 else 0.125
    M_hist = 0
    for j in range(j0, i_layer):
        M_hist += int(np.ceil(p_thick_nominal[j] / SAMPLE_DD))
    M_cur = int(np.ceil(D_SCAN * nominal_th / SAMPLE_DD)) + 1
    M_tot = M_hist + M_cur
    Ts_r = np.empty(M_tot, dtype=np.float64)
    Ts_n = np.empty(M_tot, dtype=np.float64)
    slit_on = slit_profiles is not None and slit_profiles.shape[0] > 0
    R00, R01, R10, R11, Q00, Q01, Q10, Q11 = _stack_matrix_pair(
        wl, n_H_r, n_L_r, prev_thicknesses_sim, n_H, n_L, p_thick_nominal, witness_base_layer, j0
    )
    idx = 0
    for j in range(j0, i_layer):
        n_j_r = n_H_r if j % 2 == 0 else n_L_r
        n_j_n = n_H if j % 2 == 0 else n_L
        d_rj = prev_thicknesses_sim[j]
        d_nj = p_thick_nominal[j]
        M_pj = int(np.ceil(d_nj / SAMPLE_DD))
        dep_n = np.arange(M_pj) * SAMPLE_DD
        dep_r = dep_n * (d_rj / d_nj) if d_nj > 1e-9 else dep_n
        _layer_T(wl, n_j_r, n_Sub, R00, R01, R10, R11, dep_r, Ts_r, idx)
        _layer_T(wl, n_j_n, n_Sub, Q00, Q01, Q10, Q11, dep_n, Ts_n, idx)
        for m in range(M_pj):
            if slit_on:
                Ts_r[idx + m] += slit_bias_at(slit_profiles, j, dep_r[m] / d_nj if d_nj > 1e-9 else 0.0)
            if apply_signal_noise:
                Ts_r[idx + m] += signal_noise_scale * _seeded_noise_sample(signal_noise_seed, j, signal_noise_run, m, True)
        idx += M_pj
        R00, R01, R10, R11 = _advance_matrix(wl, n_j_r, d_rj, R00, R01, R10, R11)
        Q00, Q01, Q10, Q11 = _advance_matrix(wl, n_j_n, d_nj, Q00, Q01, Q10, Q11)
    n_cur_r = n_H_r if i_layer % 2 == 0 else n_L_r
    n_cur_n = n_H if i_layer % 2 == 0 else n_L
    dep_c = np.arange(M_cur) * SAMPLE_DD
    _layer_T(wl, n_cur_r, n_Sub, R00, R01, R10, R11, dep_c, Ts_r, idx)
    _layer_T(wl, n_cur_n, n_Sub, Q00, Q01, Q10, Q11, dep_c, Ts_n, idx)
    for m in range(M_cur):
        if slit_on:
            Ts_r[idx + m] += slit_bias_at(slit_profiles, i_layer, dep_c[m] / nominal_th)
        if apply_signal_noise:
            g_noise = i_layer
            e_noise = 4096 + m
            if m == 0 and M_hist > 0:
                g_noise = i_layer - 1
                e_noise = int(np.ceil(p_thick_nominal[i_layer - 1] / SAMPLE_DD)) - 1
            Ts_r[idx + m] += signal_noise_scale * _seeded_noise_sample(
                signal_noise_seed, g_noise, signal_noise_run, e_noise, True
            )
    idx_nom_stop = M_hist + round(nominal_th / SAMPLE_DD)
    return Ts_r, Ts_n, M_tot, idx_nom_stop, M_hist


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy", inline="always")
def _invert_thickness_from_probes(
    wl: float,
    n_current: complex,
    nominal_th: float,
    probe_offset: float,
    n_Sub: complex,
    M_before_00: complex,
    M_before_01: complex,
    M_before_10: complex,
    M_before_11: complex,
    affine_scale: float,
    affine_offset: float,
    photo_curvature: float,
    slit_profiles: np.ndarray | None,
    i_layer: int,
    target_T_noisy: float,
) -> float:
    """The error on the thickness at which the machine stops the layer: three probe thicknesses around the nominal one
    (`nominal_th` and `probe_offset` either side), T read on the real stack (`M_before`) at each, a parabola through them,
    and the thickness at which it reaches `target_T_noisy`, minus the nominal thickness.

    The inversion is in MEASURED units: the affine drift and the slit bias are applied to the three probe readings, like
    everything the instrument reads, while the target stays what the controller computed. An affine map commutes with the
    parabola fit and the root solve, which is what keeps POEM invariant under it.
    """
    TWO_PI_VAL = TWO_PI
    th_points = np.array([max(0.1, nominal_th - probe_offset), nominal_th, nominal_th + probe_offset])
    T_points = np.zeros(3)
    for k in range(3):
        d = th_points[k]
        phi = TWO_PI_VAL / wl * n_current * d
        cp, sp = (np.cos(phi), np.sin(phi))
        son = sp / n_current if abs(n_current) > 1e-09 else 0.0
        m01 = +1j * son
        m10 = +1j * n_current * sp
        a00 = cp * M_before_00 + m01 * M_before_10
        a01 = cp * M_before_01 + m01 * M_before_11
        a10 = m10 * M_before_00 + cp * M_before_10
        a11 = m10 * M_before_01 + cp * M_before_11
        denom = a00 + n_Sub * a01 + a10 + n_Sub * a11
        if abs(denom) > 1e-09:
            T_points[k] = 4.0 * n_Sub.real / (denom.real**2 + denom.imag**2)
    # ---- THE INVERSION MUST BE IN MEASURED UNITS ----------------------------
    #
    # `target_T_noisy` is a level read on the instrument, so it carries the affine
    # distortion. The forward model inverted against it must carry it too, or the
    # two sides of `T(d) = target` are expressed in different units.
    #
    # 🔴 THIS WAS THE DEFECT THAT MADE THE AFFINE PARAMETERS UNUSABLE. POEM is exactly
    # invariant under T -> a.T + b: both anchors absorb the distortion, so the reported
    # level equals a.target_true + b, and solving a.T(d) + b = a.target_true + b returns
    # the intended thickness. Inverting the UNDISTORTED parabola solved
    # T(d) = a.target_true + b instead, which is a different equation.
    #
    # 📏 Measured on 6 QWOT layers monitored at 610 nm, d_nom = 94.178 nm, upstream
    # error 2 nm, no noise. Expected shift under an affine map: ZERO.
    #
    #     a = 1.0000  b = 0.000  ->  d_stop =  94.128 nm
    #     a = 0.9574  b = 0.000  ->  d_stop =  87.527 nm     -6.60 nm
    #     a = 1.0000  b = 0.020  ->  d_stop = 100.522 nm     +6.39 nm
    #
    # An affine map commutes with the parabola fit and with the root solve, so applying
    # it to the three probe points restores the invariance exactly.
    if affine_scale != 1.0 or affine_offset != 0.0 or photo_curvature != 0.0:
        for k in range(3):
            t_aff = affine_scale * T_points[k] + affine_offset
            T_points[k] = t_aff + 4.0 * photo_curvature * t_aff * (1.0 - t_aff)
    # 12.7: these three points are what the instrument READS around the stopping
    # thickness, so they carry the slit bias like every other reading. The target they
    # are solved against stays monochromatic -- that asymmetry IS the effect, and
    # applying the bias to both sides would cancel it exactly.
    #
    # 🔑 And EACH of the three carries the bias of ITS OWN thickness. They straddle the
    # stopping point, so a common constant would cancel out of the parabola's curvature
    # and shift only its offset; the differing biases tilt the parabola, which is what
    # actually moves the root. Same reason as on `Ts_r`: it is the variation that bites.
    if slit_profiles is not None and slit_profiles.shape[0] > 0 and nominal_th > 1e-9:
        for k in range(3):
            T_points[k] += slit_bias_at(slit_profiles, i_layer, th_points[k] / nominal_th)
    a_quad, b_quad, c_quad = fit_parabola_vertex_3points(th_points, T_points)
    calc_thick = _solve_quadratic_target(a_quad, b_quad, c_quad, target_T_noisy, nominal_th)
    error_raw = calc_thick - nominal_th
    return error_raw


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy", inline="always")
def _invert_thickness_exact(
    wl: float,
    n_current: complex,
    nominal_th: float,
    probe_offset: float,
    n_Sub: complex,
    M_before_00: complex,
    M_before_01: complex,
    M_before_10: complex,
    M_before_11: complex,
    affine_scale: float,
    affine_offset: float,
    photo_curvature: float,
    slit_profiles: np.ndarray | None,
    i_layer: int,
    target_T_noisy: float,
) -> float:
    """The same stop as `_invert_thickness_from_probes`, solved on the exact signal instead of a parabola (D97).

    The measured signal of the growing layer is T(d) = 4 n_sub / (P + Q cos 2kd + R sin 2kd) (`layer_scan_coeffs`), then
    the instrument's distortion and the slit bias of depth d, exactly as on the three probes. The root nearest the
    nominal thickness is bracketed by stepping outward from it, alternately on each side, then bisected. The parabola
    through three probes at +/- `probe_offset` extrapolates as soon as the stop moves away from the nominal thickness:
    measured on 2026-10-10, 0.021 nm RMS under POEM, up to 1.53 nm at an absolute level, on the judge of paix.

    An absorbing layer (k above `K_MAX_CLOSED_FORM`) has no closed form and keeps the parabola, as does a level the exact
    signal does not cross within three nominal thicknesses (the reachability test, on the read signal, said it did).
    """
    if abs(n_current.imag) >= K_MAX_CLOSED_FORM or nominal_th <= 1e-9:
        return _invert_thickness_from_probes(
            wl, n_current, nominal_th, probe_offset, n_Sub, M_before_00, M_before_01, M_before_10, M_before_11,
            affine_scale, affine_offset, photo_curvature, slit_profiles, i_layer, target_T_noisy,
        )
    P, Q, R = layer_scan_coeffs(M_before_00, M_before_01, M_before_10, M_before_11, n_current, n_Sub)
    kk2 = 2.0 * TWO_PI / wl * n_current.real
    distort = affine_scale != 1.0 or affine_offset != 0.0 or photo_curvature != 0.0
    slit_on = slit_profiles is not None and slit_profiles.shape[0] > 0
    # The step: an eighth of the probe offset, and never more than a 64th of the period of T(d) -- two roots of the
    # same level are half a period apart at least, so a bracket of this width holds one of them.
    period = TWO_PI / kk2 if kk2 > 1e-12 else nominal_th
    step = min(0.125 * probe_offset, period / 64.0)
    if step <= 1e-9:
        step = 1e-3 * nominal_th
    d_max = D_SCAN_VAL * nominal_th
    d0 = nominal_th
    t0 = 4.0 * n_Sub.real / (P + Q * np.cos(kk2 * d0) + R * np.sin(kk2 * d0))
    if distort:
        t_aff = affine_scale * t0 + affine_offset
        t0 = t_aff + 4.0 * photo_curvature * t_aff * (1.0 - t_aff)
    if slit_on:
        t0 += slit_bias_at(slit_profiles, i_layer, 1.0)
    f0 = t0 - target_T_noisy
    if f0 == 0.0:
        return 0.0
    lo_a, hi_a = d0, d0
    f_lo, f_hi = f0, f0
    found = False
    a = d0
    b = d0
    fa = f0
    n_steps = int(d_max / step) + 1
    for s_idx in range(1, n_steps + 1):
        for side in range(2):
            if side == 0:
                d_new = d0 + s_idx * step
                if d_new > d_max:
                    continue
                d_old = hi_a
                f_old = f_hi
            else:
                d_new = d0 - s_idx * step
                if d_new < 0.0:
                    continue
                d_old = lo_a
                f_old = f_lo
            t = 4.0 * n_Sub.real / (P + Q * np.cos(kk2 * d_new) + R * np.sin(kk2 * d_new))
            if distort:
                t_aff = affine_scale * t + affine_offset
                t = t_aff + 4.0 * photo_curvature * t_aff * (1.0 - t_aff)
            if slit_on:
                t += slit_bias_at(slit_profiles, i_layer, d_new / nominal_th)
            f_new = t - target_T_noisy
            if (f_new <= 0.0 < f_old) or (f_old <= 0.0 < f_new) or (f_new >= 0.0 > f_old) or (f_old >= 0.0 > f_new):
                a = d_old
                b = d_new
                fa = f_old
                found = True
                break
            if side == 0:
                hi_a = d_new
                f_hi = f_new
            else:
                lo_a = d_new
                f_lo = f_new
        if found:
            break
    if not found:
        return _invert_thickness_from_probes(
            wl, n_current, nominal_th, probe_offset, n_Sub, M_before_00, M_before_01, M_before_10, M_before_11,
            affine_scale, affine_offset, photo_curvature, slit_profiles, i_layer, target_T_noisy,
        )
    for _ in range(60):
        mid = 0.5 * (a + b)
        t = 4.0 * n_Sub.real / (P + Q * np.cos(kk2 * mid) + R * np.sin(kk2 * mid))
        if distort:
            t_aff = affine_scale * t + affine_offset
            t = t_aff + 4.0 * photo_curvature * t_aff * (1.0 - t_aff)
        if slit_on:
            t += slit_bias_at(slit_profiles, i_layer, mid / nominal_th)
        fm = t - target_T_noisy
        if (fm > 0.0) == (fa > 0.0):
            a = mid
            fa = fm
        else:
            b = mid
    return 0.5 * (a + b) - nominal_th


# ---- D96: POEM'S ANCHORS AT THE EXTREMUM ITSELF, ON REQUEST (`exact_anchors`) ----
#
# On the coarse scan an anchor is the value of the SAMPLE at which the detector put the extremum: 16 samples per replayed
# layer, 64 over three thicknesses of the current one, so the sample falls up to half a step from the summit, by an amount
# that differs between the real and the nominal signal as soon as their thicknesses differ. 📏 Measured on 2026-10-10 on
# the judge of paix's winner, noise-free, upstream errors of 0.3 nm: the kernel's stop sits 0.055 nm RMS from the exact
# POEM stop, of which the inversion (D97) explains 0.021 nm RMS and the anchors the rest. The closed form of a layer
# (`layer_scan_coeffs`) gives its extrema exactly: T = 4 n_sub / (P -+ sqrt(Q^2 + R^2)), where 2kd = atan2(R, Q), plus pi
# for a maximum. The machine grid needs none of this: it reads the exact T at every reading.
@njit(cache=True, fastmath=True, nogil=True, error_model="numpy", inline="always")
def _closed_form_extremum(
    wl: float,
    n_layer: complex,
    n_Sub: complex,
    M00: complex,
    M01: complex,
    M10: complex,
    M11: complex,
    d_sample: float,
    window: float,
    d_hi: float,
    is_max: bool,
) -> tuple[bool, float, float, float]:
    """The extremum of kind `is_max` of a layer of index `n_layer` growing on the stack (M), the one nearest `d_sample`.

    Returns (found, its depth, T there, T at `d_sample`). Found when it lies within `window` of `d_sample` and inside the
    layer, [0, `d_hi`]; never on an absorbing layer (k above `K_MAX_CLOSED_FORM`), which has no closed form.
    """
    if abs(n_layer.imag) >= K_MAX_CLOSED_FORM:
        return False, 0.0, 0.0, 0.0
    P, Q, R = layer_scan_coeffs(M00, M01, M10, M11, n_layer, n_Sub)
    kk2 = 2.0 * TWO_PI / wl * n_layer.real
    den_s = P + Q * np.cos(kk2 * d_sample) + R * np.sin(kk2 * d_sample)
    amp = np.sqrt(Q * Q + R * R)
    den = P - amp if is_max else P + amp
    if amp <= 1e-15 or kk2 <= 1e-15 or den_s <= 1e-18 or den <= 1e-18:
        return False, 0.0, 0.0, 0.0
    # P + Q cos(2kd) + R sin(2kd) = P + amp cos(2kd - phi), phi = atan2(R, Q): T is largest where that is smallest.
    base = np.arctan2(R, Q) + (np.pi if is_max else 0.0)
    d_star = (base + TWO_PI * np.floor((kk2 * d_sample - base) / TWO_PI + 0.5)) / kk2
    found = abs(d_star - d_sample) <= window and d_star >= 0.0 and d_star <= d_hi
    return found, d_star, 4.0 * n_Sub.real / den, 4.0 * n_Sub.real / den_s


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy", inline="always")
def _exact_poem_anchors(
    wl: float,
    n_Sub: complex,
    n_H_r: complex,
    n_L_r: complex,
    n_H: complex,
    n_L: complex,
    witness_base_layer: int,
    j0: int,
    i_layer: int,
    prev_thicknesses_sim: np.ndarray,
    p_thick_nominal: np.ndarray,
    n_hist: int,
    npts_cur: int,
    d_max: float,
    Ts_r: np.ndarray,
    Ts_n: np.ndarray,
    n_tot: int,
    affine_scale: float,
    photo_curvature: float,
    slit_profiles: np.ndarray | None,
    T_prev_real: float,
    T_last_real: float,
    T_prev_nom: float,
    T_last_nom: float,
) -> tuple[float, float, float, float]:
    """POEM's two anchors on each signal of the coarse scan, moved to the extremum of the layer they fall in (D96).

    Returns (T_prev_real, T_last_real, T_prev_nom, T_last_nom), the arguments of the same names. An anchor is one of the
    samples of `Ts_r` or `Ts_n`, found by its value; its kind is read against the other anchor of its pair, since a
    maximum and a minimum alternate. The nominal anchor becomes the extremum of the nominal layer. The real one keeps the
    reading noise of its sample, takes T and the slit bias at the depth of the extremum, and goes through the
    instrument's distortion exactly: the reading before the curvature is recovered from the anchor itself. An anchor
    whose layer has no extremum of its kind within two samples of it keeps its value: a turning point on a layer
    boundary, which the scan samples exactly, or an absorbing layer.
    """
    NPTS_PREV = SCAN_NPTS_HISTORY
    slit_on = slit_profiles is not None and slit_profiles.shape[0] > 0
    c4 = 4.0 * photo_curvature
    vals = np.array([T_prev_real, T_last_real, T_prev_nom, T_last_nom])
    out = vals.copy()
    for a in range(4):
        real = a < 2
        sig = Ts_r if real else Ts_n
        idx = -1
        for k in range(n_tot):
            if sig[k] == vals[a]:
                idx = k
                break
        if idx < 0:
            continue
        is_max = vals[a] > vals[a + 1 - 2 * (a % 2)]
        th = prev_thicknesses_sim if real else p_thick_nominal
        if idx < n_hist:  # a replayed layer: its sample k (1 .. 16) is at k / 16 of the layer
            j = j0 + idx // NPTS_PREV
            step = th[j] / NPTS_PREV
            d_s = (idx % NPTS_PREV + 1) * step
            d_hi = th[j]
        else:  # the layer being grown, swept over [0, d_max]
            j = i_layer
            step = d_max / (npts_cur - 1)
            d_s = (idx - n_hist) * step
            d_hi = d_max
        n_even = n_H_r if real else n_H
        n_odd = n_L_r if real else n_L
        M00, M01, M10, M11 = _stack_matrix(wl, n_even, n_odd, th, witness_base_layer, j)
        found, d_star, t_ext, t_at = _closed_form_extremum(
            wl, n_even if j % 2 == 0 else n_odd, n_Sub, M00, M01, M10, M11, d_s, 2.0 * step, d_hi, is_max
        )
        if not found:
            continue
        if not real:
            out[a] = t_ext
            continue
        delta = t_ext - t_at
        if slit_on and p_thick_nominal[j] > 1e-9:  # the profile is indexed by depth / nominal thickness of the layer
            inv_nom = 1.0 / p_thick_nominal[j]
            delta += slit_bias_at(slit_profiles, j, d_star * inv_nom) - slit_bias_at(slit_profiles, j, d_s * inv_nom)
        # The instrument reads t + c4 t (1 - t), t = a T + b: t is the root of that quadratic nearest the reading, written
        # in its stable form (it is the reading itself when c4 = 0), moved by a * delta, and read back.
        disc = (1.0 + c4) * (1.0 + c4) - 4.0 * c4 * vals[a]
        t_aff = 2.0 * vals[a] / ((1.0 + c4) + np.sqrt(disc)) if disc >= 0.0 else vals[a]
        t_aff += affine_scale * delta
        out[a] = t_aff + c4 * t_aff * (1.0 - t_aff)
    return out[0], out[1], out[2], out[3]
