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
from .certus_strat_math import check_extrema_proximity_batch, _calc_T_from_matrix, _calc_T_added_layer, _seeded_noise_sample
from .certus_strat_growth import simulate_growth_kernel

# Number of reading noise points consumed per (run, layer) in `simulate_growth_kernel`:
# NPTS_PREV for historical re-scan + NPTS for current layer scan.
# Not used to size an array (noise is generated on demand), but documents stream footprint.
MONITOR_NOISE_SLOTS_PER_LAYER = 16 + 64


@njit(cache=True, nogil=True)
def corridor_wl_range(spectral_wls: np.ndarray, monitor_wls: np.ndarray) -> tuple[float, float]:
    """The lambda normalisation of the index perturbation -- ONE definition.

    delta_M(lambda) = a_M + b_M * u(lambda), with u normalised over [lo, hi] so that
    |u| <= 1 there. The constraint |a| + |b| <= delta_max then bounds |delta| by
    delta_max -- but ONLY inside [lo, hi]. Outside it the corridor is exceeded.

    👤 DECIDED 2026-08-10: "the index error is given on the spectral grid of the
    filter, not of the monitoring" -- and "it is on the max of the spectral grid /
    monitoring". So [lo, hi] is the interval ENCLOSING BOTH.

    In practice the spectral grid contains the monitoring wavelengths and the union
    collapses to the grid. The envelope is taken anyway because it can never be
    wrong, and because 13 records that `clues_at_wl` carries the union of the two
    grids WITH overflow out of range -- a monitoring wavelength can fall outside the
    scoring grid.

    ⚠️ Before this, [lo, hi] was the monitoring span alone. On a grid reaching 400 nm
    with monitoring over 480-620, u(400) = -2.14, so |delta| reached 2.1x the
    specified corridor -- and it did so at the edges of the spectrum, precisely where
    the uncompensable crossed mode does its damage. Every corridor figure measured
    before 2026-08-10 is therefore invalid as an absolute number.

    🔴 ONE caller computes this and passes it to the growth batch, the Phase A batch
    and the scoring kernel. If each recomputes it they drift apart, which is the
    defect this function was created to prevent in the first place.
    """
    lo = min(np.min(spectral_wls), np.min(monitor_wls))
    hi = max(np.max(spectral_wls), np.max(monitor_wls))
    if abs(hi - lo) < 1e-6:
        hi = lo + 100.0
    return lo, hi


