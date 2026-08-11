import numpy as np
from numba import njit, prange
import math
from certus.core.certus_core import TWO_PI
from certus.physics.certus_opt_kernels import compute_RT_from_matrix
from certus.physics.certus_tmm_core import compute_TMM_single_point_k0_exact

NON_MONOTONIC_MODE_ATTENUATE = 0
NON_MONOTONIC_MODE_REJECT = 1
K_MAX_LAYER_BACKSIDE: float = 0.001
K_MAX_SUBSTRATE_BACKSIDE: float = 0.00001

# ── NON-TERMINATING DEPOSITION SENTINELS, DECOMPOSED BY CAUSE ────────────────
#
# THE THREE CAUSES PREVIOUSLY RETURNED THE SAME VALUE, CREATING A DIAGNOSTIC BLINDSPOT.
#
# `simulate_growth_kernel` inflated thickness by 1e6 in three unrelated situations.
# As long as they were conflated, it was impossible to know WHY a deposition did not finish.
#
# Values are multiples of 1e6 and nominal thickness remains added, so:
#   - any consumer checking `val > 1e5` counts exact same crashes as before.
#   - cause is readable via `int(val // 1e6)` without knowing nominal thickness.
#
# The three diagnostic causes correspond to:
# CRASH_LEVEL_UNREACHABLE answers "is target level reachable?",
# CRASH_TP_MISCOUNT answers "do we count expected turning points?".
#: Thickness deposited in ONE turntable revolution: 0.125 nm at 0.5 nm/s and 4 Hz
#: (9bis-1). Rate mode counts turns, so a commanded thickness is quantised to a
#: multiple of this -- which IS the U(0, 0.125 nm) stopping law of 9bis-7,
#: appearing on its own with no parameter to pose.
RATE_TURN_NM: float = 0.125

