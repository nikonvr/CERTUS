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
    affine_seed: int = 0,
    poem_enabled: bool = True,
    smoothing_window: int = 1,
    index_corridor: float = 0.0,
    index_seed: int = 0,
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
    wl_min = np.min(candidate_wls)
    wl_max = np.max(candidate_wls)
    if abs(wl_max - wl_min) < 1e-6:
        wl_max = wl_min + 100.0
    for c_idx in prange(n_cands):
        wl = candidate_wls[c_idx]
        blk = -1
        if block_start_arr is not None:
            blk = block_start_arr[c_idx]
        n_ok = 0
        n_crash = 0
        for r_idx in range(n_runs):
            prev_th = runs_history[r_idx, :i_layer]
            if affine_scale_amp != 0.0 or affine_offset_amp != 0.0:
                z_a = _seeded_noise_sample(affine_seed, 0, r_idx, 0, True)
                z_b = _seeded_noise_sample(affine_seed, 1, r_idx, 0, True)
                aff_s = 1.0 + affine_scale_amp * z_a
                aff_o = affine_offset_amp * z_b
            else:
                aff_s = 1.0
                aff_o = 0.0

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

            val, _ = simulate_growth_kernel(
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
                poem_enabled,
                smoothing_window,
                nH_real,
                nL_real,
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
            if affine_scale_amp != 0.0 or affine_offset_amp != 0.0:
                z_a = _seeded_noise_sample(affine_seed, 0, 0, 0, True)
                z_b = _seeded_noise_sample(affine_seed, 1, 0, 0, True)
                aff_s_0 = 1.0 + affine_scale_amp * z_a
                aff_o_0 = affine_offset_amp * z_b
            else:
                aff_s_0 = 1.0
                aff_o_0 = 0.0
            v_ref, _ = simulate_growth_kernel(
                p_thick_nominal, i_layer, prev_nom, wl,
                n_H_arr[c_idx], n_L_arr[c_idx], n_Sub_arr[c_idx],
                probe_offset, 0.0, non_monotonic_factor, non_monotonic_mode, blk,
                0.0, 0, 0, tp_hysteresis,
                aff_s_0, aff_o_0, poem_enabled,
                smoothing_window,
            )
            v_prt, _ = simulate_growth_kernel(
                p_thick_nominal, i_layer, prev_prt, wl,
                n_H_arr[c_idx], n_L_arr[c_idx], n_Sub_arr[c_idx],
                probe_offset, 0.0, non_monotonic_factor, non_monotonic_mode, blk,
                0.0, 0, 0, tp_hysteresis,
                aff_s_0, aff_o_0, poem_enabled,
                smoothing_window,
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
    affine_seed: int = 0,
    poem_enabled: bool = True,
    smoothing_window: int = 1,
    index_corridor: float = 0.0,
    index_seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """

    Simulates growth for the entire stack for multiple MCS runs in parallel.

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
    current_run_th_buffer = np.empty((n_runs, n_layers), dtype=np.float64)
    # Start of the monochromatic block for each layer. At unchanged lambda the
    # monitoring signal is CONTINUOUS, so the already observed turning points
    # remain exploitable by POEM; upon changing lambda the history is lost.
    # This is what gives blocks their value.
    block_start = np.zeros(n_layers, dtype=np.int64)
    for i in range(1, n_layers):
        if abs(layer_wavelengths[i] - layer_wavelengths[i - 1]) > 1e-06:
            block_start[i] = i
        else:
            block_start[i] = block_start[i - 1]
    wl_min = np.min(layer_wavelengths)
    wl_max = np.max(layer_wavelengths)
    if abs(wl_max - wl_min) < 1e-6:
        wl_max = wl_min + 100.0
    for r in prange(n_runs):
        if affine_scale_amp != 0.0 or affine_offset_amp != 0.0:
            z_a = _seeded_noise_sample(affine_seed, 0, r, 0, True)
            z_b = _seeded_noise_sample(affine_seed, 1, r, 0, True)
            aff_s = 1.0 + affine_scale_amp * z_a
            aff_o = affine_offset_amp * z_b
        else:
            aff_s = 1.0
            aff_o = 0.0

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
            val, dyn = simulate_growth_kernel(
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
                poem_enabled,
                smoothing_window,
                nH_real,
                nL_real,
            )
            current_run_th_buffer[r, i_layer] = val
            results[r, i_layer] = val
            all_dyns[r, i_layer] = dyn
    avg_dyns = np.zeros(n_layers, dtype=np.float64)
    for l in range(n_layers):
        sum_dyn = 0.0
        for r in range(n_runs):
            sum_dyn += all_dyns[r, l]
        avg_dyns[l] = sum_dyn / n_runs
    return (results, avg_dyns)


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
) -> np.ndarray:
    """Computes RMSE for a batch of simulated thicknesses against a target T spectrum.

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
    rmse_arr = np.empty(n_runs, dtype=np.float64)
    k0_arr = TWO_PI / wls
    for r in prange(n_runs):
        thicknesses = sim_thick_batch[r]
        mse_sum = 0.0
        w_sum = 0.0
        for i_wl in range(n_wls):
            Rf, Tf, Rb = compute_TMM_single_point_k0_exact(
                k0_arr[i_wl], thicknesses, n_layers_flattened[i_wl], nSub_arr[i_wl]
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