@njit(parallel=True, cache=True, fastmath=True, nogil=True, error_model="numpy")
def validate_wavelengths_batch(
    candidate_wls,
    n_H_arr,
    n_L_arr,
    n_Sub_arr,
    runs_history,
    p_thick_nominal,
    i_layer,
    probe_offset,
    noise_values,
    non_monotonic_factor,
    non_monotonic_mode: int = NON_MONOTONIC_MODE_ATTENUATE,
    block_start_arr: np.ndarray = None,
    gain_probe_nm: float = 1.0,
    signal_noise_scale: float = 0.0,
    signal_noise_seed: int = 0,
    tp_hysteresis: float = 0.0,
    affine_scale_amp: float = 0.0,
    affine_offset_amp: float = 0.0,
    photo_curvature_amp: float = 0.0,
    affine_seed: int = 0,
    poem_enabled: bool = True,
    smoothing_window: int = 1,
    index_corridor: float = 0.0,
    index_seed: int = 0,
    corridor_lo: float = 0.0,
    corridor_hi: float = 0.0,
    rate_flags: np.ndarray = None,
    slit_profiles: np.ndarray = None,
):
    """Evaluates each candidate monitoring wavelength for ONE layer (Phase A).

    Returns an array (n_cands, 4):

        [c, 0]  P95(|Delta_d|)   LOCAL error, over runs that TERMINATE
        [c, 1]  standard dev     ditto
        [c, 2]  crash rate       fraction of non-terminating runs
        [c, 3]  compensation gain, or -1.0 if not measurable

    THREE CRITERIA, AND THEY ARE ORTHOGONAL.

    P95(|Delta_d|) only measures the LOCAL error of the layer. A layer can
    be locally precise yet AMPLIFY error received from upstream: across 48 layers,
    gain determines whether total error remains bounded, not local error.

    Furthermore, a 95th percentile is structurally BLIND to any event occurring in
    less than 5% of runs: a deposition failing 2 times out of 100 left no trace
    in P95, despite representing a lost run in production.

    Measurement on 48-layer dichroic, layer 25:
        lambda 550 nm -> gain 0.257  |  lambda 475 nm -> gain 4.35
    a factor of 17 between two wavelengths that P95 alone would rank in reverse order.

    gain_probe_nm: amplitude of injected upstream error for measuring gain.
    1.0 nm default -- twenty times above the threshold where physical thickness
    differences lose physical meaning (0.05 nm, less than one atom), and in the
    linear gain regime for most measured cases.

    block_start_arr: start index of monitoring block FOR EACH candidate.
    At unchanged lambda, signal is continuous and POEM leverages already crossed
    turning points; changing lambda resets history.
    Without this array, Phase A was BLIND to block value while Phase B modeled it.
    None = legacy behavior (each layer isolated).

    signal_noise_scale / signal_noise_seed: READING noise of monitoring signal.
    0.0 = disabled, giving bit-identical execution to historical code.

    COMPENSATION GAIN IS MEASURED AT ZERO READING NOISE.
    It is a derivative -- the response of the layer to a known upstream error --
    not a run simulation. Injecting noise adds variance to a deterministic quantity.
    """
    n_cands = len(candidate_wls)
    n_runs = runs_history.shape[0]
    results = np.zeros((n_cands, 4))
    error_buffer = np.empty((n_cands, n_runs), dtype=np.float64)
    d_nom = p_thick_nominal[i_layer]
    # 🔴 THE ENVELOPE IS SUPPLIED, NEVER DEDUCED HERE -- see 17-20.
    #
    # This used to read `wl_min = np.min(candidate_wls)`, which is wrong in a way that
    # produced perfectly plausible numbers. `candidate_wls` is the list FILTERED FOR
    # THIS LAYER, so the normalisation domain of u(lambda) changed from layer to layer:
    # the same draw (a, b) then represented a DIFFERENT dispersion curve at each layer,
    # and two candidates 60 nm apart saw the full corridor swing where the spectral
    # grid says they should see 20 % of it. Phase A and Phase B were modelling two
    # different machines, which 12.2 forbids in as many words.
    #
    # There is deliberately NO fallback. A caller that activates the corridor without
    # supplying the envelope is a programming error, and the previous silent
    # degradation reinstalled exactly the defect corrected on 2026-08-10 -- control 4
    # of 20: it produced no error, it produced a plausible result.
    if index_corridor > 0.0 and corridor_hi <= corridor_lo:
        raise ValueError(
            "index_corridor is active but corridor_lo/corridor_hi were not supplied; "
            "the envelope must come from the single caller-side computation"
        )
    wl_min = corridor_lo
    wl_max = corridor_hi
    # Normalised OUTSIDE the prange: numba's array analysis rejects a ternary whose two
    # branches differ in dimensionality, so `None` cannot be selected per iteration. The
    # inert sentinel is a (1, 0, 0) array -- its 2-D slice has shape (0, ...), which is
    # exactly the "no profile" the kernel already guards on, and it keeps ONE type.
    slit_on = slit_profiles is not None
    if slit_on:
        slit_arr = slit_profiles
    else:
        slit_arr = np.zeros((1, 0, 0), dtype=np.float64)
    for c_idx in prange(n_cands):
        wl = candidate_wls[c_idx]
        # Branch-free on purpose: any conditional assignment here gets unified to
        # float64 by the parfor type inference and then rejected as an array index.
        # The inert sentinel has one row, so the modulo pins it to 0; when profiles are
        # supplied it has n_cands rows and the modulo is the identity.
        c_slit = c_idx % slit_arr.shape[0]
        blk = -1
        if block_start_arr is not None:
            blk = block_start_arr[c_idx]
        n_ok = 0
        n_crash = 0
        for r_idx in range(n_runs):
            prev_th = runs_history[r_idx, :i_layer]
            if affine_scale_amp != 0.0 or affine_offset_amp != 0.0 or photo_curvature_amp != 0.0:
                z_a = _seeded_noise_sample(affine_seed, 0, r_idx, 0, True)
                z_b = _seeded_noise_sample(affine_seed, 1, r_idx, 0, True)
                z_c = _seeded_noise_sample(affine_seed, 2, r_idx, 0, True)
                aff_s = 1.0 + affine_scale_amp * z_a
                aff_o = affine_offset_amp * z_b
                photo_curv = photo_curvature_amp * z_c
            else:
                aff_s = 1.0
                aff_o = 0.0
                photo_curv = 0.0

            if index_corridor > 0.0:
                z1_h = _seeded_noise_sample(index_seed, 0, r_idx, 0, True)
                z2_h = _seeded_noise_sample(index_seed, 0, r_idx, 1, True)
                a_h = index_corridor * z1_h
                b_h = index_corridor * z2_h * (1.0 - abs(z1_h))

                z1_l = _seeded_noise_sample(index_seed, 1, r_idx, 0, True)
                z2_l = _seeded_noise_sample(index_seed, 1, r_idx, 1, True)
                a_l = index_corridor * z1_l
                b_l = index_corridor * z2_l * (1.0 - abs(z1_l))

                u_wl = (2.0 * wl - (wl_min + wl_max)) / (wl_max - wl_min)
                nH_real = n_H_arr[c_idx] + (a_h + b_h * u_wl)
                nL_real = n_L_arr[c_idx] + (a_l + b_l * u_wl)
            else:
                nH_real = n_H_arr[c_idx]
                nL_real = n_L_arr[c_idx]

            val, _, _, _, _ = simulate_growth_kernel(
                p_thick_nominal,
                i_layer,
                prev_th,
                wl,
                n_H_arr[c_idx],
                n_L_arr[c_idx],
                n_Sub_arr[c_idx],
                probe_offset,
                noise_values[r_idx],
                non_monotonic_factor,
                non_monotonic_mode,
                blk,
                signal_noise_scale,
                signal_noise_seed,
                r_idx,
                tp_hysteresis,
                aff_s,
                aff_o,
                photo_curv,
                poem_enabled,
                smoothing_window,
                nH_real,
                nL_real,
                False,                       # Rate is a Phase B choice, never a candidate
                # 🔴 PHASE A MUST SEE THE SAME MACHINE AS PHASE B -- 12.2, and 17-23 for
                # the same defect on six other parameters. Judging a candidate with a
                # perfect monochromator and then simulating it with a 2 nm slit makes
                # Phase A select exactly the wavelengths the slit destroys: the best
                # dynamics sit at the band edge, which is where the spectral ripple is
                # finest (7.2 nm at 48 layers) and where the slit averages over a quarter
                # of a period. One physical statement, one flag, both stages (14).
                #
                # ⚠️ INDEXED BY CANDIDATE. The bias depends on the monitoring wavelength,
                # and that is precisely what this function varies, so a single per-layer
                # matrix would give every candidate the incumbent's curvature -- the
                # inert-filter failure of 20-control 4.
                slit_arr[c_slit],
            )
            if val > 100000.0:
                # non-terminable deposition: sentinel nominal_th + 1e6
                n_crash += 1
            else:
                # Local error is measured on runs that TERMINATE. Leaving
                # the sentinel there would mix two unrelated quantities
                # -- nanometers and a failure counter -- and a single crashed
                # run would be enough to saturate the layer's P95.
                error_buffer[c_idx, n_ok] = np.abs(val - d_nom)
                n_ok += 1
        if n_ok > 0:
            results[c_idx, 0] = np.percentile(error_buffer[c_idx, :n_ok], 95.0)
            results[c_idx, 1] = np.std(error_buffer[c_idx, :n_ok])
        else:
            results[c_idx, 0] = 1000000.0
            results[c_idx, 1] = 0.0
        results[c_idx, 2] = n_crash / n_runs

        # --- compensation gain: TWO evaluations, ZERO noise, no Monte-Carlo
        #
        # We inject a known error on the previous layer and observe how
        # much the current layer corrects it:
        #     gain = |Delta_d_i| / delta_sonde
        #     < 1 : upstream error is DAMPENED   > 1 : it is AMPLIFIED
        gain = -1.0
        if i_layer >= 1:
            prev_nom = p_thick_nominal[:i_layer].copy()
            prev_prt = prev_nom.copy()
            prev_prt[i_layer - 1] += gain_probe_nm
            # 17-24: the gain used to see the affine distortion but NOT the index
            # corridor, which is incoherent -- either the derivative is taken in the
            # perturbed world or in the nominal one, not half in each. Both are drawn
            # at run index 0, deliberately: the gain is a DERIVATIVE, not a run, so it
            # is evaluated in one representative realisation rather than averaged.
            if affine_scale_amp != 0.0 or affine_offset_amp != 0.0 or photo_curvature_amp != 0.0:
                z_a = _seeded_noise_sample(affine_seed, 0, 0, 0, True)
                z_b = _seeded_noise_sample(affine_seed, 1, 0, 0, True)
                z_c = _seeded_noise_sample(affine_seed, 2, 0, 0, True)
                aff_s_0 = 1.0 + affine_scale_amp * z_a
                aff_o_0 = affine_offset_amp * z_b
                photo_curv_0 = photo_curvature_amp * z_c
            else:
                aff_s_0 = 1.0
                aff_o_0 = 0.0
                photo_curv_0 = 0.0
            if index_corridor > 0.0:
                g1_h = _seeded_noise_sample(index_seed, 0, 0, 0, True)
                g2_h = _seeded_noise_sample(index_seed, 0, 0, 1, True)
                g1_l = _seeded_noise_sample(index_seed, 1, 0, 0, True)
                g2_l = _seeded_noise_sample(index_seed, 1, 0, 1, True)
                u0 = (2.0 * wl - (wl_min + wl_max)) / (wl_max - wl_min)
                nH_g = n_H_arr[c_idx] + (
                    index_corridor * g1_h + index_corridor * g2_h * (1.0 - abs(g1_h)) * u0
                )
                nL_g = n_L_arr[c_idx] + (
                    index_corridor * g1_l + index_corridor * g2_l * (1.0 - abs(g1_l)) * u0
                )
            else:
                nH_g = n_H_arr[c_idx]
                nL_g = n_L_arr[c_idx]
            v_ref, _, _, _, _ = simulate_growth_kernel(
                p_thick_nominal, i_layer, prev_nom, wl,
                n_H_arr[c_idx], n_L_arr[c_idx], n_Sub_arr[c_idx],
                probe_offset, 0.0, non_monotonic_factor, non_monotonic_mode, blk,
                0.0, 0, 0, tp_hysteresis,
                aff_s_0, aff_o_0, photo_curv_0, poem_enabled,
                smoothing_window, nH_g, nL_g,
            )
            v_prt, _, _, _, _ = simulate_growth_kernel(
                p_thick_nominal, i_layer, prev_prt, wl,
                n_H_arr[c_idx], n_L_arr[c_idx], n_Sub_arr[c_idx],
                probe_offset, 0.0, non_monotonic_factor, non_monotonic_mode, blk,
                0.0, 0, 0, tp_hysteresis,
                aff_s_0, aff_o_0, photo_curv_0, poem_enabled,
                smoothing_window, nH_g, nL_g,
            )
            if v_ref < 100000.0 and v_prt < 100000.0:
                delta = np.abs(v_prt - v_ref)
                # Below 0.05 nm there is no longer a thickness: it is less than an
                # atom. We don't fabricate a gain from this residue.
                #
                gain = 0.0 if delta < 0.05 else delta / gain_probe_nm
        else:
            # first layer: nothing upstream, so nothing to compensate
            gain = 0.0
        results[c_idx, 3] = gain
    return results