CRASH_SENTINEL_MIN: float = 100000.0
CRASH_SENTINEL_UNIT: float = 1000000.0
#: Target stopping level is not bracketed by signal before next extremum.
CRASH_LEVEL_UNREACHABLE: int = 1
#: Turning point count on real deposition differs from expected.
CRASH_TP_MISCOUNT: int = 2
#: Non-monotonic T(d) and REJECT mode requested: candidate is rejected.
CRASH_NON_MONOTONIC: int = 3
from .certus_strat_math import (
    check_extrema_proximity,
    calculate_extrema_distances,
    fit_parabola_vertex_3points,
    _seeded_noise_sample,
    _solve_quadratic_target,
    _calc_T_from_matrix,
    _calc_T_added_layer,
)


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def detect_turning_points(
    Ts: np.ndarray,
    n_tot: int,
    idx_stop: int,
    start_is_tp: bool,
    hysteresis: float,
) -> tuple[int, int, int]:
    """Counts the turning points of a monitoring signal and returns the last two.

    Returns ``(n_tp, tp_a, tp_b)``: the number of extrema located at or before ``idx_stop``,
    then the indices of the last two retained (``-1`` if absent). Same selection convention
    as legacy code: beyond ``idx_stop`` an extremum is only retained if none has been retained yet.

    SINGLE FUNCTION FOR BOTH REAL AND NOMINAL SIGNALS - THIS IS ESSENTIAL.
    Divergent counting between real and nominal signals is one of the primary crash modes.
    Detecting extrema with two separately written loops risks algorithmic divergence rather than
    physical divergence.

    ``hysteresis`` -- DETECTION RULE, in units of T:

        0.0  Legacy rule: an extremum is declared as soon as the difference between
             two consecutive samples changes sign beyond a NUMERICAL guard of 1e-12.
             This is not a physical rule, and produces a crash rate that DOES NOT DEPEND ON NOISE:
             1.47% per layer at sigma = 5e-8 vs 1.30% at real instrument noise. Where the monitoring
             signal lacks dynamic range (e.g. rejection band where T_front is 1e-5 to 1e-7),
             noisy counting diverges from clean counting regardless of noise magnitude.

        > 0  HYSTERESIS detector (modeling real hardware controllers): tracks the current extremum,
             and only DECLARES it when the signal has deviated from it by more than ``hysteresis``.
             A ripple smaller than this threshold produces no turning point.

             The returned index is that of the extremum ITSELF, not the threshold crossing time:
             the physical machine records the extreme value it observed, not the time it realized
             it had passed it.

             THIS THRESHOLD DERIVES FROM NOISE, NOT AN AMPLITUDE CRITERION.
             The 4% starting amplitude rule from Zideluns p. 112 is a wavelength PRE-SELECTION
             heuristic -- a way to guess in advance what Monte-Carlo measures directly.
             This detection threshold should not borrow its value from that heuristic.

             The governing quantity is reading noise, which is MEASURED:
             On the OMS 5100, the signal fluctuates from 45.5 to 45.55% T (peak-to-peak amplitude
             `trigger_tolerance` = 0.05 points). The draw is bounded to +/- this amplitude
             (truncated N(0, A/3) law), so the maximum apparent deviation from noise alone is 2A:

                 hysteresis >= 2 x trigger_tolerance / 100
                 -> noise alone can NEVER fabricate a false turning point reversal.

    The threshold applies to the NOMINAL signal as well. It represents what the strategy
    EXPECTS to count; evaluating it with a different rule than the physical machine
    would induce artificial per-layer counting divergence.
    """
    tp_a = -1
    tp_b = -1
    n_tp = 0
    if start_is_tp:
        n_tp += 1
        tp_b = 0

    if hysteresis <= 0.0:
        for k in range(1, n_tot - 1):
            dl = Ts[k] - Ts[k - 1]
            dr = Ts[k + 1] - Ts[k]
            if (dl > 1e-15 and dr < -1e-15) or (dl < -1e-15 and dr > 1e-15):
                if k <= idx_stop:
                    n_tp += 1
                if k <= idx_stop or tp_b < 0:
                    tp_a = tp_b
                    tp_b = k
        return (n_tp, tp_a, tp_b)

    # Hysteresis detector. Simultaneously tracks current maximum and minimum;
    # `dirn` is 0 until direction is established by first threshold crossing.
    maxv = Ts[0]
    minv = Ts[0]
    maxi = 0
    mini = 0
    dirn = 0
    for k in range(1, n_tot):
        v = Ts[k]
        if v > maxv:
            maxv = v
            maxi = k
        if v < minv:
            minv = v
            mini = k
        emit = -1
        if dirn >= 0 and maxv - v > hysteresis:
            emit = maxi
            dirn = -1
            minv = v
            mini = k
        elif dirn <= 0 and v - minv > hysteresis:
            emit = mini
            dirn = 1
            maxv = v
            maxi = k
        # Index 0 is already declared by `start_is_tp`: do not double count.
        if emit < 0 or (start_is_tp and emit == 0):
            continue
        if emit <= idx_stop:
            n_tp += 1
        if emit <= idx_stop or tp_b < 0:
            tp_a = tp_b
            tp_b = emit
    return (n_tp, tp_a, tp_b)


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def turning_point_margins(
    Ts: np.ndarray, n_tot: int, hysteresis: float
) -> tuple[float, float]:
    """How close the turning-point COUNT came to being wrong, both ways -- A23 stage 2.

    Returns ``(margin_missed, margin_fabricated)``, both in transmission units:

    * ``margin_missed`` = ``smallest emitted swing - hysteresis``. An extremum is only
      seen once the signal has retraced by more than the threshold, so a ripple that
      only just exceeds it is one noise realisation away from going UNCOUNTED.
    * ``margin_fabricated`` = ``hysteresis - largest excursion that did NOT emit``. The
      symmetric failure: an excursion that nearly crossed the threshold is one noise
      realisation away from being counted as an extremum that never existed.

    🔑 WHY A MARGIN AND NOT A RATE. At 150 draws a crash rate of 0/150 says p < 2 % and
    nothing more, and every strategy on this stack reads 0. A margin is CONTINUOUS and
    defined even when nothing failed, so it ranks strategies that a rate cannot
    separate. It is also the better Trap-1 control: it must scale as 1/sigma, and a
    margin that does not move with the noise is an artefact -- a test far more
    sensitive than a rate that jumps from 0 to 1/N.

    ⚠️ TWO NUMBERS, NOT ONE, AND THEY DO NOT MERGE. A23 is explicit: the failure modes
    have neither the same units of physical meaning nor the same remedy. A layer whose
    ripple is too faint to be seen is cured by moving the wavelength; a layer where
    noise invents an extremum is cured by raising the threshold. Collapsing them into
    one figure is the very confusion Trap 1, corollary 2, warns against.

    Returns ``(1e18, 1e18)`` when no extremum is emitted at all -- there is then no
    counting constraint to be close to, which is not the same as being safe, and the
    caller must not read the sentinel as a large margin.

    Same detection rule as ``detect_turning_points``, deliberately duplicated rather
    than folded into it: that function is re-exported and used by the fabrication probe,
    and changing its return arity would break a measurement instrument for a diagnostic.
    One extra pass over an array is free next to the TMM evaluations around it.
    """
    if hysteresis <= 0.0 or n_tot < 2:
        return (1e18, 1e18)
    # The detector's own state -- maxv/minv/dirn -- is reproduced exactly, because the
    # emission decisions must be the ones the machine makes.
    maxv = Ts[0]
    minv = Ts[0]
    dirn = 0
    # 🔴 SEPARATE state for the SEGMENT peak-to-peak, and it must be reset on BOTH
    # sides at every emission. The detector only half-resets (it sets minv = v when it
    # emits a maximum, leaving maxv stale), which is correct for detection and wrong
    # for measuring "how big is the current wiggle": reusing it left a stale extreme in
    # the excursion, which then never fell below the threshold, and the fabrication
    # margin read its sentinel on EVERY input. A quantity that never varies with what
    # it measures is Trap 1 -- caught by sweeping the wiggle amplitude, not by a test.
    maxi = 0
    mini = 0
    seg_hi = Ts[0]
    seg_lo = Ts[0]
    min_swing = 1e18       # smallest RIPPLE between two consecutive emitted extrema
    prev_ext = 0.0
    n_emit = 0
    for k in range(1, n_tot):
        v = Ts[k]
        if v > maxv:
            maxv = v
            maxi = k
        if v < minv:
            minv = v
            mini = k
        if v > seg_hi:
            seg_hi = v
        if v < seg_lo:
            seg_lo = v
        emit_idx = -1
        if dirn >= 0 and maxv - v > hysteresis:
            emit_idx = maxi
            dirn = -1
            minv = v
            mini = k
        elif dirn <= 0 and v - minv > hysteresis:
            emit_idx = mini
            dirn = 1
            maxv = v
            maxi = k
        if emit_idx >= 0:
            # 🔴 THE RIPPLE IS THE DISTANCE BETWEEN TWO CONSECUTIVE EXTREMA, not the
            # segment span at the moment of emission. A first version measured the
            # latter, which is ~= hysteresis BY CONSTRUCTION -- emission happens as
            # soon as the retracement crosses the threshold -- so the margin read
            # ~0 whether the ripple was 1.2x or 20x the threshold. Sweeping the
            # amplitude is what exposed it: a margin that does not follow the
            # quantity it measures is Trap 1, and it would have shipped looking fine.
            ext = Ts[emit_idx]
            if n_emit > 0:
                swing = ext - prev_ext
                if swing < 0.0:
                    swing = -swing
                if swing < min_swing:
                    min_swing = swing
            prev_ext = ext
            n_emit += 1
            seg_hi = v
            seg_lo = v
    cur_exc = seg_hi - seg_lo
    # 🔴 THE TWO GUARDS ARE SEPARATE, and merging them hid the most interesting case.
    # A single `if n_emit == 0: return sentinel, sentinel` killed fabrication exactly
    # where it matters most: a layer whose signal is too flat to emit anything is
    # precisely the one where noise is closest to inventing an extremum. The two
    # quantities have different preconditions -- a ripple needs TWO extrema to be
    # measured, a near-fabrication needs NONE.
    m_missed = min_swing if n_emit >= 2 else 1e18
    if m_missed < 1e17:
        m_missed = m_missed - hysteresis
    # ⚠️ THE TRAILING SEGMENT IS NOT A NEAR-FABRICATION, and reading it as one gives
    # nonsense. After the last emission the signal is usually mid-swing: its excursion
    # keeps growing and would emit, the array simply ends first. Taking
    # `hysteresis - cur_exc` there returned -398 A on a clean sine -- a "fabrication
    # margin" that is negative, i.e. an excursion that crossed the threshold without
    # emitting, which cannot happen. Caught by a sanity check, not by the tests.
    #
    # A trailing excursion only carries fabrication information while it stays BELOW
    # the threshold. Above it, there is no near-miss to measure and the sentinel says
    # "no constraint" rather than inventing one.
    m_fab = (hysteresis - cur_exc) if cur_exc < hysteresis else 1e18
    return (m_missed, m_fab)


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def next_turning_point_after(Ts: np.ndarray, n_tot: int, i_start: int, hysteresis: float) -> int:
    """Index of the first turning point located after ``i_start``, or ``n_tot - 1`` if none.

    Used to bound the window for the level reachability test: beyond the next
    extremum, the signal turns around and the target level will never be reached.

    **Same detection rule as ``detect_turning_points``**, and it is required:
    otherwise a micro-extremum fabricated by noise just after stopping would
    truncate the window and cause a crash that the machine would not suffer --
    exactly the artifact that hysteresis exists to suppress.
    """
    if hysteresis <= 0.0:
        for k in range(i_start + 1, n_tot - 1):
            dl = Ts[k] - Ts[k - 1]
            dr = Ts[k + 1] - Ts[k]
            if (dl > 1e-12 and dr < -1e-12) or (dl < -1e-12 and dr > 1e-12):
                return k
        return n_tot - 1

    if i_start + 1 >= n_tot:
        return n_tot - 1
    maxv = Ts[i_start]
    minv = Ts[i_start]
    maxi = i_start
    mini = i_start
    dirn = 0
    for k in range(i_start + 1, n_tot):
        v = Ts[k]
        if v > maxv:
            maxv = v
            maxi = k
        if v < minv:
            minv = v
            mini = k
        if dirn >= 0 and maxv - v > hysteresis:
            if maxi > i_start:
                return maxi
            dirn = -1
            minv = v
            mini = k
        elif dirn <= 0 and v - minv > hysteresis:
            if mini > i_start:
                return mini
            dirn = 1
            maxv = v
            maxi = k
    return n_tot - 1


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def simulate_growth_kernel(
    p_thick_nominal: np.ndarray,
    i_layer: int,
    prev_thicknesses_sim: np.ndarray,
    wl: float,
    n_H,
    n_L,
    n_Sub,
    probe_offset: float,
    noise_val_precalc: float,
    non_monotonic_factor: float,
    non_monotonic_mode: int = NON_MONOTONIC_MODE_ATTENUATE,
    block_start_layer: int = -1,
    signal_noise_scale: float = 0.0,
    signal_noise_seed: int = 0,
    signal_noise_run: int = 0,
    tp_hysteresis: float = 0.0,
    affine_scale: float = 1.0,
    affine_offset: float = 0.0,
    poem_enabled: bool = True,
    smoothing_window: int = 1,
    n_H_real: float = -1.0,
    n_L_real: float = -1.0,
    is_rate: bool = False,
) -> tuple[float, float, float, float, float]:
    """

    Fast TMM Simulation for robustness heuristics.

    CRITICAL PHYSICS NOTE:

    This kernel calculates T_front (Internal Transmission) ONLY.

    It intentionally IGNORES backside reflection for computational speed in heuristics.

    Do not use for absolute photometric accuracy. Use calculate_detailed_growth for that.

    This is a RELATIVE control kernel: target extraction and inversion both use the

    same front-only model, so there is no absolute backside mismatch in this loop.

    Args:

        non_monotonic_mode: How to handle non-monotonic T(d) curves:

            0 (ATTENUATE): Divide error by non_monotonic_factor (legacy)

            1 (REJECT): Return large penalty to reject candidate

        signal_noise_scale: AXIS 1.1 -- scale of the READING noise applied to the
            REAL monitoring signal ``Ts_r``, in units of T (0..1), BEFORE detecting
            turning points, reading POEM anchors, and testing level reachability.
            0.0 = disabled, and the computation path is then word for word the one
            from before this parameter. See the "READING NOISE" block below.

        signal_noise_seed: seed of the reading noise stream. Must be a function
            of the draw configuration only (seed, noise level) and NEVER of the
            evaluated strategy: this is what preserves common random numbers.

        signal_noise_run: Monte-Carlo draw index. Same requirement.

        tp_hysteresis: AXIS 1.2 -- THE TURNING POINT DETECTION RULE, in units of T.
            0.0 = historical rule (sign change beyond a numerical guard of 1e-12),
            which is not a physical rule. > 0 = hysteresis detector. See
            ``detect_turning_points``, which contains the derivation of the
            threshold from measured noise -- and why it is NOT the 4% criterion
            from Zideluns.

            🔴 WITHOUT THIS PARAMETER, `signal_noise_scale` IS NOT MEASURABLE:
            the crash rate it produces does not depend on sigma (1.47% per layer at
            sigma = 5e-8 versus 1.30% at the real sigma), so it does not measure noise.

        affine_scale, affine_offset: PHOTOMETRIC CALIBRATION DRIFT of the instrument,
            T_measured = affine_scale * T_true + affine_offset. Applied to the REAL
            monitoring signal ``Ts_r`` and to the three probe points of the parabolic
            inversion -- and to nothing else. ``Ts_n`` is the offline design: no
            instrument reads it, so no instrument can distort it. (1.0, 0.0) = disabled,
            and the computation path is then word for word the one from before these
            parameters.

            POEM is EXACTLY invariant under this transform; the absolute fallback is
            not. That contrast IS the measurement these parameters exist to make. Any
            code cancelling the distortion on one side of a comparison destroys it --
            three such cancellations were removed on 2026-08-08, see the comment at the
            inversion below.

    """
    if wl < 0.1:
        # No monitoring wavelength: nothing is read, so neither margin is constrained.
        return (float(p_thick_nominal[i_layer]), 0.0, 1e18, 1e18, 1e18)

    # ---- RATE MODE (14, A24) -------------------------------------------------
    #
    # The machine stops watching and counts turntable revolutions instead. It needs a
    # deposition rate to convert a thickness into a number of turns, and 👤 settled how
    # it gets one (2026-08-11):
    #
    #   Q2  Rate is FORBIDDEN until a layer of this material has been deposited under
    #       photometric control -- without one there is no measured rate at all.
    #   Q4  the estimate AVERAGES over every previous layer of the material.
    #   Q3  it CHAINS: the last deposited layer is a reference, Rate ones included.
    #
    # 🔑 sigma_rate IS NOT A PARAMETER. The machine compares turns observed against the
    # thickness it BELIEVES it deposited -- the nominal one, since nothing told it
    # otherwise -- and the simulator holds both numbers. So its estimate is reproduced,
    # not replaced by a draw. There is nothing to tune here.
    #
    #   layer k, deposited under POEM: real d_real_k, so n_k = d_real_k / q turns,
    #   while the machine believes d_nom_k. Its rate estimate is v.d_nom_k/d_real_k.
    #   Averaged:  v_hat = v . mean_k(d_nom_k / d_real_k) = v . A
    #   Rate layer i: it commands round(d_nom_i / (A.q)) turns, hence
    #
    #       d_real_i = round(d_nom_i / (A.q)) . q
    #
    # 📏 Without the rounding this is d_nom_i / A, i.e. the HARMONIC MEAN of the
    # previous ratios -- so averaging divides the inherited scatter by sqrt(n): 2,0 %
    # at one reference layer, 0,41 % at twenty-four (measured 2026-08-11). The Rate
    # gets steadily more accurate deeper into the stack.
    #
    # 🟢 And the rounding IS 9bis-7's U(0, 0.125 nm) stopping quantisation, appearing
    # on its own with no parameter to pose: one turn at 0.5 nm/s and 4 Hz is 0.125 nm.
    #
    # ⚠️ C2 is safe BY CONSTRUCTION, and it is worth saying why. A Rate layer reads
    # nothing, so it consumes no reading noise -- and that shifts nothing, because
    # `_seeded_noise_sample` is a pure function of (seed, group, run, element), a hash
    # and not a sequential stream. Skipping draws cannot misalign another layer. This
    # is exactly the property 12.4 chose the generator for.
    if is_rate:
        n_ref = 0
        acc = 0.0
        for j in range(i_layer - 2, -1, -2):        # same parity = same material
            d_real_j = prev_thicknesses_sim[j]
            d_nom_j = p_thick_nominal[j]
            if d_real_j > 1e-9 and d_nom_j > 1e-9:
                acc += d_nom_j / d_real_j
                n_ref += 1
        if n_ref > 0:                                # Q2: otherwise fall through to POEM
            a_est = acc / n_ref
            d_nom_i = p_thick_nominal[i_layer]
            if a_est > 1e-9 and d_nom_i > 0.0:
                turns = np.round(d_nom_i / (a_est * RATE_TURN_NM))
                if turns < 1.0:
                    turns = 1.0
                # dyn = -1.0 flags "NOT MONITORED": this layer has no observed swing at
                # all, and averaging a 0.0 into the dynamics profile would report it as
                # a catastrophically flat layer instead of an unwatched one.
                # Both counting margins are sentinels, and that is not a shortcut: with
                # no trigger, a Rate layer CANNOT suffer CRASH_LEVEL_UNREACHABLE nor
                # CRASH_TP_MISCOUNT. It removes those two failure modes on itself --
                # and hands the cost to the next layer, which loses its anchors (14-10).
                return (float(turns * RATE_TURN_NM), -1.0, 1e18, 1e18, 1e18)

    TWO_PI_VAL = TWO_PI
    n_H_r = n_H if n_H_real.real < 0.0 else n_H_real
    n_L_r = n_L if n_L_real.real < 0.0 else n_L_real

    M_before_00 = 1.0 + 0j
    M_before_01 = 0.0 + 0j
    M_before_10 = 0.0 + 0j
    M_before_11 = 1.0 + 0j
    for j in range(i_layer):
        n_prev = n_H_r if j % 2 == 0 else n_L_r
        th_prev = prev_thicknesses_sim[j]
        phi = TWO_PI_VAL / wl * n_prev * th_prev
        cp, sp = (np.cos(phi), np.sin(phi))
        son = sp / n_prev if abs(n_prev) > 1e-09 else 0.0
        m01 = +1j * son
        m10 = +1j * n_prev * sp
        t00 = cp * M_before_00 + m01 * M_before_10
        t01 = cp * M_before_01 + m01 * M_before_11
        t10 = m10 * M_before_00 + cp * M_before_10
        t11 = m10 * M_before_01 + cp * M_before_11
        M_before_00, M_before_01, M_before_10, M_before_11 = (t00, t01, t10, t11)
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
    M_nom_00 = 1.0 + 0j
    M_nom_01 = 0.0 + 0j
    M_nom_10 = 0.0 + 0j
    M_nom_11 = 1.0 + 0j
    for j in range(i_layer):
        n_prev = n_H if j % 2 == 0 else n_L
        th_prev_nom = p_thick_nominal[j]
        phi = TWO_PI_VAL / wl * n_prev * th_prev_nom
        cp, sp = (np.cos(phi), np.sin(phi))
        son = sp / n_prev if abs(n_prev) > 1e-09 else 0.0
        m01 = +1j * son
        m10 = +1j * n_prev * sp
        t00 = cp * M_nom_00 + m01 * M_nom_10
        t01 = cp * M_nom_01 + m01 * M_nom_11
        t10 = m10 * M_nom_00 + cp * M_nom_10
        t11 = m10 * M_nom_01 + cp * M_nom_11
        M_nom_00, M_nom_01, M_nom_10, M_nom_11 = (t00, t01, t10, t11)

    nominal_th = p_thick_nominal[i_layer]
    n_current = n_H if i_layer % 2 == 0 else n_L
    is_non_monotonic = False
    T_mono = np.zeros(5, dtype=np.float64)
    T_mono_nom = np.zeros(5, dtype=np.float64)  # same scan, NOMINAL stack
    k_ext = -1  # index of the last extremum crossed (swing), -1 if none
    if nominal_th > 0.0001:
        for k in range(5):
            th_frac = k / 4.0 * nominal_th
            phi_c = TWO_PI_VAL / wl * n_current * th_frac
            cp_c, sp_c = (np.cos(phi_c), np.sin(phi_c))
            son_c = sp_c / n_current if abs(n_current) > 1e-09 else 0.0
            m01_c = +1j * son_c
            m10_c = +1j * n_current * sp_c
            a00 = cp_c * M_before_00 + m01_c * M_before_10
            a01 = cp_c * M_before_01 + m01_c * M_before_11
            a10 = m10_c * M_before_00 + cp_c * M_before_10
            a11 = m10_c * M_before_01 + cp_c * M_before_11
            denom = a00 + n_Sub * a01 + a10 + n_Sub * a11
            if abs(denom) > 1e-09:
                T_mono[k] = 4.0 * n_Sub.real / (denom.real**2 + denom.imag**2)
            # same point, but on the NOMINAL matrix: this is the value the
            # controller EXPECTED to see pass.
            b00 = cp_c * M_nom_00 + m01_c * M_nom_10
            b01 = cp_c * M_nom_01 + m01_c * M_nom_11
            b10 = m10_c * M_nom_00 + cp_c * M_nom_10
            b11 = m10_c * M_nom_01 + cp_c * M_nom_11
            den_n = b00 + n_Sub * b01 + b10 + n_Sub * b11
            if abs(den_n) > 1e-09:
                T_mono_nom[k] = 4.0 * n_Sub.real / (den_n.real**2 + den_n.imag**2)
        diffs = np.zeros(4, dtype=np.float64)
        for k in range(4):
            diffs[k] = T_mono[k + 1] - T_mono[k]
        flips = 0
        current_sign = 0.0
        if diffs[0] > 1e-09:
            current_sign = 1.0
        elif diffs[0] < -1e-09:
            current_sign = -1.0
        for k in range(1, 4):
            next_sign = 0.0
            if diffs[k] > 1e-09:
                next_sign = 1.0
            elif diffs[k] < -1e-09:
                next_sign = -1.0
            if next_sign != 0.0:
                if current_sign != 0.0 and next_sign != current_sign:
                    flips += 1
                current_sign = next_sign
        if flips > 0:
            is_non_monotonic = True
    # FROZEN trigger level, calculated on the nominal and not on the real.
    target_nominal = 0.0
    if nominal_th > 0.0001:
        phi_t = TWO_PI_VAL / wl * n_current * nominal_th
        cp_t, sp_t = (np.cos(phi_t), np.sin(phi_t))
        son_t = sp_t / n_current if abs(n_current) > 1e-09 else 0.0
        mt01 = +1j * son_t
        mt10 = +1j * n_current * sp_t
        b00 = cp_t * M_nom_00 + mt01 * M_nom_10
        b01 = cp_t * M_nom_01 + mt01 * M_nom_11
        b10 = mt10 * M_nom_00 + cp_t * M_nom_10
        b11 = mt10 * M_nom_01 + cp_t * M_nom_11
        den_t = b00 + n_Sub * b01 + b10 + n_Sub * b11
        if abs(den_t) > 1e-09:
            target_nominal = 4.0 * n_Sub.real / (den_t.real**2 + den_t.imag**2)
    else:
        target_nominal = T_mono[4]

    # ------------------------------------------------------------------------
    # POEM -- Percent of Optical Extrema Monitoring
    #
    #   T_POEM = (T_trigger - T_prev_TP) / (T_last_TP - T_prev_TP)      (Arsac
    #   these 2025, eq. 2.2 ; Zideluns et al., Opt. Express 29, 33398 (2021))
    #
    # The stopping point is NOT a transmission value but a FRACTION of the
    # photometric amplitude between the last two turning points. The fraction
    # is pre-calculated on the NOMINAL and frozen before deposition; at runtime
    # it is reported on the ACTUALLY observed extrema.
    #
    # Consequence, and this is the whole point: if the real signal undergoes an
    # affine distortion T_real = a*T_nom + b -- gain drift or photometric offset,
    # index error, upstream thickness error -- then T_prev and T_last undergo
    # the same, and the reported level is a*T_trigger_nom + b. We thus stop
    # exactly at the desired thickness. Compensation is obtained by CHANGE OF
    # VARIABLE, not by a manually tuned reduction coefficient.
    #
    # "If the current layer has less than two turning points, the virtual next
    #  turning points are used": we extend the scan beyond d_nom.
    #
    # Fallback: if the swing amplitude is too weak (< SWING_MIN, cf. the 4%
    # minimum starting amplitude of Zideluns et al.), POEM is ill-conditioned
    # and we fall back on the frozen absolute target.
    # 64 points and not 5: locating a turning point with 5 points neither allows
    # distinguishing a clear extremum from a shoulder, nor counting several of them.
    # Cost: 64 T evaluations per layer and per run, versus 8 previously.
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
    NPTS = 64
    NPTS_PREV = 16
    MAX_LOOKBACK = 4
    D_SCAN = 3.0
    SWING_MIN = 0.04
    apply_signal_noise = signal_noise_scale > 0.0
    poem_ok = False
    # A23 stage 2. Both in TRANSMISSION units, normalised to multiples of A upstream --
    # the kernel is not told what A is and must not guess it. 1e18 = "no constraint of
    # this kind here", which is NOT the same as "safe" and must never be averaged.
    margin_level = 1e18      # distance of the stopping level from the reachable band
    # 🔴 THE TWO COUNTING CAUSES STAY SEPARATE, and A23 says so in as many words:
    # "one margin per layer is too coarse -- it takes one per layer AND per cause".
    # Merging them into min(missed, fabricated) was tried and measured: the number
    # jumped from 0.15 A to 505 A between two noise levels, a factor 3000, purely
    # because the BINDING CAUSE switched. That reads as a bug and hides the only thing
    # an operator can act on -- a faint ripple is cured by moving the wavelength, an
    # invented extremum by raising the threshold. Trap 1, corollary 2.
    margin_missed = 1e18     # ripple too faint  -> an extremum goes UNCOUNTED
    margin_fab = 1e18        # noise excursion   -> an extremum is INVENTED
    T_prev_real = 0.0
    T_last_real = 0.0
    T_prev_nom = 0.0
    T_last_nom = 0.0
    if nominal_th > 0.0001:
        j0 = block_start_layer
        if j0 < 0 or j0 > i_layer:
            j0 = i_layer
        if i_layer - j0 > MAX_LOOKBACK:
            j0 = i_layer - MAX_LOOKBACK
        n_hist = (i_layer - j0) * NPTS_PREV
        n_tot = n_hist + NPTS
        Ts_r = np.zeros(n_tot, dtype=np.float64)
        Ts_n = np.zeros(n_tot, dtype=np.float64)
        R00, R01, R10, R11 = (1.0 + 0j, 0.0 + 0j, 0.0 + 0j, 1.0 + 0j)
        Q00, Q01, Q10, Q11 = (1.0 + 0j, 0.0 + 0j, 0.0 + 0j, 1.0 + 0j)
        for j in range(j0):
            n_p_r = n_H_r if j % 2 == 0 else n_L_r
            n_p_n = n_H if j % 2 == 0 else n_L
            ph1 = TWO_PI_VAL / wl * n_p_r * prev_thicknesses_sim[j]
            c1, s1 = (np.cos(ph1), np.sin(ph1))
            so1 = s1 / n_p_r if abs(n_p_r) > 1e-09 else 0.0
            a0 = c1 * R00 + 1j * so1 * R10
            a1 = c1 * R01 + 1j * so1 * R11
            a2 = 1j * n_p_r * s1 * R00 + c1 * R10
            a3 = 1j * n_p_r * s1 * R01 + c1 * R11
            R00, R01, R10, R11 = (a0, a1, a2, a3)
            ph2 = TWO_PI_VAL / wl * n_p_n * p_thick_nominal[j]
            c2, s2 = (np.cos(ph2), np.sin(ph2))
            so2 = s2 / n_p_n if abs(n_p_n) > 1e-09 else 0.0
            b0 = c2 * Q00 + 1j * so2 * Q10
            b1 = c2 * Q01 + 1j * so2 * Q11
            b2 = 1j * n_p_n * s2 * Q00 + c2 * Q10
            b3 = 1j * n_p_n * s2 * Q01 + c2 * Q11
            Q00, Q01, Q10, Q11 = (b0, b1, b2, b3)
        idx = 0
        for j in range(j0, i_layer):
            n_j_r = n_H_r if j % 2 == 0 else n_L_r
            n_j_n = n_H if j % 2 == 0 else n_L
            d_rj = prev_thicknesses_sim[j]
            d_nj = p_thick_nominal[j]
            for k in range(1, NPTS_PREV + 1):
                f = k / NPTS_PREV
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
        d_max = D_SCAN * nominal_th
        step_s = d_max / (NPTS - 1)
        n_cur_r = n_H_r if i_layer % 2 == 0 else n_L_r
        n_cur_n = n_H if i_layer % 2 == 0 else n_L
        for k in range(NPTS):
            d_k = k * step_s
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

        if smoothing_window > 1:
            # ── AXIS 1.1 / T3-T4: decoupled machine sampling grid (0.125 nm) + moving-average smoothing
            SAMPLE_DD = 0.125
            M_hist = 0
            for j in range(j0, i_layer):
                M_hist += int(np.ceil(p_thick_nominal[j] / SAMPLE_DD))
            M_cur = int(np.ceil(D_SCAN * nominal_th / SAMPLE_DD)) + 1
            M_tot = M_hist + M_cur

            Ts_r_samp = np.empty(M_tot, dtype=np.float64)
            Ts_n_samp = np.empty(M_tot, dtype=np.float64)

            idx_src = 0
            idx_dst = 0
            for j in range(j0, i_layer):
                d_rj = prev_thicknesses_sim[j]
                d_nj = p_thick_nominal[j]
                M_pj = int(np.ceil(d_nj / SAMPLE_DD))
                tmm_sub_r = Ts_r[idx_src : idx_src + NPTS_PREV]
                tmm_sub_n = Ts_n[idx_src : idx_src + NPTS_PREV]
                inv_drj_npts = (NPTS_PREV / d_rj) * SAMPLE_DD if d_rj > 1e-9 else 0.0
                inv_dnj_npts = (NPTS_PREV / d_nj) * SAMPLE_DD if d_nj > 1e-9 else 0.0
                kr_flt = 0.0
                kn_flt = 0.0
                for m in range(M_pj):
                    kr_low = min(max(0, int(kr_flt)), NPTS_PREV - 1)
                    kr_frac = kr_flt - kr_low
                    kr_hi = min(kr_low + 1, NPTS_PREV - 1)
                    vr = (1.0 - kr_frac) * tmm_sub_r[kr_low] + kr_frac * tmm_sub_r[kr_hi]

                    kn_low = min(max(0, int(kn_flt)), NPTS_PREV - 1)
                    kn_frac = kn_flt - kn_low
                    kn_hi = min(kn_low + 1, NPTS_PREV - 1)
                    vn = (1.0 - kn_frac) * tmm_sub_n[kn_low] + kn_frac * tmm_sub_n[kn_hi]

                    Ts_r_samp[idx_dst] = vr
                    Ts_n_samp[idx_dst] = vn

                    if apply_signal_noise:
                        Ts_r_samp[idx_dst] += signal_noise_scale * _seeded_noise_sample(
                            signal_noise_seed, j, signal_noise_run, m, True
                        )
                    idx_dst += 1
                    kr_flt += inv_drj_npts
                    kn_flt += inv_dnj_npts
                idx_src += NPTS_PREV

            tmm_cur_r = Ts_r[n_hist : n_hist + NPTS]
            tmm_cur_n = Ts_n[n_hist : n_hist + NPTS]
            d_max_cur = D_SCAN * nominal_th
            fc_step = ((NPTS - 1) / d_max_cur) * SAMPLE_DD if d_max_cur > 1e-9 else 0.0
            fc_flt = 0.0
            for m in range(M_cur):
                kc_low = min(max(0, int(fc_flt)), NPTS - 2)
                kc_frac = fc_flt - kc_low
                kc_hi = kc_low + 1

                vr = (1.0 - kc_frac) * tmm_cur_r[kc_low] + kc_frac * tmm_cur_r[kc_hi]
                vn = (1.0 - kc_frac) * tmm_cur_n[kc_low] + kc_frac * tmm_cur_n[kc_hi]

                Ts_r_samp[idx_dst] = vr
                Ts_n_samp[idx_dst] = vn

                if apply_signal_noise:
                    g_noise = i_layer
                    e_noise = 4096 + m
                    if m == 0 and M_hist > 0:
                        g_noise = i_layer - 1
                        prev_M = int(np.ceil(p_thick_nominal[i_layer - 1] / SAMPLE_DD))
                        e_noise = prev_M - 1
                    Ts_r_samp[idx_dst] += signal_noise_scale * _seeded_noise_sample(
                        signal_noise_seed, g_noise, signal_noise_run, e_noise, True
                    )
                idx_dst += 1
                fc_flt += fc_step

            n_tot = M_tot
            Ts_r = Ts_r_samp
            Ts_n = Ts_n_samp
            idx_nom_stop = M_hist + int(round(nominal_th / SAMPLE_DD))
        else:
            if affine_scale != 1.0 or affine_offset != 0.0:
                for k_aff in range(n_tot):
                    Ts_r[k_aff] = affine_scale * Ts_r[k_aff] + affine_offset
            idx_nom_stop = n_hist + int(round((NPTS - 1) / D_SCAN))

        if smoothing_window > 1:
            if affine_scale != 1.0 or affine_offset != 0.0:
                for k_aff in range(n_tot):
                    Ts_r[k_aff] = affine_scale * Ts_r[k_aff] + affine_offset
            k_win = smoothing_window
            Ts_r_raw = Ts_r.copy()
            Ts_n_raw = Ts_n.copy()
            sum_r = 0.0
            sum_n = 0.0
            for idx_w in range(n_tot):
                sum_r += Ts_r_raw[idx_w]
                sum_n += Ts_n_raw[idx_w]
                if idx_w >= k_win:
                    sum_r -= Ts_r_raw[idx_w - k_win]
                    sum_n -= Ts_n_raw[idx_w - k_win]
                w_len = idx_w + 1 if idx_w < k_win else k_win
                Ts_r[idx_w] = sum_r / w_len
                Ts_n[idx_w] = sum_n / w_len
        # ---- THE BARE SUBSTRATE IS A TURNING POINT, AND IT WAS IGNORED ----------
        #
        # Physicist, 2026-08-05: "for layer 1 we start the layer on a turning point,
        # but that is mandatory".
        #
        # This is correct and automatic. For a single layer on substrate,
        # R(d) = A + B.cos(2.delta) with delta = 2.pi.n.d/lambda, therefore
        # dR/dd proportional to sin(2.delta), which VANISHES at d = 0. Numerically
        # verified (n_H = 2.35, substrate 1.52, lambda = 500 nm): slope at d = 0 of
        # -8.0e-4 per nm versus -7.9e-3 in the middle of the quarter wave, which is
        # ten times less -- the residue comes from the finite difference on a 2.5 nm
        # step, the true derivative is zero.
        #
        # However the detection loop starts at k = 1: an EDGE extremum is structurally
        # invisible. Consequence measured on the example, whose first multiplier
        # is 1.556 (thus idx_nom_stop ~ 33):
        #
        #     detected extrema    [21, 42]        d = 53.2 and 106.4 nm
        #     k = 21 <= 33        tp_b = 21, tp_a remains -1
        #     k = 42 >  33        rejected because tp_b >= 0
        #     => tp_a = -1  =>  poem_ok = FALSE on layer 0
        #
        # Layer 0 therefore fell back on the absolute target, without compensation.
        # And this explained why it had only ONE surviving wavelength out of ~51
        # scanned, hence the absence of a common lambda with layer 1, hence the
        # force_monolayer fallback which fabricates an invalid edge.
        #
        # 🔴 THIS ANCHOR IS THE MOST RELIABLE OF ALL. At d = 0 on layer 0, the real
        # stack and the nominal stack are the SAME object -- the bare substrate.
        # T_prev_real = T_prev_nom exactly, with no upstream error possible, and
        # the machine measures this level even before starting.
        #
        # Intentionally narrow condition: only the first layer of the stack (i_layer == 0,
        # thus j0 == 0). For a block starting higher, d = 0 of its first layer is NOT an
        # extremum in general: the sub-stack already deposited has no reason to be
        # stationary there.
        start_is_tp = i_layer == 0 and j0 == 0
        # The REAL signal: what the machine counts.
        n_tp_real, tp_a, tp_b = detect_turning_points(
            Ts_r, n_tot, idx_nom_stop, start_is_tp, tp_hysteresis
        )
        # The NOMINAL signal: what the strategy expects of it. SAME detection
        # rule, imperatively -- the two countings also serve to detect the
        # DIVERGENCE of the number of extrema, which is one of the two crash
        # modes, and two different rules would fabricate one at each layer.
        # Counting the edge on one side and not the other would have the same effect.
        n_tp_nom, tp_a_n, tp_b_n = detect_turning_points(
            Ts_n, n_tot, idx_nom_stop, start_is_tp, tp_hysteresis
        )
        # A23 stage 2, counting side. Measured on the REAL signal -- the one the
        # machine reads. The binding margin is the smaller of the two ways the count
        # can go wrong; they are returned separately by `turning_point_margins` and
        # combined here only because one number per (run, layer) is what the batch can
        # carry. The CAUSE is recoverable from the sentinel when it actually crashes.
        margin_missed, margin_fab = turning_point_margins(Ts_r, n_tot, tp_hysteresis)
        if tp_a >= 0 and tp_b >= 0 and tp_a_n >= 0 and tp_b_n >= 0:
            # fraction: NOMINAL anchors  |  report: MEASURED REAL anchors
            T_prev_nom = Ts_n[tp_a_n]
            T_last_nom = Ts_n[tp_b_n]
            T_prev_real = Ts_r[tp_a]
            T_last_real = Ts_r[tp_b]
            amp_nom = T_last_nom - T_prev_nom
            amp_real = T_last_real - T_prev_real
            # SWING_MIN is a floor in MEASURED units. POEM is ill-conditioned when the
            # amplitude between the two anchors is small compared to reading noise, and
            # reading noise is what the instrument reports, hence measured units too.
            # Scaling the threshold by `affine_scale` cancelled the gain exactly and
            # made the test blind to the very distortion it must survive.
            if poem_enabled and abs(amp_nom) > SWING_MIN and abs(amp_real) > SWING_MIN:
                poem_ok = True

    if poem_ok:
        # frozen fraction, calculated on the nominal (eq. 2.2)
        p_poem = (target_nominal - T_prev_nom) / (T_last_nom - T_prev_nom)
        # reported on the actually observed extrema
        target_level = T_prev_real + p_poem * (T_last_real - T_prev_real)
    else:
        # ABSOLUTE FALLBACK -- the controller does NOT know (affine_scale, affine_offset).
        #
        # It was handed a level computed offline from the nominal design, in TRUE T
        # units, and it compares that number against what its instrument reports, in
        # MEASURED units. Pre-distorting the level to `a * target + b` gave the
        # controller back the calibration it is precisely assumed to have lost, which
        # made absolute monitoring immune to gain and offset drift. That immunity is
        # what POEM provides and absolute monitoring does not -- cancelling it here
        # erased the only contrast these parameters exist to measure.
        target_level = target_nominal

    target_T_noisy = target_level + noise_val_precalc

    # ---- HARD FAILURE: the stopping level is never reached ----------
    #
    # Very unfavorable case reported in the room: if the theoretical stop falls
    # JUST BEFORE a turning point, an upstream error can make the signal turn
    # before having reached the targeted value. The machine waits for a level
    # that will never come and the deposition goes into a tailspin. It's not a
    # loss of precision, it's a CRASH -- a discrete event, invisible to an RMSE
    # criterion as long as it's not explicitly detected.
    #
    # This is why stopping AFTER a turning point is much safer: the extremum
    # is already counted, the signal moves away from it monotonically, and the
    # level is inevitably reached. This is also the justification for the
    # asymmetry of check_extrema_proximity -- forbidden zone 3x wider BEFORE
    # a turning point than AFTER.
    #
    # We model the failure here as it happens: if the targeted level is not
    # bracketed by the real signal between the start of the layer and the next
    # extremum, the run is lost.
    #
    # ⚠ THIS TEST MUST NOT DEPEND ON poem_ok. It did, and it was a hole.
    #
    # Whether a level is reachable or not is a question of signal PHYSICS, not
    # of the anchoring strategy used to calculate it. Keeping the detection
    # behind `poem_ok` deactivated it precisely in cases where POEM is
    # ill-conditioned -- swing below SWING_MIN, fewer than two turning points --
    # which are exactly the most exposed.
    #
    # Measurement on example/example_strat/JSON-strat-example.json, 48 layers x 51
    # scan wavelengths, upstream error of +2 nm, zero noise:
    #   detected crash                           :  0.21 %
    #   SILENT fallback on vertex (disc < 0)     :  6.68 %   <- 30 times more
    #
    # These 6.68% came out of _solve_quadratic_target through its
    # `discriminant < 0` branch (certus_strat_math.py:207), which returns the
    # vertex of the parabola without reporting anything: median error 5.2 nm,
    # maximum 29 nm, where 0.05 nm is already worth less than an atom. The
    # verified rate did NOT depend on probe_offset (6.63% at 0.5 nm, 6.88% at
    # 10 nm): it was not a fit artifact, but the physical failure itself, uncounted.
    if nominal_th > 0.0001:
        i_lay0 = n_hist
        i_stop = idx_nom_stop
        # upper bound: next real extremum after stop, else end of scan.
        # Same detection rule as counting, cf. next_turning_point_after.
        i_end = next_turning_point_after(Ts_r, n_tot, i_stop, tp_hysteresis)
        t_lo = Ts_r[i_lay0]
        t_hi = Ts_r[i_lay0]
        for k in range(i_lay0, i_end + 1):
            if Ts_r[k] < t_lo:
                t_lo = Ts_r[k]
            if Ts_r[k] > t_hi:
                t_hi = Ts_r[k]
        # ✅ NO TOLERANCE HERE, AND THIS IS INTENDED.
        #
        # I thought for a moment that an overshoot of the order of noise should be
        # tolerated, on the grounds that a quarter-wave stack monitored at its own
        # centering wavelength crashed at 100%. This was my mistake: this 100% is
        # the CORRECT result.
        #
        # At exact QWOT the stop falls on the turning point, where dT/dd = 0: a
        # level no longer has any thickness sensitivity, and half of the noise
        # realizations place the target beyond the extremum, where it will never
        # be reached. This is exactly why a QWOT is not monitored at its lambda_0
        # by level cut-off -- and it is STRAT's job to go look elsewhere.
        # check_extrema_proximity exists for the same reason.
        # A23 stage 2, level side: how far INSIDE the reachable band the target sits.
        # Positive = that much room to spare, negative = missed by that much. Signed on
        # purpose: a crashed layer still carries how badly, which is what lets the 2x
        # noise level calibrate the model where crashes are countable (A23 stage 3).
        d_lo = target_T_noisy - t_lo
        d_hi = t_hi - target_T_noisy
        margin_level = d_lo if d_lo < d_hi else d_hi
        if target_T_noisy < t_lo - 1e-12 or target_T_noisy > t_hi + 1e-12:
            # level never reached: non-terminable deposition
            return (
                nominal_th + CRASH_LEVEL_UNREACHABLE * CRASH_SENTINEL_UNIT,
                np.max(T_mono) - np.min(T_mono),
                margin_level,
                margin_missed,
                margin_fab,
            )
        # Divergent extrema counting between nominal and real: the machine
        # does not anchor POEM on the same turning points as the strategy.
        # This one, however, REMAINS conditioned to poem_ok: without POEM there is
        # no anchoring on turning points, so nothing that can diverge.
        if poem_ok and n_tp_real != n_tp_nom:
            return (
                nominal_th + CRASH_TP_MISCOUNT * CRASH_SENTINEL_UNIT,
                np.max(T_mono) - np.min(T_mono),
                margin_level,
                margin_missed,
                margin_fab,
            )
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
    if affine_scale != 1.0 or affine_offset != 0.0:
        for k in range(3):
            T_points[k] = affine_scale * T_points[k] + affine_offset
    a_quad, b_quad, c_quad = fit_parabola_vertex_3points(th_points, T_points)
    calc_thick = _solve_quadratic_target(a_quad, b_quad, c_quad, target_T_noisy, nominal_th)
    error_raw = calc_thick - nominal_th
    dyn_encounter = 0.0
    if nominal_th > 0.0001:
        dyn_encounter = np.max(T_mono) - np.min(T_mono)
    if is_non_monotonic:
        if non_monotonic_mode == NON_MONOTONIC_MODE_REJECT:
            return (
                nominal_th + CRASH_NON_MONOTONIC * CRASH_SENTINEL_UNIT,
                dyn_encounter,
                margin_level,
                margin_missed,
                margin_fab,
            )
        # non_monotonic_factor IS NO LONGER APPLIED.
        #
        # It divided the error by a constant (default 2.0) as soon as an extremum
        # was crossed. This was the reduced form of the information gain brought
        # by the swing -- a band-aid, made necessary by the fact that the model
        # COULD NOT produce this gain itself: the target being recalculated on
        # the real stack, error_raw only contained local noise and there was
        # nothing to correct.
        #
        # With the frozen target and POEM, the swing gain is now STRUCTURAL:
        # it varies with the actually observed contrast and with the number
        # of extrema, instead of being the same for a layer that grazes an
        # extremum and a layer that crosses three. Dividing it on top of that
        # would amount to double-counting the same effect.
        #
        # The parameter is kept in the signature to avoid breaking the six
        # call sites; it is now only used for the REJECT mode above.
        return (
        max(0.0, nominal_th + error_raw), dyn_encounter,
        margin_level, margin_missed, margin_fab,
    )
    return (
        max(0.0, nominal_th + error_raw), dyn_encounter,
        margin_level, margin_missed, margin_fab,
    )


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def compute_T_front_at_layer(
    wl: float, n_layer, n_Sub, M_before_00, M_before_01, M_before_10, M_before_11, d: float
) -> float:
    """

    Compute front-side T at end of a single layer (same convention as simulate_growth_kernel).

    Used to compute dT/dd for converting thickness noise (nm) to transmission noise.

    """
    if wl < 0.1:
        return 0.0
    TWO_PI_VAL = TWO_PI
    phi = TWO_PI_VAL / wl * n_layer * d
    cp, sp = (np.cos(phi), np.sin(phi))
    son = sp / n_layer if abs(n_layer) > 1e-09 else 0.0
    m01 = +1j * son
    m10 = +1j * n_layer * sp
    a00 = cp * M_before_00 + m01 * M_before_10
    a01 = cp * M_before_01 + m01 * M_before_11
    a10 = m10 * M_before_00 + cp * M_before_10
    a11 = m10 * M_before_01 + cp * M_before_11
    denom = a00 + n_Sub * a01 + a10 + n_Sub * a11
    if abs(denom) > 1e-09:
        return float(4.0 * np.real(n_Sub) / (denom.real**2 + denom.imag**2))
    return 0.0


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def compute_T_front_profile(
    wl: float,
    n_layer,
    n_Sub,
    M_before_00,
    M_before_01,
    M_before_10,
    M_before_11,
    d_array: np.ndarray,
) -> np.ndarray:
    """Front-side T over a WHOLE thickness grid, in a single call.

    Same calculation as ``compute_T_front_at_layer``, point by point: the loop is
    simply passed to the compiled side. The arithmetic is identical, so the
    results are bit-for-bit identical.

    Motive: ``_compute_theoretical_layer_profile`` sampled the T(d) curve
    every nanometer from Python, which is ~200 Python->njit boundary crossings
    per layer, repeated for each strategy and each Monte-Carlo draw. The calculation
    itself is negligible compared to this dispatch cost.
    """
    n = d_array.shape[0]
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        out[i] = compute_T_front_at_layer(
            wl, n_layer, n_Sub, M_before_00, M_before_01, M_before_10, M_before_11, d_array[i]
        )
    return out


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def compute_dT_dd_kernel(
    layer_wavelengths: np.ndarray,
    n_H_vals: np.ndarray,
    n_L_vals: np.ndarray,
    n_Sub_vals: np.ndarray,
    p_thick_arr: np.ndarray,
    M_before_all: np.ndarray,
    h_nm: float,
) -> np.ndarray:
    """dT/dd by centered difference, for all layers in one call.

    Direct transposition of the final loop of ``_compute_dT_dd_per_layer``:
    same operations in the same order, thus same results bit for bit. It made
    two njit calls per layer from Python; on a forty-layer stack, evaluated for
    each candidate strategy, the dispatch cost exceeded the calculation cost.
    """
    num_layers = p_thick_arr.shape[0]
    dT_dd = np.zeros(num_layers, dtype=np.float64)

    for i in range(num_layers):
        wl_i = layer_wavelengths[i]

        if wl_i < 0.1:
            dT_dd[i] = 1e-6
            continue

        n_current = n_H_vals[i] if (i % 2) == 0 else n_L_vals[i]
        n_Sub = n_Sub_vals[i]
        d_nom = p_thick_arr[i]

        M00 = M_before_all[i, 0, 0]
        M01 = M_before_all[i, 0, 1]
        M10 = M_before_all[i, 1, 0]
        M11 = M_before_all[i, 1, 1]

        d_plus = d_nom + h_nm
        d_minus = max(0.1, d_nom - h_nm)

        T_plus = compute_T_front_at_layer(wl_i, n_current, n_Sub, M00, M01, M10, M11, d_plus)
        T_minus = compute_T_front_at_layer(wl_i, n_current, n_Sub, M00, M01, M10, M11, d_minus)

        denom = d_plus - d_minus
        dT_dd[i] = (T_plus - T_minus) / denom if denom > 1e-9 else 1e-6

    return dT_dd


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def prepare_dynamics_data_kernel(
    wls_array: np.ndarray,
    all_wls: np.ndarray,
    nominal_matrix_cache: np.ndarray,
    n_H_arr: np.ndarray,
    n_L_arr: np.ndarray,
    n_Sub_arr: np.ndarray,
    i_layer: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """

    Parallel preparation of data for dynamics calculation.

    """
    n = len(wls_array)
    n_layer_array = np.empty(n, dtype=np.complex128)
    n_sub_array = np.empty(n, dtype=np.complex128)
    M_before_stack = np.empty((n, 2, 2), dtype=np.complex128)
    for i in prange(n):
        wl = wls_array[i]
        if i_layer % 2 == 0:
            n_layer_array[i] = n_H_arr[i]
        else:
            n_layer_array[i] = n_L_arr[i]
        n_sub_array[i] = n_Sub_arr[i]
        M_before_stack[i, 0, 0] = 1.0
        M_before_stack[i, 0, 1] = 0.0
        M_before_stack[i, 1, 0] = 0.0
        M_before_stack[i, 1, 1] = 1.0
        if i_layer > 0:
            idx = np.searchsorted(all_wls, wl)
            if idx >= len(all_wls):
                idx = len(all_wls) - 1
            elif idx > 0:
                diff_curr = abs(wl - all_wls[idx])
                diff_prev = abs(wl - all_wls[idx - 1])
                if diff_prev < diff_curr:
                    idx = idx - 1
            M_before_stack[i, 0, 0] = nominal_matrix_cache[i_layer - 1, idx, 0, 0]
            M_before_stack[i, 0, 1] = nominal_matrix_cache[i_layer - 1, idx, 0, 1]
            M_before_stack[i, 1, 0] = nominal_matrix_cache[i_layer - 1, idx, 1, 0]
            M_before_stack[i, 1, 1] = nominal_matrix_cache[i_layer - 1, idx, 1, 1]
    return (n_layer_array, n_sub_array, M_before_stack)


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def compute_dynamics_kernel(wls, n_layers, n_subs, thicknesses, M_befores):
    """

    Compute TMM dynamics: peak-to-peak range of T(d) over layer growth.

    For each wavelength, T(d) is evaluated at thickness steps from 0 to

    nominal thickness. The dynamics metric is T_max - T_min (not endpoint

    delta). Returns dynamics, t_init, t_final, t_min (min T over growth).

    Precision adapts to input dtypes via Numba JIT.

    """
    n_wls = wls.shape[0]
    n_steps = thicknesses.shape[0]
    dynamics = np.empty(n_wls, dtype=np.float64)
    t_init = np.empty(n_wls, dtype=np.float64)
    t_final = np.empty(n_wls, dtype=np.float64)
    t_min = np.empty(n_wls, dtype=np.float64)
    I_VAL = +1j
    for wl_idx in prange(n_wls):
        wl = wls[wl_idx]
        n_layer = n_layers[wl_idx]
        n_sub = n_subs[wl_idx]
        M_before_00 = M_befores[wl_idx, 0, 0]
        M_before_01 = M_befores[wl_idx, 0, 1]
        M_before_10 = M_befores[wl_idx, 1, 0]
        M_before_11 = M_befores[wl_idx, 1, 1]
        T_min_val = 2.0
        T_max = -1.0
        T_start = 0.0
        T_end = 0.0
        for step_idx in range(n_steps):
            thickness = thicknesses[step_idx]
            if wl < 0.1:
                T_current = 0.0
            else:
                phi = TWO_PI / wl * n_layer * thickness
                cp, sp = (np.cos(phi), np.sin(phi))
                son = sp / n_layer if abs(n_layer) > 1e-09 else 0.0
                m01 = I_VAL * son
                m10 = I_VAL * n_layer * sp
                a00 = cp * M_before_00 + m01 * M_before_10
                a01 = cp * M_before_01 + m01 * M_before_11
                a10 = m10 * M_before_00 + cp * M_before_10
                a11 = m10 * M_before_01 + cp * M_before_11
                denom = a00 + n_sub * a01 + a10 + n_sub * a11
                if abs(denom) > 1e-09:
                    T_current = 4.0 * np.real(n_sub) / (denom.real**2 + denom.imag**2)
                else:
                    T_current = 0.0
            if step_idx == 0:
                T_start = T_current
            if step_idx == n_steps - 1:
                T_end = T_current
            if T_current < T_min_val:
                T_min_val = T_current
            if T_current > T_max:
                T_max = T_current
        dynamics[wl_idx] = T_max - T_min_val
        t_init[wl_idx] = T_start
        t_final[wl_idx] = T_end
        t_min[wl_idx] = T_min_val
    return (dynamics, t_init, t_final, t_min)


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def update_run_states_kernel(
    p_thick_nom_arr: np.ndarray,
    i_layer: int,
    prev_stacks: np.ndarray,
    best_wl: float,
    nH,
    nL,
    nSub,
    offset_val: float,
    noise_values: np.ndarray,
    factor_val: float,
    non_monotonic_mode: int = NON_MONOTONIC_MODE_ATTENUATE,
    block_start_layer: int = -1,
    signal_noise_scale: float = 0.0,
    signal_noise_seed: int = 0,
    tp_hysteresis: float = 0.0,
    affine_scale_amp: float = 0.0,
    affine_offset_amp: float = 0.0,
    affine_seed: int = 0,
    poem_enabled: bool = True,
    smoothing_window: int = 1,
    index_corridor: float = 0.0,
    index_seed: int = 0,
    corridor_lo: float = 0.0,
    corridor_hi: float = 0.0,
):
    """Parallel update of simulation states for next layer.

    ``block_start_layer`` must be the one OF THE RETAINED WAVELENGTH. The states
    propagated here become the history on which the next layer will be judged:
    evaluating them without the block history while the candidates were evaluated
    with it would produce a Phase A inconsistent with itself.

    ``signal_noise_scale`` / ``signal_noise_seed`` : reading noise of the monitoring
    signal (axis 1.1, cf. ``simulate_growth_kernel``). They must be THOSE OF THE
    CANDIDATE VALIDATION, for the same reason as ``block_start_layer``. The draw
    index passed to the kernel is ``r``, the same one that was used to judge the
    candidates.

    🔴 AND THE SAME REASON EXTENDS TO SIX MORE PARAMETERS -- defect 17-23.

    This function used to hand the kernel 16 arguments out of 22, so ``affine_scale``,
    ``affine_offset``, ``poem_enabled``, ``smoothing_window`` and the corridor indices
    silently took their NEUTRAL defaults. Phase A therefore judged its candidates in a
    world carrying photometric drift, an index corridor, reading smoothing and possibly
    no POEM -- and then remembered what happened in a clean one. The history was
    systematically kinder than the world it was history of, at every layer.

    The principle was already written three paragraphs above; only the list of
    parameters it applies to was incomplete. **Anything that changes how a layer grows
    must be passed here identically to how it was passed to the candidate validation.**

    ⚠️ AMPLITUDES ARE TAKEN, NOT DRAWN VALUES -- and that is C2, not a style choice.
    The distortion and the corridor are drawn ONCE PER RUN. Accepting a ready-made
    ``affine_scale`` here would have applied one single draw to every run, which is a
    fresh violation committed while repairing another. The draw is therefore redone
    inside the loop, from the same seeds and the same run index the candidate
    validation used, so both see EXACTLY the same randomness.
    """
    num_runs = prev_stacks.shape[0]
    updates = np.empty(num_runs, dtype=np.float64)
    if index_corridor > 0.0 and corridor_hi <= corridor_lo:
        raise ValueError(
            "index_corridor is active but corridor_lo/corridor_hi were not supplied; "
            "the envelope must come from the single caller-side computation"
        )
    for r in prange(num_runs):
        if affine_scale_amp != 0.0 or affine_offset_amp != 0.0:
            aff_s = 1.0 + affine_scale_amp * _seeded_noise_sample(affine_seed, 0, r, 0, True)
            aff_o = affine_offset_amp * _seeded_noise_sample(affine_seed, 1, r, 0, True)
        else:
            aff_s = 1.0
            aff_o = 0.0
        if index_corridor > 0.0:
            z1_h = _seeded_noise_sample(index_seed, 0, r, 0, True)
            z2_h = _seeded_noise_sample(index_seed, 0, r, 1, True)
            z1_l = _seeded_noise_sample(index_seed, 1, r, 0, True)
            z2_l = _seeded_noise_sample(index_seed, 1, r, 1, True)
            u_wl = (2.0 * best_wl - (corridor_lo + corridor_hi)) / (corridor_hi - corridor_lo)
            nH_real = nH + (index_corridor * z1_h + index_corridor * z2_h * (1.0 - abs(z1_h)) * u_wl)
            nL_real = nL + (index_corridor * z1_l + index_corridor * z2_l * (1.0 - abs(z1_l)) * u_wl)
        else:
            nH_real = nH
            nL_real = nL
        updates[r], _, _, _, _ = simulate_growth_kernel(
            p_thick_nom_arr,
            i_layer,
            prev_stacks[r],
            best_wl,
            nH,
            nL,
            nSub,
            offset_val,
            noise_values[r],
            factor_val,
            non_monotonic_mode,
            block_start_layer,
            signal_noise_scale,
            signal_noise_seed,
            r,
            tp_hysteresis,
            aff_s,
            aff_o,
            poem_enabled,
            smoothing_window,
            nH_real,
            nL_real,
        )
    return updates


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def calculate_detailed_growth(
    num_layers, p_thick_nominal, layer_wavelengths, n_H_arr, n_L_arr, n_Sub_arr, steps_per_layer_arr
):
    """

    Detailed growth simulation with exact physics.

    CRITICAL PHYSICS NOTE:

    This function computes T_total including INCOHERENT BACKSIDE reflection.

    T_val = (Tf * T_ext) / (1.0 - Rf * R_ext)

    Matches the "Real World" signal seen by the monitor.

    The expression is intentionally expanded inline (instead of routing through

    compute_RT_from_matrix) for step-wise growth performance. Keep formulas aligned.

    """
    if num_layers == 0:
        return (np.zeros(1), np.zeros(1), np.zeros(1))
    total_steps = np.sum(steps_per_layer_arr)
    total_points = total_steps + num_layers + 1
    x_points = np.empty(total_points)
    y_points = np.empty(total_points)
    layer_boundaries = np.empty(num_layers + 1)
    current_idx = 0
    cumulative_thick = 0.0
    layer_boundaries[0] = 0.0
    F00 = 1.0 + 0j
    F01 = 0.0 + 0j
    F10 = 0.0 + 0j
    F11 = 1.0 + 0j
    R00 = 1.0 + 0j
    R01 = 0.0 + 0j
    R10 = 0.0 + 0j
    R11 = 1.0 + 0j
    prev_wl = -1.0
    for i_layer in range(num_layers):
        target_th = p_thick_nominal[i_layer]
        current_wl = layer_wavelengths[i_layer]
        if current_wl < 0.1:
            current_wl = 1500.0
        n_l_target = n_H_arr[i_layer] if i_layer % 2 == 0 else n_L_arr[i_layer]
        n_s = n_Sub_arr[i_layer]
        nsr = n_s.real
        R_ext = ((nsr - 1.0) / (nsr + 1.0)) ** 2
        T_ext = 1.0 - R_ext
        if i_layer > 0 and abs(current_wl - prev_wl) > 0.001:
            F00 = 1.0 + 0j
            F01 = 0.0 + 0j
            F10 = 0.0 + 0j
            F11 = 1.0 + 0j
            R00 = 1.0 + 0j
            R01 = 0.0 + 0j
            R10 = 0.0 + 0j
            R11 = 1.0 + 0j
            k0 = TWO_PI / current_wl
            for j in range(i_layer):
                dj = p_thick_nominal[j]
                nj = n_H_arr[i_layer] if j % 2 == 0 else n_L_arr[i_layer]
                phi = k0 * nj * dj
                cp = np.cos(phi)
                isp = +1j * np.sin(phi)
                mj01 = isp / nj if abs(nj) > 1e-09 else 0j
                mj10 = isp * nj
                t00 = cp * F00 + mj01 * F10
                t01 = cp * F01 + mj01 * F11
                t10 = mj10 * F00 + cp * F10
                t11 = mj10 * F01 + cp * F11
                F00, F01, F10, F11 = (t00, t01, t10, t11)
                t00 = R00 * cp + R01 * mj10
                t01 = R00 * mj01 + R01 * cp
                t10 = R10 * cp + R11 * mj10
                t11 = R10 * mj01 + R11 * cp
                R00, R01, R10, R11 = (t00, t01, t10, t11)
        k0_curr = TWO_PI / current_wl
        denom_f = F00 + n_s * F01 + F10 + n_s * F11
        denom_r = n_s * R00 + n_s * R01 + R10 + R11
        if abs(denom_f) > 1e-12 and abs(denom_r) > 1e-12:
            Tf = 4.0 * nsr / (denom_f.real**2 + denom_f.imag**2)
            num_r = n_s * R00 + n_s * R01 - R10 - R11
            Rf = (num_r.real**2 + num_r.imag**2) / (denom_r.real**2 + denom_r.imag**2)
            T_val = Tf * T_ext / (1.0 - Rf * R_ext)
        else:
            T_val = 0.0
        x_points[current_idx] = cumulative_thick
        y_points[current_idx] = T_val
        current_idx += 1
        steps = steps_per_layer_arr[i_layer]
        step_sz = target_th / steps
        for s in range(1, steps + 1):
            d_partial = step_sz * s
            phi = k0_curr * n_l_target * d_partial
            cp = np.cos(phi)
            isp = +1j * np.sin(phi)
            mj01 = isp / n_l_target if abs(n_l_target) > 1e-09 else 0j
            mj10 = isp * n_l_target
            ft00 = cp * F00 + mj01 * F10
            ft01 = cp * F01 + mj01 * F11
            ft10 = mj10 * F00 + cp * F10
            ft11 = mj10 * F01 + cp * F11
            rt00 = R00 * cp + R01 * mj10
            rt01 = R00 * mj01 + R01 * cp
            rt10 = R10 * cp + R11 * mj10
            rt11 = R10 * mj01 + R11 * cp
            denom_f = ft00 + n_s * ft01 + ft10 + n_s * ft11
            denom_r = n_s * rt00 + n_s * rt01 + rt10 + rt11
            if abs(denom_f) > 1e-12 and abs(denom_r) > 1e-12:
                Tf = 4.0 * nsr / (denom_f.real**2 + denom_f.imag**2)
                num_r = n_s * rt00 + n_s * rt01 - rt10 - rt11
                Rf = (num_r.real**2 + num_r.imag**2) / (denom_r.real**2 + denom_r.imag**2)
                val = Tf * T_ext / (1.0 - Rf * R_ext)
            else:
                val = 0.0
            x_points[current_idx] = cumulative_thick + d_partial
            y_points[current_idx] = val
            current_idx += 1
        phi_full = k0_curr * n_l_target * target_th
        cp = np.cos(phi_full)
        isp = +1j * np.sin(phi_full)
        mf01 = isp / n_l_target if abs(n_l_target) > 1e-09 else 0j
        mf10 = isp * n_l_target
        t00 = cp * F00 + mf01 * F10
        t01 = cp * F01 + mf01 * F11
        t10 = mf10 * F00 + cp * F10
        t11 = mf10 * F01 + cp * F11
        F00, F01, F10, F11 = (t00, t01, t10, t11)
        t00 = R00 * cp + R01 * mf10
        t01 = R00 * mf01 + R01 * cp
        t10 = R10 * cp + R11 * mf10
        t11 = R10 * mf01 + R11 * cp
        R00, R01, R10, R11 = (t00, t01, t10, t11)
        cumulative_thick += target_th
        layer_boundaries[i_layer + 1] = cumulative_thick
        prev_wl = current_wl
    return (x_points[:current_idx], y_points[:current_idx], layer_boundaries)
