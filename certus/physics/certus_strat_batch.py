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
from .certus_strat_math import check_extrema_proximity_batch, _calc_T_from_matrix, _calc_T_added_layer
from .certus_strat_growth import simulate_growth_kernel


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
):
    """Evalue chaque longueur d'onde candidate pour UNE couche (Phase A).

    Renvoie un tableau (n_cands, 4) :

        [c, 0]  P95(|Delta_d|)   erreur LOCALE, sur les runs qui se TERMINENT
        [c, 1]  ecart-type       idem
        [c, 2]  taux de plantage fraction de runs non terminables
        [c, 3]  gain de compensation, ou -1.0 si non mesurable

    🔴 TROIS CRITERES, ET ILS SONT ORTHOGONAUX.

    P95(|Delta_d|) ne mesure que l'erreur LOCALE de la couche. Une couche peut
    etre precise localement et AMPLIFIER ce qu'elle recoit : sur 48 couches c'est
    le gain qui decide si l'erreur reste bornee, pas l'erreur locale.

    Et un 95e percentile est structurellement AVEUGLE a tout evenement survenant
    dans moins de 5 % des runs : un depot qui ne se termine pas 2 fois sur 100
    n'y laissait aucune trace, alors que c'est un run perdu en salle.

    Mesure sur example/example_strat, couche 25 :
        lambda 550 nm -> gain 0,257  |  lambda 475 nm -> gain 4,35
    soit un facteur 17 entre deux longueurs d'onde que le seul P95 pouvait
    classer dans l'ordre inverse.

    gain_probe_nm : amplitude de l'erreur amont injectee pour mesurer le gain.
    1,0 nm par defaut — vingt fois le seuil sous lequel une difference
    d'epaisseur n'a plus de sens physique (0,05 nm, soit moins d'un atome), et
    dans le regime lineaire du gain pour l'essentiel des cas mesures (variation
    inferieure a 10 % entre 0,5 et 2 nm).

    block_start_arr : indice de debut du bloc monochromatique POUR CHAQUE
    candidate. A lambda inchangee le signal est continu et POEM exploite les
    points tournants deja traverses ; au changement de lambda tout est perdu.
    Sans ce tableau la Phase A etait AVEUGLE a la valeur des blocs alors que la
    Phase B, elle, la modelise — mesure sur l'exemple reel, le gain change d'un
    facteur allant jusqu'a 2,5 selon que l'historique est vu ou non.
    None = comportement historique (chaque couche isolee).
    """
    n_cands = len(candidate_wls)
    n_runs = runs_history.shape[0]
    results = np.zeros((n_cands, 4))
    error_buffer = np.empty((n_cands, n_runs), dtype=np.float64)
    d_nom = p_thick_nominal[i_layer]
    for c_idx in prange(n_cands):
        wl = candidate_wls[c_idx]
        blk = -1
        if block_start_arr is not None:
            blk = block_start_arr[c_idx]
        n_ok = 0
        n_crash = 0
        for r_idx in range(n_runs):
            prev_th = runs_history[r_idx, :i_layer]
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
            )
            if val > 100000.0:
                # depot non terminable : sentinelle nominal_th + 1e6
                n_crash += 1
            else:
                # L'erreur locale se mesure sur les runs qui se TERMINENT. Y
                # laisser la sentinelle melangerait deux grandeurs sans rapport
                # — des nanometres et un compteur d'echecs — et un seul run
                # plante suffirait a saturer le P95 de la couche.
                error_buffer[c_idx, n_ok] = np.abs(val - d_nom)
                n_ok += 1
        if n_ok > 0:
            results[c_idx, 0] = np.percentile(error_buffer[c_idx, :n_ok], 95.0)
            results[c_idx, 1] = np.std(error_buffer[c_idx, :n_ok])
        else:
            results[c_idx, 0] = 1000000.0
            results[c_idx, 1] = 0.0
        results[c_idx, 2] = n_crash / n_runs

        # --- gain de compensation : DEUX evaluations, bruit NUL, aucun Monte-Carlo
        #
        # On injecte une erreur connue sur la couche precedente et on regarde de
        # combien la couche courante la corrige :
        #     gain = |Delta_d_i| / delta_sonde
        #     < 1 : l'erreur amont est AMORTIE   > 1 : elle est AMPLIFIEE
        gain = -1.0
        if i_layer >= 1:
            prev_nom = p_thick_nominal[:i_layer].copy()
            prev_prt = prev_nom.copy()
            prev_prt[i_layer - 1] += gain_probe_nm
            v_ref, _ = simulate_growth_kernel(
                p_thick_nominal, i_layer, prev_nom, wl,
                n_H_arr[c_idx], n_L_arr[c_idx], n_Sub_arr[c_idx],
                probe_offset, 0.0, non_monotonic_factor, non_monotonic_mode, blk,
            )
            v_prt, _ = simulate_growth_kernel(
                p_thick_nominal, i_layer, prev_prt, wl,
                n_H_arr[c_idx], n_L_arr[c_idx], n_Sub_arr[c_idx],
                probe_offset, 0.0, non_monotonic_factor, non_monotonic_mode, blk,
            )
            if v_ref < 100000.0 and v_prt < 100000.0:
                delta = np.abs(v_prt - v_ref)
                # Sous 0,05 nm il n'y a plus d'epaisseur : c'est moins d'un
                # atome. On ne fabrique pas un gain a partir de ce residu.
                gain = 0.0 if delta < 0.05 else delta / gain_probe_nm
        else:
            # premiere couche : rien en amont, donc rien a compenser
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
) -> tuple[np.ndarray, np.ndarray]:
    """

    Simulates growth for the entire stack for multiple MCS runs in parallel.

    Returns: (simulated_thicknesses, average_dynamics_per_layer)

    """
    n_runs = noise_matrix.shape[0]
    n_layers = len(p_thick_nominal)
    results = np.empty((n_runs, n_layers), dtype=np.float64)
    all_dyns = np.empty((n_runs, n_layers), dtype=np.float64)
    current_run_th_buffer = np.empty((n_runs, n_layers), dtype=np.float64)
    # Debut du bloc monochromatique de chaque couche. A lambda inchangee le signal
    # de monitoring est CONTINU, donc les points tournants deja observes restent
    # exploitables par POEM ; au changement de lambda l'historique est perdu.
    # C'est ce qui donne leur valeur aux blocs.
    block_start = np.zeros(n_layers, dtype=np.int64)
    for i in range(1, n_layers):
        if abs(layer_wavelengths[i] - layer_wavelengths[i - 1]) > 1e-06:
            block_start[i] = i
        else:
            block_start[i] = block_start[i - 1]
    for r in prange(n_runs):
        for i_layer in range(n_layers):
            wl = layer_wavelengths[i_layer]
            n_H, n_L, n_Sub = (n_H_vals[i_layer], n_L_vals[i_layer], n_Sub_vals[i_layer])
            noise_val = noise_matrix[r, i_layer]
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
) -> np.ndarray:
    """Computes RMSE for a batch of simulated thicknesses against a target T spectrum.

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
            mse_sum += diff * diff
        rmse_arr[r] = np.sqrt(mse_sum / n_wls)
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