@njit(parallel=True, cache=True, fastmath=True, nogil=True, error_model="numpy")
def simulate_stack_robustness_batch(
    p_thick_nominal: np.ndarray,
    layer_wavelengths: np.ndarray,
    n_H_vals: np.ndarray,
    n_L_vals: np.ndarray,
    n_Sub_vals: np.ndarray,
    noise_matrix: np.ndarray,
    probe_offset: float,
    non_monotonic_factor: float,
    non_monotonic_mode: int = NON_MONOTONIC_MODE_ATTENUATE,
    signal_noise_scale: np.ndarray = None,
    signal_noise_seed: int = 0,
    tp_hysteresis: float = 0.0,
    affine_scale_amp: float = 0.0,
    affine_offset_amp: float = 0.0,
    photo_curvature_amp: float = 0.0,
    affine_seed: int = 0,
    poem_enabled: bool = True,
    smoothing_window: int = 1,
    index_corridor: float = 0.0,
    index_seed: int = 0,
    corridor_lo: float = 0.0,
    corridor_hi: float = 0.0,
    rate_flags: np.ndarray = None,
    slit_profiles: np.ndarray = None,
    witness_reset_flags: np.ndarray = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """

    Simulates growth for the entire stack for multiple MCS runs in parallel.

    ``corridor_lo`` / ``corridor_hi`` -- the interval over which delta_M(lambda) is
    normalised, supplied by the caller from `corridor_wl_range(spectral, monitoring)`.
    The scoring kernel receives the SAME pair, so both stages apply one dispersion
    curve per material per run. Left at (0, 0) the function degrades to normalising
    over the monitoring wavelengths alone, which is the behaviour from before
    2026-08-10 and is wrong -- see `corridor_wl_range`.

    Returns: (simulated_thicknesses, average_dynamics_per_layer)

    signal_noise_scale : READING noise scale of the monitoring signal, PER
    LAYER, in T units (axis 1.1, cf. `simulate_growth_kernel`). An array and
    not a scalar because the "tolerance in nm" mode converts the tolerance to
    T units via dT/dd, which depends on the layer. None = disabled, and the
    computation path reverts word for word to the one before this parameter.

    signal_noise_seed : stream seed. Function of the draw configuration only,
    NEVER of the strategy -- this is what preserves common random numbers
    between compared strategies.
    """
    n_runs = noise_matrix.shape[0]
    n_layers = len(p_thick_nominal)
    results = np.empty((n_runs, n_layers), dtype=np.float64)
    all_dyns = np.empty((n_runs, n_layers), dtype=np.float64)
    # A23 stage 2. One margin per (run, layer) and per CAUSE -- never merged: the two
    # have different physics and different remedies, and merging them is exactly the
    # confusion Trap 1 corollary 2 warns against. 1e18 = no constraint of that kind.
    all_m_level = np.full((n_runs, n_layers), 1e18, dtype=np.float64)
    all_m_missed = np.full((n_runs, n_layers), 1e18, dtype=np.float64)
    all_m_fab = np.full((n_runs, n_layers), 1e18, dtype=np.float64)
    current_run_th_buffer = np.empty((n_runs, n_layers), dtype=np.float64)
    # Start of the monochromatic block for each layer. At unchanged lambda the
    # monitoring signal is CONTINUOUS, so the already observed turning points
    # remain exploitable by POEM; upon changing lambda the history is lost.
    # This is what gives blocks their value.
    # MULTIPLE-TESTGLASS. `witness_base[i]` = index of the first layer carried by the
    # witness that layer i is monitored on. All zeros = one witness for the whole run,
    # which is the historical behaviour and must stay bit-identical to it.
    #
    # 🔴 THE PART IS NOT CUT. `results` / `current_run_th_buffer` keep every layer of
    # every run: the part stays on the platter and receives the whole stack. Only what
    # the BEAM sees is truncated. 👤 confirmed 2026-08-14 that witness and part receive
    # the same thickness, so the swap separates the optical MEMORY and nothing else --
    # no tooling factor to carry here.
    witness_base = np.zeros(n_layers, dtype=np.int64)
    if witness_reset_flags is not None:
        for i in range(1, n_layers):
            if witness_reset_flags[i]:
                witness_base[i] = i
            else:
                witness_base[i] = witness_base[i - 1]

    block_start = np.zeros(n_layers, dtype=np.int64)
    for i in range(1, n_layers):
        # A fresh witness necessarily opens a new block: the anchors POEM would replay
        # were observed on a piece of glass that is no longer in the beam. Same reason a
        # lambda change or a Rate layer wipes the history, and it must be applied FIRST
        # so the two rules cannot disagree.
        if witness_reset_flags is not None and witness_reset_flags[i]:
            block_start[i] = i
            continue
        # 🔑 A LAYER IN RATE WIPES THE NEXT ONE'S HISTORY, exactly as a wavelength change
        # does -- 14-10: "the machine does not keep the history of extrema crossed after
        # a rate". Nothing is watched during a Rate layer, so any extremum that went past
        # was not recorded; and the anchors acquired BEFORE are worthless too, being now
        # separated from the current signal by an unwatched stretch.
        #
        # 👤 This is exactly what makes a block boundary the cheapest place for a Rate
        # layer (A24, 2026-08-11): there the next layer already starts with n_hist = 0,
        # so the cost is ALREADY PAID and two of the three terms of 14-10 vanish.
        if (
            abs(layer_wavelengths[i] - layer_wavelengths[i - 1]) > 1e-06
            or (rate_flags is not None and rate_flags[i - 1])
        ):
            block_start[i] = i
        else:
            block_start[i] = block_start[i - 1]
    # Supplied by the caller, never recomputed here: the growth path and the scoring
    # path must normalise delta_M(lambda) over one and the same interval.
    #
    # 🔴 NO FALLBACK -- see 17-25. This used to degrade silently to
    # `corridor_wl_range(layer_wavelengths, layer_wavelengths)`, i.e. back to
    # normalising on the monitoring span alone, which is the exact defect corrected on
    # 2026-08-10 and which invalidated every corridor measurement before that date.
    # A caller that forgets the pair must find out, not receive a plausible number.
    if index_corridor > 0.0 and corridor_hi <= corridor_lo:
        raise ValueError(
            "index_corridor is active but corridor_lo/corridor_hi were not supplied; "
            "the envelope must come from the single caller-side computation"
        )
    wl_min, wl_max = corridor_lo, corridor_hi
    for r in prange(n_runs):
        if affine_scale_amp != 0.0 or affine_offset_amp != 0.0 or photo_curvature_amp != 0.0:
            z_a = _seeded_noise_sample(affine_seed, 0, r, 0, True)
            z_b = _seeded_noise_sample(affine_seed, 1, r, 0, True)
            # Group 2, distinct from 0 and 1: gain, offset and detector curvature are
            # three independent imperfections and must not share a draw.
            z_c = _seeded_noise_sample(affine_seed, 2, r, 0, True)
            aff_s = 1.0 + affine_scale_amp * z_a
            aff_o = affine_offset_amp * z_b
            photo_curv = photo_curvature_amp * z_c
        else:
            aff_s = 1.0
            aff_o = 0.0
            photo_curv = 0.0

        if index_corridor > 0.0:
            z1_h = _seeded_noise_sample(index_seed, 0, r, 0, True)
            z2_h = _seeded_noise_sample(index_seed, 0, r, 1, True)
            a_h = index_corridor * z1_h
            b_h = index_corridor * z2_h * (1.0 - abs(z1_h))

            z1_l = _seeded_noise_sample(index_seed, 1, r, 0, True)
            z2_l = _seeded_noise_sample(index_seed, 1, r, 1, True)
            a_l = index_corridor * z1_l
            b_l = index_corridor * z2_l * (1.0 - abs(z1_l))
        else:
            a_h, b_h, a_l, b_l = 0.0, 0.0, 0.0, 0.0

        for i_layer in range(n_layers):
            wl = layer_wavelengths[i_layer]
            n_H, n_L, n_Sub = (n_H_vals[i_layer], n_L_vals[i_layer], n_Sub_vals[i_layer])
            if index_corridor > 0.0:
                u_wl = (2.0 * wl - (wl_min + wl_max)) / (wl_max - wl_min)
                nH_real = n_H + (a_h + b_h * u_wl)
                nL_real = n_L + (a_l + b_l * u_wl)
            else:
                nH_real = n_H
                nL_real = n_L

            noise_val = noise_matrix[r, i_layer]
            sig_scale = 0.0
            if signal_noise_scale is not None:
                sig_scale = signal_noise_scale[i_layer]
            val, dyn, m_lvl, m_mis, m_fab = simulate_growth_kernel(
                p_thick_nominal,
                i_layer,
                current_run_th_buffer[r, :i_layer],
                wl,
                n_H,
                n_L,
                n_Sub,
                probe_offset,
                noise_val,
                non_monotonic_factor,
                non_monotonic_mode,
                block_start[i_layer],
                sig_scale,
                signal_noise_seed,
                r,
                tp_hysteresis,
                aff_s,
                aff_o,
                photo_curv,
                poem_enabled,
                smoothing_window,
                nH_real,
                nL_real,
                rate_flags is not None and rate_flags[i_layer],
                # The WHOLE matrix, not the row: the kernel replays the block history and
                # each replayed layer must carry its own bias profile, not this layer's.
                slit_profiles,
                witness_base[i_layer],
                # ⚠️ Les deux defauts du noyau, repetes tels quels pour pouvoir atteindre le
                # parametre suivant par position. `machine_sampling_dd` reste donc a 0.0 --
                # c'est le defaut A8 documente comme INATTEIGNABLE, et ce n'est pas ici
                # qu'on le repare : le repeter ne change rien, l'omettre non plus.
                False,
                0.0,
                # 👤 2026-08-19 : le rate ne se calcule QUE sur les couches optiquement
                # deposees. Le noyau ne recevait que le drapeau de la couche courante et
                # reprenait donc les couches Rate anterieures comme references, alors
                # qu'elles ne portent aucune mesure. On lui passe le tableau entier.
                rate_flags,
            )
            current_run_th_buffer[r, i_layer] = val
            results[r, i_layer] = val
            all_dyns[r, i_layer] = dyn
            all_m_level[r, i_layer] = m_lvl
            all_m_missed[r, i_layer] = m_mis
            all_m_fab[r, i_layer] = m_fab
    avg_dyns = np.zeros(n_layers, dtype=np.float64)
    for l in range(n_layers):
        sum_dyn = 0.0
        for r in range(n_runs):
            sum_dyn += all_dyns[r, l]
        avg_dyns[l] = sum_dyn / n_runs
    return (results, avg_dyns, all_m_level, all_m_missed, all_m_fab)


@njit(parallel=True, cache=True, fastmath=True, nogil=True, error_model="numpy")
def compute_batch_rmse(
    sim_thick_batch: np.ndarray,
    wls: np.ndarray,
    nH_arr: np.ndarray,
    nL_arr: np.ndarray,
    nSub_arr: np.ndarray,
    T_target: np.ndarray,
    n_layers_flattened: np.ndarray,
    weights: np.ndarray = None,
    index_corridor: float = 0.0,
    index_seed: int = 0,
    corridor_wl_min: float = 0.0,
    corridor_wl_max: float = 0.0,
) -> np.ndarray:
    """Computes RMSE for a batch of simulated thicknesses against a target T spectrum.

    ``index_corridor`` -- INDEX UNCERTAINTY ON THE SCORING PATH. 0.0 = disabled, and
    the computation path is then word for word the one from before this parameter.

    🔴 WHY THE SCORING MUST BE PERTURBED TOO, AND NOT ONLY THE GROWTH.
    The deposited filter really carries the wrong index. Evaluating its spectrum at
    the NOMINAL index measures a filter that does not exist. Worse, it hides the one
    mode the physicist calls uncompensable: a CROSSED dispersion curve carries an
    error of opposite sign on either side of the monitoring wavelength, so the
    correction made at that wavelength AGGRAVATES the error elsewhere -- and that
    shows up in the final spectrum, nowhere else. Perturbing the growth alone
    measures the compensable half of the problem and calls it the whole.

    🔴 THE DRAW IS REPEATED HERE, NOT PASSED IN, AND THAT IS DELIBERATE.
    Same seed, same group (0 = H, 1 = L), same run index, same formula as
    ``simulate_stack_robustness_batch``: the two stages therefore see the SAME index
    curve for the same run, which is what contraint C2 demands. Threading four arrays
    through the call chain would have offered a way for them to drift apart.

    ⚠️ ``corridor_wl_min`` / ``corridor_wl_max`` MUST be the values the growth batch
    used -- the range of the MONITORING wavelengths, not of the spectral grid. Pass
    them explicitly; a local recomputation here would normalise over the spectral
    grid and silently apply a different perturbation to the same material.

    ``weights`` -- SPECTRAL WEIGHTING, axis 3. ``None`` = uniform, and the computation
    path then becomes word for word the one before this parameter.

    🔴 WHY WEIGHTING IS INDISPENSABLE ON A DICHROIC.
    👤 The physicist: "the most important is the respected spectral target". However,
    a uniform RMSE on the final arbiter makes the BLOCKED band weigh -- 146 points
    out of 301, with a 0.1% transmission requirement -- exactly as much as the passband,
    where a deviation of a full point is inconsequential. The requirement there is 500
    times harder and it counts the same. A global RMSE on a dichroic thus says nothing,
    and this is why every metric in this module is broken down by band.

    The expected weights are those that DESIGN already uses
    (``prepare_targets_vectorized`` : user weight of the zone x spectral
    quadrature in d ln lambda). A point outside any zone receives a ZERO weight --
    it then does not enter the denominator, which is the intended behavior: a
    wavelength about which the user said nothing should neither help nor penalize.

    Args:

        sim_thick_batch: (n_runs, n_layers)

        wls: (n_wls,)

        nSub_arr: (n_wls,)

        T_target: (n_wls,)

        n_layers_flattened: (n_wls, n_layers) complex array of refractive clues

                           This must be pre-assembled: [n0_w0, n1_w0...; n0_w1, n1_w1...]

    Returns:

        rmse_arr: (n_runs,)"""
    n_runs = sim_thick_batch.shape[0]
    n_wls = len(wls)
    n_layers = sim_thick_batch.shape[1]
    rmse_arr = np.empty(n_runs, dtype=np.float64)
    k0_arr = TWO_PI / wls
    corridor_on = index_corridor > 0.0 and corridor_wl_max > corridor_wl_min
    for r in prange(n_runs):
        thicknesses = sim_thick_batch[r]
        # Same draw as the growth batch: same seed, same groups, same run index.
        # 0 = H (even layers), 1 = L (odd layers).
        a_h = 0.0
        b_h = 0.0
        a_l = 0.0
        b_l = 0.0
        if corridor_on:
            z1_h = _seeded_noise_sample(index_seed, 0, r, 0, True)
            z2_h = _seeded_noise_sample(index_seed, 0, r, 1, True)
            a_h = index_corridor * z1_h
            b_h = index_corridor * z2_h * (1.0 - abs(z1_h))
            z1_l = _seeded_noise_sample(index_seed, 1, r, 0, True)
            z2_l = _seeded_noise_sample(index_seed, 1, r, 1, True)
            a_l = index_corridor * z1_l
            b_l = index_corridor * z2_l * (1.0 - abs(z1_l))
        n_pert = np.empty(n_layers, dtype=np.complex128)
        mse_sum = 0.0
        w_sum = 0.0
        for i_wl in range(n_wls):
            n_row = n_layers_flattened[i_wl]
            if corridor_on:
                u_wl = (2.0 * wls[i_wl] - (corridor_wl_min + corridor_wl_max)) / (
                    corridor_wl_max - corridor_wl_min
                )
                d_h = a_h + b_h * u_wl
                d_l = a_l + b_l * u_wl
                for j in range(n_layers):
                    n_pert[j] = n_row[j] + (d_h if j % 2 == 0 else d_l)
                n_row = n_pert
            Rf, Tf, Rb = compute_TMM_single_point_k0_exact(
                k0_arr[i_wl], thicknesses, n_row, nSub_arr[i_wl]
            )
            ns_real = nSub_arr[i_wl].real
            r_sub = (ns_real - 1.0) / (ns_real + 1.0)
            R_sub_air = r_sub * r_sub
            T_sub_air = 1.0 - R_sub_air
            denom = 1.0 - Rb * R_sub_air
            if denom < 1e-12:
                denom = 1e-12
            T_total = Tf * T_sub_air / denom
            diff = T_total - T_target[i_wl]
            if weights is None:
                mse_sum += diff * diff
            else:
                w = weights[i_wl]
                mse_sum += w * diff * diff
                w_sum += w
        if weights is None:
            rmse_arr[r] = np.sqrt(mse_sum / n_wls)
        elif w_sum > 1e-300:
            rmse_arr[r] = np.sqrt(mse_sum / w_sum)
        else:
            # No zone covers the grid: returning 0 would make any strategy look
            # perfect. We return infinity, which eliminates and is visible.
            rmse_arr[r] = np.inf
    return rmse_arr


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def precompute_matrix_cache_kernel(
    all_wls: np.ndarray, n_H_arr: np.ndarray, n_L_arr: np.ndarray, p_thick_nominal: np.ndarray, num_layers: int
) -> np.ndarray:
    """Parallel computation of nominal transfer matrix cache.

    Supports complex refractive clues for nH and nL."""
    n_wls = len(all_wls)
    TWO_PI_LOCAL = 2.0 * np.pi
    cache = np.zeros((num_layers, n_wls, 2, 2), dtype=np.complex128)
    for wl_idx in prange(n_wls):
        wl = all_wls[wl_idx]
        inv_wl = TWO_PI_LOCAL / wl
        M00 = complex(1.0, 0.0)
        M01 = complex(0.0, 0.0)
        M10 = complex(0.0, 0.0)
        M11 = complex(1.0, 0.0)
        for i_layer in range(num_layers):
            n_layer = n_H_arr[wl_idx] if i_layer % 2 == 0 else n_L_arr[wl_idx]
            thickness = p_thick_nominal[i_layer]
            phi = inv_wl * n_layer * thickness
            cp = np.cos(phi)
            isp = +1j * np.sin(phi)
            if abs(n_layer) > 1e-12:
                m01 = isp / n_layer
            else:
                m01 = 0j
            m10 = isp * n_layer
            t00 = cp * M00 + m01 * M10
            t01 = cp * M01 + m01 * M11
            t10 = m10 * M00 + cp * M10
            t11 = m10 * M01 + cp * M11
            M00, M01, M10, M11 = (t00, t01, t10, t11)
            cache[i_layer, wl_idx, 0, 0] = M00
            cache[i_layer, wl_idx, 0, 1] = M01
            cache[i_layer, wl_idx, 1, 0] = M10
            cache[i_layer, wl_idx, 1, 1] = M11
    return cache


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _calculate_RT_HL_single_point(wl, nH, nL, n_s, thicknesses):
    """Single wavelength, single run TMM for HL stacks.

    CONVENTION: index 0 = layer 1 = substrate side (aligned with compute_TMM_single_point_k0_exact).

    j=0 -> nH, j=1 -> nL => Sub | nH(thicknesses[0]) | nL(thicknesses[1]) | Air."""
    k0 = TWO_PI / wl
    n_layers = len(thicknesses)
    I_VAL = +1j
    M00 = 1.0 + 0j
    M01 = 0.0 + 0j
    M10 = 0.0 + 0j
    M11 = 1.0 + 0j
    for j in range(n_layers):
        d = thicknesses[j]
        n_l = nH if j % 2 == 0 else nL
        phi = k0 * n_l * d
        cp = np.cos(phi)
        sp = np.sin(phi)
        son = sp / n_l if abs(n_l) > 1e-12 else 0j
        m01 = I_VAL * son
        m10 = I_VAL * n_l * sp
        t00 = cp * M00 + m01 * M10
        t01 = cp * M01 + m01 * M11
        t10 = m10 * M00 + cp * M10
        t11 = m10 * M01 + cp * M11
        M00, M01, M10, M11 = (t00, t01, t10, t11)
    n_air = complex(1.0)
    R_front, T_front = compute_RT_from_matrix(M00, M01, M10, M11, n_air, n_s)
    Mp00 = 1.0 + 0j
    Mp01 = 0.0 + 0j
    Mp10 = 0.0 + 0j
    Mp11 = 1.0 + 0j
    for j in range(n_layers):
        d = thicknesses[j]
        n_l = nH if j % 2 == 0 else nL
        phi = k0 * n_l * d
        cp = np.cos(phi)
        sp = np.sin(phi)
        son = sp / n_l if abs(n_l) > 1e-12 else 0j
        m01 = I_VAL * son
        m10 = I_VAL * n_l * sp
        t00 = Mp00 * cp + Mp01 * m10
        t01 = Mp00 * m01 + Mp01 * cp
        t10 = Mp10 * cp + Mp11 * m10
        t11 = Mp10 * m01 + Mp11 * cp
        Mp00, Mp01, Mp10, Mp11 = (t00, t01, t10, t11)
    R_prime, _ = compute_RT_from_matrix(Mp00, Mp01, Mp10, Mp11, n_s, n_air)
    nsr = n_s.real
    r_sub = (nsr - 1.0) / (nsr + 1.0)
    R_sub = r_sub * r_sub
    T_sub = 1.0 - R_sub
    denom = 1.0 - R_prime * R_sub
    if denom < 1e-12:
        denom = 1e-12
    T_total = T_front * T_sub / denom
    R_total = R_front + T_front * T_front * R_sub / denom
    return (R_total, T_total)


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_RT_batch_kernel(wls, nH_arr, nL_arr, nSub_arr, thicknesses_batch):
    """
    Parallel loop over 'num_runs', where each run is a full TMM spectral calculation.
    thicknesses_batch: (num_runs, num_layers)
    """
    n_runs = thicknesses_batch.shape[0]
    n_wls = wls.shape[0]
    R_batch = np.empty((n_runs, n_wls), dtype=np.float64)
    T_batch = np.empty((n_runs, n_wls), dtype=np.float64)
    for r in prange(n_runs):
        thicknesses = thicknesses_batch[r]
        for wl_idx in range(n_wls):
            r_val, t_val = _calculate_RT_HL_single_point(
                wls[wl_idx], nH_arr[wl_idx], nL_arr[wl_idx], nSub_arr[wl_idx], thicknesses
            )
            R_batch[r, wl_idx] = r_val
            T_batch[r, wl_idx] = t_val
    return (R_batch, T_batch)
